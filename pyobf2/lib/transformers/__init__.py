import ast
import os.path
import pathlib
import random
from ast import *

from ..cfg import ConfigSegment, ConfigValue
from ..renamer import MappingGenerator, MappingApplicator


class Transformer(object):
    def __init__(self, name: str, desc: str, default_enabled: bool = False, **add_config: ConfigValue):
        self.name = name
        self.config = ConfigSegment(
            self.name, desc, enabled=ConfigValue("Enables this transformer", default_enabled), **add_config
        )

    def transform_output(self, output_location: pathlib.Path, all_files: list[pathlib.Path]) -> list[pathlib.Path]:
        return all_files

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        return ast


def compute_import_path(from_path: str, to_path: str):
    common_prefix = len(os.path.commonpath([os.path.dirname(from_path), os.path.dirname(to_path)]))
    from_path = from_path[common_prefix + 1 :].split(os.path.sep)
    to_path = to_path[common_prefix + 1 :].split(os.path.sep)

    full_imp = ""
    while len(from_path) > 1:
        full_imp += ".."
        from_path.pop(0)
    if to_path[len(to_path) - 1] == "__init__.py":
        to_path.pop()

    for x in to_path:
        full_imp += x + "."
    full_imp = full_imp[:-1]
    if full_imp.endswith(".py"):
        full_imp = full_imp[:-3]
    if len(full_imp) == 0:
        full_imp = "."
    return full_imp


def rnd_name():
    return "".join(random.choices(["l", "I", "M", "N"], k=32))


def collect_fstring_consts(node: JoinedStr) -> str:
    s = ""
    for x in node.values:
        if isinstance(x, Constant):
            s += str(x.value)
        else:
            raise ValueError("Non-constant format specs are not supported")
    return s


def optimize_ast(ast1: AST):
    generator = MappingGenerator('f"{kind[0]}{get_counter(kind)}"')
    generator.visit(ast1)
    MappingApplicator(generator.mappings).visit(ast1)
    for x in ast.walk(ast1):
        if isinstance(x, (AsyncFunctionDef, FunctionDef, ClassDef, Module)):
            clear_docstring(x)
    return ast1


def clear_docstring(node):
    if not isinstance(node, (AsyncFunctionDef, FunctionDef, ClassDef, Module)):
        raise TypeError("%r can't have docstrings" % node.__class__.__name__)
    if not (node.body and isinstance(node.body[0], Expr)):
        return None
    nnode = node.body[0].value
    if isinstance(nnode, Str) or (isinstance(nnode, Constant) and isinstance(nnode.value, str)):
        del node.body[0]


def ast_import_from(name: str, *names) -> ImportFrom:
    return ImportFrom(module=name, names=[alias(name=x) for x in names], level=0)


def ast_import_full(name: str) -> Call:
    return Call(func=Name("__import__", Load()), args=[Constant(name)], keywords=[])
