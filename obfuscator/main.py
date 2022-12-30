import ast
import os.path
from ast import *
from concurrent.futures import ThreadPoolExecutor

import colorama
import rich.tree
import tomlkit
from rich.console import Console
from rich.progress import track
from tomlkit import *
import time as tme

import transformers as transf
from cfg import *
from util import NonEscapingUnparser, get_dependency_tree

colorama.init()

console = Console()

config_file = "config.toml"

general_settings = ConfigSegment(
    "general",
    "General settings for the obfuscator",
    input_file=ConfigValue("The input for the obfuscator", "input.py"),
    output_file=ConfigValue("The output for the obfuscator", "output.py"),
    transitive=ConfigValue("Resolves local imports from the target file and obfuscates them aswell", True)
)

all_config_segments = [general_settings]

all_transformers = [
    x()
    for x in [
        transf.FstringsToFormatSequence,
        transf.IntObfuscator,
        transf.EncodeStrings,
        transf.MemberRenamer,
        transf.ReplaceAttribs,
        transf.Collector,
        transf.ConstructDynamicCodeObject,
    ]
]

for x in all_transformers:
    all_config_segments.append(x.config)


def populate_with(doc: TOMLDocument, seg: ConfigSegment):
    tbl = table()
    tbl.add(comment(seg.desc))
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
        console.log(
            "Configuration file does not exist, creating example...", style="red"
        )
        example_cfg = generate_example_config()
        st = dumps(example_cfg)
        with open(config_file, "w") as f:
            f.write(st)
        console.log("Created, view at", os.path.abspath("config.toml"), style="green")
        exit(1)
    with open(config_file, "r") as f:
        cfg_file_contents = f.read()
    cfg_file = loads(cfg_file_contents)
    try:
        parse_config(cfg_file)
    except Exception:
        console.print_exception(suppress=[tomlkit])
        console.log(
            "The configuration [red]failed to parse[/red]. This is probably due to your configuration being outdated. "
            "Please [red]remove[/red] your current configuration file and regenerate it."
        )
        exit(1)
    if general_settings["transitive"].value:
        go_transitive()
    else:
        go_single()


def transform_source(c_ast: AST, log_indent: int = 0) -> AST:
    transformers_to_run = list(
        filter(lambda x: x.config["enabled"].value, all_transformers)
    )
    if len(transformers_to_run) == 0:
        console.log(" " * log_indent + "Nothing to do, bailing out", style="red")
        exit(0)
    for t in track(transformers_to_run, description="Obfuscating...", console=console):
        c_ast = t.transform(c_ast)
        console.log(" " * log_indent + f"Executed transformer {t.name}", style="green")
    fix_missing_locations(c_ast)
    return c_ast


def do_obf(task: rich.progress.TaskID, progress: rich.progress.Progress, input_file, output_file_path):
    transformers_to_run = list(
        filter(lambda x: x.config["enabled"].value, all_transformers)
    )
    progress.update(task, total=2 + len(transformers_to_run) + 2)  # load, parse, transform+1, unparse
    progress.start_task(task)
    progress.update(task, completed=0, description="Loading source")
    tme.sleep(1)
    with open(input_file, "r", encoding="utf8") as f:
        inp_source = f.read()
    progress.update(task, completed=1, description="Parsing source")
    tme.sleep(1)
    compiled_ast: AST = ast.parse(inp_source)
    progress.update(task, completed=2, description="Running transformers")
    tme.sleep(1)
    if len(transformers_to_run) == 0:
        console.log("Nothing to do, bailing out", style="red")
        exit(0)
    p = 1
    for t in transformers_to_run:
        progress.update(task, completed=2 + p, description="Transformer " + t.name)
        tme.sleep(1)
        compiled_ast = t.transform(compiled_ast)
        p += 1
    fix_missing_locations(compiled_ast)
    progress.update(task, completed=3 + len(transformers_to_run), description="Writing")
    tme.sleep(1)
    try:
        src = NonEscapingUnparser().visit(compiled_ast)
    except Exception as e:
        console.print_exception(max_frames=3)
        if str(e) == "Unable to avoid backslash in f-string expression part":
            console.log(
                "[red]An error occurred with re-parsing the python AST into source code.[/red] AST was not "
                "able to escape ASCII"
                "characters in an F-String expression. Please check if you have any "
                "ASCII characters in F-Strings, and escape them manually."
            )
        exit(1)
        return

    with open(output_file_path, "w", encoding="utf8") as f:
        f.write(src)
    progress.update(task, completed=3 + len(transformers_to_run) + 1, description="Done")
    tme.sleep(1)
    # progress.stop_task(task)


