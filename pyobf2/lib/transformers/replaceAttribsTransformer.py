from _ast import Assign, Attribute, Expr, Call, Name, Load, Constant, AST
from ast import NodeTransformer
from typing import Any

from . import Transformer


class ReplaceAttribs(Transformer, NodeTransformer):
    def __init__(self):
        super().__init__("replaceAttribSet", "Replaces direct attribute sets with setattr")

    def visit_Assign(self, node: Assign) -> Any:
        if len(node.targets) == 1:
            attrib = node.targets[0]
            if isinstance(attrib, Attribute):
                parent = attrib.value
                name = attrib.attr
                value = node.value
                return Expr(Call(func=Name("setattr", Load()), args=[parent, Constant(name), value], keywords=[]))
        return self.generic_visit(node)

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        return self.visit(ast)
