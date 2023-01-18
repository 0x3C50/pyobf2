from _ast import JoinedStr, FormattedValue, Call, Name, Load, Constant, Attribute, AST
from ast import NodeTransformer
from typing import Any

from . import Transformer, collect_fstring_consts


class FstringsToFormatSequence(Transformer, NodeTransformer):
    conversion_method_dict = {"s": "str", "r": "repr", "a": "ascii"}

    def __init__(self):
        super().__init__("fstrToFormatSeq", "Converts F-Strings to their str.format equivalent")

    def visit_JoinedStr(self, node: JoinedStr) -> Any:
        converted_format = ""
        collected_args = []
        for value in node.values:
            if isinstance(value, FormattedValue):
                converted_format += "{"
                if value.format_spec is not None and isinstance(value.format_spec, JoinedStr):  # god i hate fstrings
                    converted_format += ":" + collect_fstring_consts(value.format_spec)
                converted_format += "}"
                loader_mth = value.value
                if value.conversion != -1 and chr(value.conversion) in self.conversion_method_dict:
                    mth = self.conversion_method_dict[chr(value.conversion)]
                    loader_mth = Call(func=Name(mth, Load()), args=[loader_mth], keywords=[])
                collected_args.append(loader_mth)
            elif isinstance(value, Constant):
                converted_format += str(value.value)
        return Call(
            func=Attribute(value=Constant(converted_format), attr="format", ctx=Load()),
            args=collected_args,
            keywords=[],
        )

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        return self.visit(ast)
