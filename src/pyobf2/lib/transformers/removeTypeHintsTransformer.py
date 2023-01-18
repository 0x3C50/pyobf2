from _ast import FunctionDef, arg, AnnAssign, Assign, AST, Constant
from ast import NodeTransformer, dump
from typing import Any

from . import Transformer


class RemoveTypeHints(Transformer, NodeTransformer):
    def __init__(self):
        super().__init__("removeTypeHints", "Removes type hints")

    def visit_FunctionDef(self, node: FunctionDef) -> Any:
        node.returns = None
        return self.generic_visit(node)

    def visit_arg(self, node: arg) -> Any:
        node.annotation = None
        return self.generic_visit(node)

    def visit_AnnAssign(self, node: AnnAssign) -> Any:
        # print(dump(node, indent=2))
        a = Assign(targets=[node.target], value=node.value or Constant(None))
        return self.generic_visit(a)

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        return self.visit(ast)
