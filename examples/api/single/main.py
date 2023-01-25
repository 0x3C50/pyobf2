import ast
import os

import pyobf2.lib as obf


def main() -> None:
    """
    The main function of the script. It performs the following steps:
    1. Defines the input and output file paths
    2. Reads the contents of the input file
    3. Parses the input file contents into an AST (Abstract Syntax Tree)
    4. Enables integer obfuscation in the pyobf2 library
    5. Passes the AST and the input file path to the pyobf2 library's single file obfuscation function
    6. Writes the obfuscated AST to the output file
    """
    in_file = os.path.join(os.path.dirname(__file__), "input", "file.py")
    out_file = os.path.join(os.path.dirname(__file__), "output", "file.py")

    with open(in_file, "r", encoding="utf-8") as f:
        in_file_contents = f.read()

    main_ast = ast.parse(in_file_contents)

    obf.set_config_dict({"intObfuscator.enabled": True})
    obf.do_obfuscation_single_ast(main_ast, in_file)

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(ast.unparse(main_ast))


if __name__ == "__main__":
    main()
