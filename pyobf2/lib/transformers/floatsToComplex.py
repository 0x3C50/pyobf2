import math
from typing import Any

from . import *
from ast import *


def decoder_int(c: int):
    a = random.uniform(0, c)  # 0-c to avoid sqrt() having a negative input
    b = math.sqrt(c**2 - a**2)
    return Call(
        func=Name("round", Load()),
        args=[Call(func=Name("abs", Load()), args=[BinOp(Constant(a), Add(), Constant(b * 1j))], keywords=[])],
        keywords=[],
    )


def decoder_float(c: float):
    float_part = c - int(c)
    return BinOp(left=decoder_int(int(c)), op=Add(), right=Constant(float_part))


class FloatsToComplex(Transformer, NodeTransformer):
    def __init__(self):
        super().__init__(
            "floatsToComplex",
            "Converts floats to a representation of them on the complex number plane, "
            "then converts them back at runtime\n"
            "Warning: float precision might change some numbers in ways you don't want, please open a bug report "
            "if you find such a case",
        )

    def visit_Constant(self, node: Constant) -> Any:
        val = node.value
        t = type(val)
        if t != int and t != float:
            return self.generic_visit(node)
        if t == int:
            return decoder_int(val)
        elif t == float:
            return decoder_float(val)

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        return self.visit(ast)
