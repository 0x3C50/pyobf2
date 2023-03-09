import itertools
from typing import Any

from . import *
from ast import *
from ..util import random_identifier


class TypeAliasTransformer(Transformer, NodeTransformer):
    def __init__(self):
        super().__init__("typeAliasTransformer",
                         "Adds alias classes to certain classes to obfuscate their original meaning",
                         classes_to_alias=ConfigValue("Classes to create aliases for", [
                             "str",
                             "int",
                             "float",
                             "filter",
                             "bool",
                             "bytes",
                             "map",
                             "range"
                         ])
                         )
        self.entries = []

    def visit_Name(self, node: Name) -> Any:
        n = node.id
        cf = self.config["classes_to_alias"].value
        if n in cf:
            t = random_identifier(32)
            rec = random.randint(5, 10)
            self.entries.append({
                "i": rec,
                "final_name": t,
                "target": n
            })
            return Subscript(
                value=Call(
                    func=Attribute(
                        Name(t, Load()),
                        "mro",
                        Load()
                    ),
                    args=[], keywords=[]
                ),
                slice=Constant(rec),
                ctx=Load()
            )
            # node.id = t
        return node

    def transform(self, aa: AST, current_file_name, all_asts, all_file_names) -> AST:
        aa = self.visit(aa)
        assert isinstance(aa, Module)
        tta = []
        for x in self.entries:
            tt = []
            prev = x["target"]
            for i in range(x["i"] - 1):
                p = random_identifier(32)
                tt.append(ClassDef(
                    name=p,
                    bases=[
                        Name(prev, Load())
                    ],
                    keywords=[],
                    body=[Ellipsis()],
                    decorator_list=[]
                ))
                prev = p
            tt.append(ClassDef(
                name=x["final_name"],
                bases=[
                    Name(prev, Load())
                ],
                keywords=[],
                body=[Ellipsis()],
                decorator_list=[]
            ))
            tta.append(tt)
        tt = []
        for x in itertools.zip_longest(*tta):
            tt += filter(lambda v: v is not None, x)
        aa.body = [*tt, *aa.body]
        return aa
