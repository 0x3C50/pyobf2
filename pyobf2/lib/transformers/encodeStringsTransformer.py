import base64
import random
import zlib
from _ast import *
from ast import NodeTransformer
from typing import Any

from . import Transformer, ast_import_full
from ..cfg import ConfigValue
from ..log import warn


class EncodeStrings(Transformer, NodeTransformer):
    def __init__(self):
        self.in_formatted_str = False
        self.no_lzma = False
        self.xor_table = []
        self.fname = None
        super().__init__(
            "encodeStrings",
            "Encodes strings to make them harder to read",
            mode=ConfigValue(
                "How to transform the strings\n"
                "Mode chararray is best used with the intObfuscator transformer\n"
                "Available modes: b64lzma, chararray, xortable",
                "b64lzma",
            ),
        )

    def visit_JoinedStr(self, node: JoinedStr) -> Any:
        self.in_formatted_str = True
        self.no_lzma = True
        r = self.generic_visit(node)
        self.no_lzma = False
        self.in_formatted_str = False
        return r

    def visit_FormattedValue(self, node: FormattedValue) -> Any:
        prev = self.in_formatted_str
        self.in_formatted_str = False
        r = self.generic_visit(node)
        self.in_formatted_str = prev
        return r

    def visit_constant_b64lzma(self, node: Constant):
        do_decode = False
        val = node.value
        if isinstance(val, str):
            encoded = base64.b64encode(val.encode("utf8"))
            do_decode = True
            if self.no_lzma:  # can't use unicode chars in fstrings since these would lead to escapes
                compressed = encoded
            else:
                compressed = zlib.compress(encoded, 9)
        elif type(val) == bytes:
            encoded = base64.b64encode(val)
            if self.no_lzma:
                compressed = encoded
            else:
                compressed = zlib.compress(encoded, 9)
        else:
            compressed = None
        if compressed is not None:
            t = Call(
                func=Attribute(value=ast_import_full("base64"), attr="b64decode", ctx=Load()),
                args=[
                    # We haven't compressed if we're in an fstr
                    Call(
                        func=Attribute(value=ast_import_full("zlib"), attr="decompress", ctx=Load()),
                        args=[Constant(compressed)],
                        keywords=[],
                    )
                    if not self.no_lzma
                    else Constant(compressed)
                ],
                keywords=[],
            )
            if do_decode:
                t = Call(func=Attribute(value=t, attr="decode", ctx=Load()), args=[], keywords=[])
            if self.in_formatted_str:
                t = FormattedValue(value=t, conversion=-1)
            return t
        else:
            return self.generic_visit(node)

    def visit_constant_xortable(self, node: Constant):
        val = node.value
        if not isinstance(val, str) and not isinstance(val, bytes):
            return self.generic_visit(node)
        if len(val) == 0:
            return node
        if len(val) > 250:
            warn(self.fname, node, f"String too big to obfuscate properly using xor table ({len(val)} > 250)")
            return node
        raw_ints = [(ord(x) if type(node.value) == str else x) for x in list(val)]
        encoded_positions = [(raw_ints[i] ^ self.xor_table[i % len(self.xor_table)], i) for i in range(len(raw_ints))]
        random.shuffle(encoded_positions)
        ie = IfExp(
            test=Compare(left=Name("i", Load()), ops=[Eq()], comparators=[Constant(encoded_positions[0][1])]),
            body=Constant(encoded_positions[0][0]),
            orelse=Constant(random.randint(0, 0xFFFF)),
        )
        for x in range(1, len(encoded_positions)):
            current_ps = encoded_positions[x]
            ie = IfExp(
                test=Compare(left=Name("i", Load()), ops=[Eq()], comparators=[Constant(current_ps[1])]),
                body=Constant(current_ps[0]),
                orelse=ie,
            )
        generator_elem = BinOp(
            left=ie,
            op=BitXor(),
            right=Subscript(
                value=Name("xor_table", Load()),
                slice=BinOp(
                    left=Name(id="i", ctx=Load()),
                    op=Mod(),
                    right=Call(func=Name(id="len", ctx=Load()), args=[Name(id="xor_table", ctx=Load())], keywords=[]),
                ),
                ctx=Load(),
            ),
        )
        if type(val) == str:
            generator_elem = Call(Name("chr", Load()), [generator_elem], [])
        decrypt_generator = ListComp(
            elt=generator_elem,
            generators=[
                comprehension(
                    target=Name("i", Store()),
                    iter=Call(func=Name("range", Load()), args=[Constant(len(encoded_positions))], keywords=[]),
                    ifs=[],
                    is_async=0,
                )
            ],
        )
        if type(val) == str:
            return Call(
                func=Attribute(value=Constant("" if type(val) == str else b""), attr="join", ctx=Load()),
                args=[decrypt_generator],
                keywords=[],
            )
        else:
            return Call(
                func=Name("bytes", Load()),
                args=[decrypt_generator],
                keywords=[],
            )

    def visit_constant_chararray(self, node: Constant):
        val = node.value
        if not isinstance(val, str) and not isinstance(val, bytes):
            return self.generic_visit(node)
        chars = list(val)
        mapped_int_chars = [(ord(x) if type(val) == str else x) for x in chars]
        if type(val) == str:
            return Call(
                func=Attribute(value=Constant("" if type(val) == str else b""), attr="join", ctx=Load()),
                args=[
                    ListComp(
                        elt=Call(func=Name("chr", Load()), args=[Name("x", Load())], keywords=[]),
                        generators=[
                            comprehension(
                                target=Name("x", Store()),
                                iter=List(elts=[Constant(x) for x in mapped_int_chars], ctx=Load()),
                                ifs=[],
                                is_async=0,
                            )
                        ],
                    )
                ],
                keywords=[],
            )
        else:
            return Call(
                func=Name("bytes", Load()),
                args=[List(elts=[Constant(x) for x in mapped_int_chars], ctx=Load())],
                keywords=[],
            )

    def visit_Constant(self, node: Constant) -> Any:
        mode = self.config["mode"].value
        if mode == "b64lzma":
            return self.visit_constant_b64lzma(node)
        elif mode == "chararray":
            return self.visit_constant_chararray(node)
        elif mode == "xortable":
            return self.visit_constant_xortable(node)

    def _generator_xor_table(self, length: int):
        self.xor_table = [random.randint(0x0001, 0xFFFF) for _ in range(length)]

    def visit_Module(self, node: Module) -> Any:
        if self.config["mode"].value == "xortable":
            self._generator_xor_table(64)
            xor_table_save = Assign([Name("xor_table", Store())], List([Constant(x) for x in self.xor_table], Load()))
            node.body.insert(0, xor_table_save)
        return self.generic_visit(node)

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        if self.config["mode"].value not in ("b64lzma", "chararray", "xortable"):
            raise ValueError("Invalid mode " + self.config["mode"].value)
        self.fname = current_file_name
        return self.visit(ast)
