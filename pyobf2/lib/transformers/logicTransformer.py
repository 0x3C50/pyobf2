from typing import Any

from . import *
from ast import *


def _generator_if_and(node: If):
    node.test = BoolOp(
        op=And(),
        values=[
            node.test,
            Compare(
                left=Call(
                    func=Attribute(value=ast_import_full("random"), attr="betavariate", ctx=Load()),
                    args=[Constant(random.uniform(1, 100)), Constant(random.uniform(1, 100))],
                    keywords=[],
                ),
                ops=[NotEq()],
                comparators=[Constant(random.uniform(1.1, 100))],
            ),
        ],
    )


def _generator_if_or(node: If):
    node.test = BoolOp(
        op=Or(),
        values=[
            node.test,
            Compare(
                left=Call(
                    func=Attribute(value=ast_import_full("random"), attr="betavariate", ctx=Load()),
                    args=[Constant(random.uniform(1, 100)), Constant(random.uniform(1, 100))],
                    keywords=[],
                ),
                ops=[Eq()],
                comparators=[Constant(random.uniform(1.1, 100))],
            ),
        ],
    )


all_cond_gens = [_generator_if_and, _generator_if_or]


def create_equivalent_dogshit(node: If) -> If:
    random.choice(all_cond_gens)(node)
    return node


def wrap_cond(node: If):
    radix = random.randint(3, 16)
    node.test = Compare(
        left=BinOp(left=node.test, op=LShift(), right=Constant(radix)), ops=[Eq()], comparators=[Constant(1 << radix)]
    )


class LogicTransformer(Transformer, NodeVisitor):
    def __init__(self):
        super().__init__("logicTransformer", "Transforms boolean logic into confusing, but equally valid statements")

    def visit_If(self, node: If) -> Any:
        create_equivalent_dogshit(node)
        wrap_cond(node)

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        self.visit(ast)
        return ast
