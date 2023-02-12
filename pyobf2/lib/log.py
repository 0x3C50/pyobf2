import ast
from ast import *


def warn(source_file: str, source_ast: AST, warning: str):
    unparsed = ast.unparse(source_ast)
    intro = f"warn({source_file}:{source_ast.lineno}.{source_ast.col_offset})"
    prefix = "... "
    additional_whitespaces = len(intro) - len(prefix)
    log_msg = f"{intro}: {warning}"

    log_msg += "\n" + "\n".join(map(lambda x: " " * (additional_whitespaces + 1) + prefix + x, unparsed.split("\n")))

    print(log_msg)


def warn_simple(source: str, warning: str):
    print(f"warn({source}): {warning}")
