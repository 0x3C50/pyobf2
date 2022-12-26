import ast
import os.path
from ast import *

from tomlkit import *

import transformers as transf
from cfg import *
from util import NonEscapingUnparser

config_file = "config.toml"

general_settings = ConfigSegment(
    "general",
    "General settings for the obfuscator",
    input_file=ConfigValue("The input for the obfuscator", "input.py"),
    output_file=ConfigValue("The output for the obfuscator", "output.py")
)

transformers = ConfigSegment(
    "transformers",
    "Transformer options",
    collect_method_calls=ConfigValue("Collects all method calls into a list and references them via eval()", True),
    remap_members=ConfigValue("Remaps all members (methods*, arguments, variables). Mostly stable, but can get funny "
                              "at times. * Methods in classes are not remapped due to inheritance issues", True),
    collect_consts=ConfigValue("Collects all constant values into an array and replaces them with access to the array",
                               True),
    change_ints=ConfigValue("Obscures int constants", True),
    encode_strings=ConfigValue("Encodes strings in base64 followed by level 9 zlib compression", True),
    simplify_strings=ConfigValue("Splits strings up into chars, then adds them back together at runtime. Useful with "
                                 "collect_consts, at a cost of higher file size", True),
    remove_direct_attrib_set=ConfigValue("Removes direct attribute setting and replaces it with setattr()", True),
    wrap_in_code_obj=ConfigValue("Wraps the entire program in a dynamically created code object at runtime. It is "
                                 "recommended to do another pass after this, since it exposes string constants and "
                                 "similar", True),
    wrap_in_code_obj_and_encrypt=ConfigValue("In addition to wrapping the entire program in dynamically created code "
                                             "objects, also encrypts the bytecode. Only works if wrap_in_code_obj is "
                                             "enabled", True)
)

all_config_segments = [general_settings, transformers]

all_transformers = [
    (transf.EncodeStrings, "encode_strings"),
    (transf.StringSplitter, "simplify_strings"),
    (transf.IntObfuscator, "change_ints"),
    (transf.MemberRenamer, "remap_members"),
    (transf.ReplaceAttribs, "remove_direct_attrib_set"),
    (transf.Collector, "collect_method_calls"),
    (transf.ConstructDynamicCodeObject, "wrap_in_code_obj")
]


def populate_with(doc: TOMLDocument, seg: ConfigSegment):
    tbl = table()
    tbl.add(comment(seg.desc))
    for k in seg.keys():
        v: ConfigValue = seg[k]
        tbl.add(comment(v.desc))
        tbl.add(k, v.value)
    doc.add(seg.name, tbl)


def generate_example_config() -> TOMLDocument:
    doc = document()
    # Header
    doc.add(comment("Obfuscator configuration file"))
    doc.add(nl())

    # Values
    populate_with(doc, general_settings)
    populate_with(doc, transformers)
    return doc


def parse_config(cfg: TOMLDocument):
    for x in all_config_segments:
        config_segment = cfg[x.name]
        for y in x:
            v: ConfigValue = x[y]
            v.value = config_segment[y]


def main():
    if not os.path.exists(config_file):
        print("Configuration path does not exist, creating configuration for you...")
        example_cfg = generate_example_config()
        st = dumps(example_cfg)
        with open(config_file, "w") as f:
            f.write(st)
        print("Created, exiting")
        exit(1)
    with open(config_file, "r") as f:
        cfg_file_contents = f.read()
    cfg_file = loads(cfg_file_contents)
    parse_config(cfg_file)
    go()


def recursive_attrib_resolve(inp: Attribute):
    t = ""
    if isinstance(inp.value, Attribute):
        t += recursive_attrib_resolve(inp.value)
    elif isinstance(inp.value, Name):
        t += inp.value.id
    t += '.'
    t += inp.attr
    return t


def transform_source(c_ast: AST) -> AST:
    for t in all_transformers:
        if transformers[t[1]].value:
            c_ast = t[0](transformers).transform(c_ast)
            print(f"Executed transformer {t[0].__name__}")
    fix_missing_locations(c_ast)
    return c_ast


def go():
    input_file = general_settings["input_file"].value
    output_file = general_settings["output_file"].value
    with open(input_file, "r") as f:
        inp_source = f.read()
    compiled_ast: AST = ast.parse(inp_source)
    compiled_ast = transform_source(compiled_ast)
    try:
        src = NonEscapingUnparser().visit(compiled_ast)
    except ValueError as e:
        if str(e) == "Unable to avoid backslash in f-string expression part":
            print("An error occured with re-parsing the python AST into source code. AST was not able to escape ASCII "
                  "characters in an F-String expression. Please check if you have any "
                  "ASCII characters in F-Strings, and escape them manually.")
            print("Full error: ", e)
            return
        raise
    with open(output_file, "w") as f:
        f.write(src)


if __name__ == '__main__':
    main()
