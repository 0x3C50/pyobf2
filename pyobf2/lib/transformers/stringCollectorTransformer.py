import math
import textwrap
from ast import *
from typing import Any

from pyobf2.lib.transformers import Transformer, rnd_name
from ..cfg import ConfigValue
from ..log import warn


class StringCollectorTransformer(Transformer, NodeTransformer):
    def __init__(self):
        super().__init__(
            "stringCollector",
            "Collects all strings into a list",
            False,
            sample_size=ConfigValue("How many characters to store in a string element. -1 is off", -1),
            max_samples=ConfigValue("How many samples to have, at max", 512),
        )
        self.collected = []
        self.str_col_name = rnd_name()
        self.cf = ""
        self.in_formatted_v = False

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        self.cf = current_file_name
        vst = self.visit(ast)
        if isinstance(vst, Module):
            vst.body.insert(
                0,
                Assign(
                    targets=[Name(self.str_col_name, Store())],
                    value=Constant(self.collected),
                ),
            )
        return vst

    def visit_ClassDef(self, node: ClassDef) -> Any:
        if len(node.body) > 0 and isinstance(node.body[0], Expr) and isinstance(node.body[0].value, Constant):
            node.body = node.body[1:]
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: FunctionDef) -> Any:
        if len(node.body) > 0 and isinstance(node.body[0], Expr) and isinstance(node.body[0].value, Constant):
            node.body = node.body[1:]
        return self.generic_visit(node)

    def visit_JoinedStr(self, node: FormattedValue) -> Any:
        self.in_formatted_v = True
        v = self.generic_visit(node)
        self.in_formatted_v = False
        return v

    def visit_FormattedValue(self, node: FormattedValue) -> Any:
        prev = self.in_formatted_v
        self.in_formatted_v = False
        t = self.generic_visit(node)
        self.in_formatted_v = prev

        return t

    def visit_Constant(self, node: Constant) -> Any:
        if isinstance(node.value, str):
            nv: str = node.value
            t = self.config["sample_size"].value
            if t != -1:
                n_samples = math.ceil(len(nv) / t)
                if n_samples > self.config["max_samples"].value:
                    warn(self.cf, node, f"Would need {n_samples} samples, {self.config['max_samples'].value} is max")
                    return self.generic_visit(node)
            split = textwrap.wrap(nv, t) if t != -1 else [nv]
            if len(split) == 0:
                split = [""]
            p = None
            for x in split:
                if x in self.collected:
                    idx = self.collected.index(x)
                else:
                    idx = len(self.collected)
                    self.collected.append(x)
                el = Subscript(value=Name(self.str_col_name, Load()), slice=Constant(idx), ctx=Load())
                if p is None:
                    p = el
                else:
                    p = BinOp(left=p, op=Add(), right=el)
            if self.in_formatted_v:
                p = FormattedValue(value=p, conversion=-1)
            return p
        return self.generic_visit(node)
