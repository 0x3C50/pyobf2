import ast

import colorama
from rich.console import Console
from rich.panel import Panel

import obfuscator as obf

colorama.init()
cons = Console()

default_config = {**obf.get_current_config()}


def single_example():
    obf.set_config_dict({"intObfuscator.enabled": True})
    cons.log(obf.get_current_config())
    the_ast = ast.parse("print(1234)")
    cons.log("before", ast.unparse(the_ast))
    real_ast = obf.do_obfuscation_single_ast(the_ast, "<str>")
    cons.log("after", ast.unparse(real_ast))


def mult_file_example():
    obf.set_config_dict({"renamer.enabled": True})
    cons.log(obf.get_current_config())
    asts = [
        {
            "f": "fileA.py",
            "src": """
def abc():
    print("bye")

def ddd():
    print("hello")

ddd()
        """,
        },
        {
            "f": "fileB.py",
            "src": """
import fileA as fa
fa.abc()
some_deref = fa
some_deref.abc()
            """,
        },
    ]
    the_asts = [ast.parse(x["src"]) for x in asts]
    the_fnames = [x["f"] for x in asts]
    for i in range(len(the_asts)):
        x = the_asts[i]
        y = the_fnames[i]
        cons.log(Panel(ast.unparse(x), title="Before", subtitle=y, expand=False))
    for x in obf.do_obfuscation_batch_ast(the_asts, the_fnames):
        # The for loop is mandatory to consume the events. without it, this wouldn't run
        cons.log("Step", x)
    for i in range(len(the_asts)):
        x = the_asts[i]
        y = the_fnames[i]
        cons.log(Panel(ast.unparse(x), title="After", subtitle=y, expand=False))


if __name__ == "__main__":
    cons.log("-- Single example --")
    single_example()
    obf.set_config_dict(default_config)
    cons.log("-- Multiple file example --")
    mult_file_example()
