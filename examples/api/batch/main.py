import ast
import os

import pyobf2.lib as obf


def walk(dir: str) -> list:
    """
    This function recursively traverses the directory 'dir' and returns a generator that yields the file paths of all files that end with ".py"
    """
    for root, dirs, files in os.walk(dir):
        for file in files:
            if file.endswith(".py"):
                yield os.path.join(root, file)


def main() -> None:
    """
    The main function of the script. It performs the following steps:
    1. Defines the input and output directories
    2. Enables renamer obfuscation in the pyobf2 library
    3. Reads the content of all python files in the input directory
    4. Parses the content of each file into an AST (Abstract Syntax Tree)
    5. Passes the ASTs and their corresponding file paths to the pyobf2 library's obfuscation function
    6. Writes the obfuscated ASTs to the output directory, preserving the original file structure
    """

    in_dir = os.path.join(os.path.dirname(__file__), "input")
    out_dir = os.path.join(os.path.dirname(__file__), "output")

    obf.set_config_dict({"renamer.enabled": True})

    in_files = {x: open(x, "r", encoding="utf-8").read() for x in walk(in_dir)}
    in_asts = {x: ast.parse(y) for x, y in in_files.items()}

    for _ in obf.do_obfuscation_batch_ast(list(in_asts.values()), list(in_asts.keys())):
        pass

    for x, y in in_asts.items():
        out_file = os.path.join(out_dir, os.path.relpath(x, in_dir))
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(ast.unparse(y))


if __name__ == "__main__":
    main()
