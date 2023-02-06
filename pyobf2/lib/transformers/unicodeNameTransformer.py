import random
from _ast import Name, AST
from ast import NodeVisitor
from typing import Any

from . import Transformer

import unicodedata


variations = [
    "MATHEMATICAL SANS-SERIF BOLD ITALIC",
    "MATHEMATICAL SANS-SERIF BOLD",
    "MATHEMATICAL SANS-SERIF ITALIC",
    "MATHEMATICAL SANS-SERIF FRAKTUR",
]


def convert_char(ch: str) -> str:
    if len(ch) != 1:
        return ch
    iscap = ch.isupper()
    vs = []
    for x in variations:
        try:
            vs.append(unicodedata.lookup(f"{x} {'CAPITAL' if iscap else 'SMALL'} {ch}"))
        except KeyError:
            pass
    if len(vs) == 0:
        return ch
    return random.choice(vs)


class UnicodeNameTransformer(Transformer, NodeVisitor):
    def __init__(self):
        super().__init__(
            "unicodeTransformer",
            "Converts names to equally valid, but weird looking unicode names\n"
            "Does not work with compileFinalFiles, has to be source code",
        )

    def transform(self, ast: AST, current_file_name: str, all_asts, all_file_names) -> AST:
        self.visit(ast)
        return ast

    def visit_Name(self, node: Name) -> Any:
        node.id = "".join([convert_char(x) for x in node.id])
