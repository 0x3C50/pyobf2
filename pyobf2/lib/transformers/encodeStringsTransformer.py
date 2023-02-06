import base64
import zlib
from _ast import (
    JoinedStr,
    FormattedValue,
    Constant,
    Call,
    Attribute,
    Load,
    AST,
    ListComp,
    Name,
    comprehension,
    List,
    Store,
)
from ast import NodeTransformer
from typing import Any

from . import Transformer, ast_import_full
from ..cfg import ConfigValue


class EncodeStrings(Transformer, NodeTransformer):
    def __init__(self):
        self.in_formatted_str = False
        self.no_lzma = False
        super().__init__(
            "encodeStrings",
            "Encodes strings to make them harder to read",
            mode=ConfigValue(
                "How to transform the strings\n"
                "Mode chararray is best used with the intObfuscator transformer\n"
                "Available modes: b64lzma, chararray",
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

    def visit_Constant(self, node: Constant) -> Any:
        val = node.value
        if self.config["mode"].value == "b64lzma":
            do_decode = False
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
        else:
            chars = list(val)
            mapped_int_chars = [ord(x) for x in chars]
            return Call(
                func=Attribute(value=Constant(""), attr="join", ctx=Load()),
                args=[
                    ListComp(
                        elt=Call(func=Name("chr", Load()), args=[Name("x", Load())], keywords=[]),
                        generators=[
                            comprehension(
                                target=Name("x", Store()),
                                iter=List(elts=[Constant(x) for x in mapped_int_chars]),
                                ifs=[],
                                is_async=0,
                            )
                        ],
                    )
                ],
                keywords=[],
            )

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        if self.config["mode"].value not in ("b64lzma", "chararray"):
            raise ValueError("Invalid mode " + self.config["mode"].value)
        return self.visit(ast)