def go_transitive():
    input_file = general_settings["input_file"].value
    output_file = general_settings["output_file"].value
    if not os.path.exists(input_file) or not os.path.isfile(input_file):
        console.log(
            "The input file at",
            os.path.abspath(input_file),
            "does not exist",
            style="red",
        )
        exit(1)
    if not os.path.exists(output_file):
        os.makedirs(output_file)
    elif not os.path.isdir(output_file):
        console.log("Transitive obfuscation requires the output to be a directory", style="red")
        exit(1)
    console.log("Parsing inheritance tree...", style="#4f4f4f")
    deptree = get_dependency_tree(input_file)
    common_prefix_l = len(os.path.commonprefix(list(deptree.keys())))
    tree = rich.tree.Tree(
        os.path.abspath(input_file)[common_prefix_l:],
        style="green"
    )
    recurse_tree_inner(deptree, deptree[os.path.abspath(input_file)], common_prefix_l, tree)
    console.log(tree)
    all_files = []
    for x in deptree.keys():
        if x not in all_files:
            all_files.append(x)
        for y in deptree[x]:
            if y not in all_files:
                all_files.append(y)
    common_prefix_l = len(os.path.commonprefix(all_files))
    progress = rich.progress.Progress(
        rich.progress.TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        rich.progress.BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        rich.progress.TextColumn("[#4f4f4f]{task.description:>40}", justify="right"),
        console=console
    )
    with progress:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for file in all_files:
                task = progress.add_task("Waiting", start=False, filename=file[common_prefix_l:])
                full_path = os.path.join(output_file, file[common_prefix_l:])
                dname = os.path.dirname(full_path)
                if not os.path.exists(dname):
                    os.makedirs(dname)
                pool.submit(do_obf, task, progress, file, full_path)
    console.log("Done", style="green")


def recurse_tree_inner(orig, m, common_prefix_len: int, tree: rich.tree.Tree):
    for x in m:
        el = tree.add(x[common_prefix_len:])
        if x in orig:
            recurse_tree_inner(orig, orig[x], common_prefix_len, el)


# def recurse_tree(m, common_prefix_len: int, tree: rich.tree.Tree):
#     for x in m.keys():
#         el = tree.add(x[common_prefix_len:])
#         recurse_tree_inner(m, m[x], common_prefix_len, el)


def go_single():
    input_file = general_settings["input_file"].value
    output_file = general_settings["output_file"].value
    if not os.path.exists(input_file) or not os.path.isfile(input_file):
        console.log(
            "The input file at",
            os.path.abspath(input_file),
            "does not exist",
            style="red",
        )
        exit(1)
    if os.path.exists(output_file) and os.path.isdir(
            output_file
    ):  # output "file" is a dir
        base = os.path.basename(input_file)  # so append the input file name to it
        output_file = os.path.join(output_file, base)
    if os.path.exists(output_file):
        console.log(
            "The output path at",
            output_file,
            "already exists, choosing alternative...",
            style="yellow",
        )
        base1 = os.path.basename(output_file)
        base1 = ".".join(base1.split(".")[0:-1])
        attempts = 0
        while os.path.exists(output_file):
            output_file = os.path.join(
                os.path.dirname(output_file), f"{base1}_{attempts}.py"
            )
            attempts += 1
        console.log("Found one:", output_file, style="green")
    with open(input_file, "r", encoding="utf8") as f:
        inp_source = f.read()
    console.log("Parsing AST...", style="#4f4f4f")
    compiled_ast: AST = ast.parse(inp_source)
    compiled_ast = transform_source(compiled_ast)
    console.log("Re-structuring source...", style="#4f4f4f")
    try:
        src = NonEscapingUnparser().visit(compiled_ast)
    except Exception as e:
        console.print_exception(max_frames=3)
        if str(e) == "Unable to avoid backslash in f-string expression part":
            console.log(
                "[red]An error occurred with re-parsing the python AST into source code.[/red] AST was not "
                "able to escape ASCII"
                "characters in an F-String expression. Please check if you have any "
                "ASCII characters in F-Strings, and escape them manually."
            )
        exit(1)
        return
    console.log("Writing...", style="#4f4f4f")
    with open(output_file, "w", encoding="utf8") as f:
        f.write(src)
    console.log("Done", style="green")
