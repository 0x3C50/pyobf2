import base64
import zlib
from _ast import JoinedStr, FormattedValue, Constant, Call, Attribute, Load, AST
from ast import NodeTransformer
from typing import Any

from . import Transformer, ast_import_full


class EncodeStrings(Transformer, NodeTransformer):
    def __init__(self):
        self.in_formatted_str = False
        self.no_lzma = False
        super().__init__("encodeStrings", "Encodes strings with base64 and (if not in a fstring) lzma")

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

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        return self.visit(ast)
