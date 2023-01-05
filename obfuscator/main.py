import ast
import math
import os.path
import time as tme
from ast import *

import colorama
import rich.tree
import tomlkit
from rich.console import Console
from rich.progress import track
from tomlkit import *

import constructDynamicCodeObjTransformer
import encodeStringsTransformer
import fstrToFormatTransformer
import intObfuscatorTransformer
import memberRenamerTransformer
import removeTypeHintsTransformer
import replaceAttribsTransformer
import varAccessToGLDictTransformer
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
    transitive=ConfigValue("Resolves local imports from the target file and obfuscates them aswell", True),
    overwrite_output_forcefully=ConfigValue("Skips the existance check of the output file. This WILL nuke the output file if it already exists",
                                            False)
)

all_config_segments = [general_settings]

all_transformers = [
    x()
    for x in [
        removeTypeHintsTransformer.RemoveTypeHints,
        fstrToFormatTransformer.FstringsToFormatSequence,
        intObfuscatorTransformer.IntObfuscator,
        encodeStringsTransformer.EncodeStrings,
        memberRenamerTransformer.MemberRenamer,
        replaceAttribsTransformer.ReplaceAttribs,
        constructDynamicCodeObjTransformer.ConstructDynamicCodeObject,
        varAccessToGLDictTransformer.Collector,
    ]
]

for x in all_transformers:
    x.console = console
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


def transform_source(c_ast: AST, source_file_name: str) -> AST:
    transformers_to_run = list(
        filter(lambda x: x.config["enabled"].value, all_transformers)
    )
    if len(transformers_to_run) == 0:
        console.log("Nothing to do, bailing out", style="red")
        exit(0)
    for t in track(transformers_to_run, description="Obfuscating...", console=console):
        c_ast = t.transform(c_ast, source_file_name, None, None)  # just this one
        console.log(f"Executed transformer {t.name}", style="green")
    fix_missing_locations(c_ast)
    return c_ast


def do_obf(task: rich.progress.TaskID, progress: rich.progress.Progress, current_file_path, all_asts, the_index, other_file_paths):
    try:
        transformers_to_run = list(
            filter(lambda x: x.config["enabled"].value, all_transformers)
        )
        completed = -1
        progress.update(task, total=len(transformers_to_run) + 1)  # transform+1
        progress.start_task(task)
        progress.update(task, completed=(completed := completed + 1), description="Running transformers")
        if len(transformers_to_run) == 0:
            console.log("Nothing to do, bailing out", style="red")
            exit(0)
        for t in transformers_to_run:
            progress.update(task, completed=(completed := completed + 1), description="Transformer " + t.name)
            all_asts[the_index] = t.transform(all_asts[the_index], current_file_path, all_asts, other_file_paths)
            tme.sleep(5)
        all_asts[the_index] = fix_missing_locations(all_asts[the_index])
        progress.update(task, completed=(completed := completed + 1), description="Done")
        return all_asts[the_index]
    except Exception:
        console.print_exception(show_locals=True)


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
    if len(deptree) == 0:
        console.log("Transitive run with no dependencies, aborting\nSet transitive to false in your config.toml if you have only one file",
                    style="red")
        exit(1)
    common_prefix_l = len(os.path.commonpath(list(map(lambda x: os.path.dirname(x)+"/", deptree.keys()))))+1
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
    common_prefix_l = len(os.path.commonpath(list(map(lambda x: os.path.dirname(x)+"/", all_files))))+1
    progress = rich.progress.Progress(
        rich.progress.TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        rich.progress.BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        rich.progress.TextColumn("[#4f4f4f]{task.description:>32}", justify="right"),
        console=console
    )
    all_asts = []
    for x in all_files:
        with open(x, "r", encoding="utf8") as f:
            inp_source = f.read()
        all_asts.append(ast.parse(inp_source))
    all_tasks = []
    for file in all_files:
        task1 = progress.add_task("Waiting", start=False, filename=file[common_prefix_l:])
        all_tasks.append(task1)

    transformers_to_run = list(
        filter(lambda x: x.config["enabled"].value, all_transformers)
    )
    if len(transformers_to_run) == 0:
        console.log("Nothing to do, bailing out", style="red")
        exit(0)
    task_labels = [*["Transformer "+x.name for x in transformers_to_run], "Done"]
    with progress:
        for trafo in transformers_to_run:
            for index in range(len(all_files)):
                task = all_tasks[index]
                file = all_files[index]
                progress.update(task, total=len(task_labels))
                comp_i = progress._tasks[task].completed
                if comp_i == 0:
                    progress.start_task(task)
                progress.update(task, total=len(task_labels), completed=comp_i+1, description=task_labels[math.floor(comp_i)])
                all_asts[index] = fix_missing_locations(trafo.transform(all_asts[index], file, all_asts, all_files))

        for index in range(len(all_files)):
            task = all_tasks[index]
            progress.update(task, total=len(task_labels))
            comp_i = progress._tasks[task].completed
            progress.update(task, total=len(task_labels), completed=comp_i+1, description=task_labels[math.floor(comp_i)])



    console.log("Writing")
    for i in range(len(all_files)):
        file = all_files[i]
        out_ast = all_asts[i]
        full_path = os.path.join(output_file, file[common_prefix_l:])
        dname = os.path.dirname(full_path)
        if not os.path.exists(dname):
            os.makedirs(dname)
        try:
            src = NonEscapingUnparser().visit(out_ast)
        except Exception as e:
            console.print_exception(max_frames=3)
            if str(e) == "Unable to avoid backslash in f-string expression part":
                console.log(
                    "[red]An error occurred with re-parsing the python AST into source code.[/red] AST was not able to escape ASCII characters in an "
                    "F-String expression. Please check if you have any ASCII characters in F-Strings, and escape them manually. "
                )
                console.log("Current file:", full_path)
            exit(1)
            return

        with open(full_path, "w", encoding="utf8") as f:
            f.write(src)
            f.flush()
    console.log("Done", style="green")


def recurse_tree_inner(orig, m, common_prefix_len: int, tree: rich.tree.Tree):
    for x in m:
        el = tree.add(x[common_prefix_len:])
        if x in orig:
            recurse_tree_inner(orig, orig[x], common_prefix_len, el)


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
    if os.path.exists(output_file) and not general_settings["overwrite_output_forcefully"].value:
        console.log(
            "The output path at",
            output_file,
            "already exists, choosing alternative...",
            style="yellow",
        )
        base1 = os.path.basename(output_file)
        base1 = ".".join(base1.split(".")[0:-1]) if base1.endswith(".py") else base1
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
    compiled_ast = transform_source(compiled_ast, os.path.abspath(input_file))
    console.log("Re-structuring source...", style="#4f4f4f")
    try:
        src = NonEscapingUnparser().visit(compiled_ast)
    except Exception as e:
        console.print_exception(max_frames=3)
        if str(e) == "Unable to avoid backslash in f-string expression part":
            console.log(
                "[red]An error occurred with re-parsing the python AST into source code.[/red] AST was not able to escape ASCII characters in an "
                "F-String expression. Please check if you have any ASCII characters in F-Strings, and escape them manually. "
            )
        exit(1)
        return
    console.log("Writing...", style="#4f4f4f")
    with open(output_file, "w", encoding="utf8") as f:
        f.write(src)
    console.log("Done", style="green")
