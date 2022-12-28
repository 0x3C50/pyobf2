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

all_config_segments = [general_settings]

all_transformers = [x() for x in [transf.FstringsToFormatSequence, transf.IntObfuscator, transf.EncodeStrings, transf.MemberRenamer,
                                  transf.ReplaceAttribs, transf.Collector, transf.ConstructDynamicCodeObject]]

for x in all_transformers:
    all_config_segments.append(x.config)

# all_transformers = [
#     (transf.FstringsToFormatSequence, "convert_fstrings_to_format"),
#     (transf.IntObfuscator, "change_ints"),
#     (transf.EncodeStrings, "encode_strings"),
#     (transf.MemberRenamer, "remap_members"),
#     (transf.ReplaceAttribs, "remove_direct_attrib_set"),
#     (transf.Collector, "collect_method_calls"),
#     (transf.ConstructDynamicCodeObject, "wrap_in_code_obj")
# ]


def populate_with(doc: TOMLDocument, seg: ConfigSegment):
    tbl = table()
    doc.add(comment(seg.desc))
    for k in seg.keys():
        v: ConfigValue = seg[k]
        for x in [comment(y.strip()) for y in v.desc.split("\n")]:
            tbl.add(x)
        tbl.add(k, v.value)
    doc.add(seg.name, tbl)


def generate_example_config() -> TOMLDocument:
    doc = document()
    # Header
    doc.add(comment("Obfuscator configuration file"))
    doc.add(nl())

    # Values
    for x in all_config_segments:
        populate_with(doc, x)
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
        if t.config["enabled"].value:
            c_ast = t.transform(c_ast)
            print(f"Executed transformer {t.name}")
    fix_missing_locations(c_ast)
    return c_ast


def go():
    input_file = general_settings["input_file"].value
    output_file = general_settings["output_file"].value
    with open(input_file, "r", encoding="utf8") as f:
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
