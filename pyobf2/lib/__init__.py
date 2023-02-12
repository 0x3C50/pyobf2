import os.path
import pathlib
from ast import *

from .cfg import *
from .transformers.collector import Collector
from .transformers.compileFinalFiles import CompileFinalFiles
from .transformers.constructDynamicCodeObjTransformer import ConstructDynamicCodeObject
from .transformers.encodeStringsTransformer import EncodeStrings
from .transformers.floatsToComplex import FloatsToComplex
from .transformers.fstrToFormatTransformer import FstringsToFormatSequence
from .transformers.intObfuscatorTransformer import IntObfuscator
from .transformers.logicTransformer import LogicTransformer
from .transformers.memberRenamerTransformer import MemberRenamer
from .transformers.packPyz import PackInPyz
from .transformers.removeTypeHintsTransformer import RemoveTypeHints
from .transformers.replaceAttribsTransformer import ReplaceAttribs
from .transformers.unicodeNameTransformer import UnicodeNameTransformer

config_file = "config.toml"

all_config_segments = []

all_transformers = [
    x()
    for x in [
        LogicTransformer,
        RemoveTypeHints,
        FstringsToFormatSequence,
        EncodeStrings,
        FloatsToComplex,
        IntObfuscator,
        MemberRenamer,
        ReplaceAttribs,
        ConstructDynamicCodeObject,
        Collector,
        UnicodeNameTransformer,
        CompileFinalFiles,
        PackInPyz,
    ]
]

for x in all_transformers:
    all_config_segments.append(x.config)


def get_current_config() -> dict[str, str]:
    """
    Returns an example configuration as a dict
    :return: An example configuration, as dict
    """
    d = dict()
    for x in all_config_segments:
        for v in x.keys():
            d[f"{x.name}.{v}"] = x[v].value
    return d


def set_configuration_key(k: str, v: Any):
    """
    Sets a configuration key to the specified value
    :param k: The configuration key (parent.child)
    :param v: The configuration value
    :return: Nothing
    """
    for x in all_config_segments:
        for vt in x.keys():
            if f"{x.name}.{vt}" == k:
                if type(x[vt].value) != type(v):
                    raise ValueError(f"Type {type(v)} not assignable to type {type(x[vt].value)}")
                x[vt].value = v
                return
    raise ValueError("Key " + k + " not found")


def set_config_dict(cfg: dict[str, Any]):
    """
    Sets the configuration to the provided dict. Each element is extracted and used in set_configuration_key
    :param cfg: key : value pairs
    :return: Nothing
    """
    for x in cfg.keys():
        set_configuration_key(x, cfg[x])


def do_obfuscation_batch_ast(source_asts: list[AST], source_file_names: list[str]):
    """
    Obfuscates a batch of files at once, which comes at the advantage of the transformers being aware of the other files
    as well. Useful when working across files with mappings (for example, when renaming).
    Will yield each step as
    {"file_index": <index of file being processed>, "transformer": <transformer instance currently running>}
    :param source_asts: The source asts
    :param source_file_names:
    The source file names, corresponding to source_asts. It is assumed that len(source_asts) = len(source_file_names).
    :return: Nothing
    """
    assert len(source_file_names) == len(source_asts)
    source_file_names = list(map(lambda p: p if os.path.isabs(p) else os.path.abspath(p), source_file_names))
    transformers_to_run = list(filter(lambda x: x.config["enabled"].value, all_transformers))
    for x in transformers_to_run:
        for i in range(len(source_asts)):
            s_ast = source_asts[i]
            s_fn = source_file_names[i]
            source_asts[i] = fix_missing_locations(x.transform(s_ast, s_fn, source_asts, source_file_names))
            yield {"file_index": i, "transformer": x}


def do_obfuscation_single_ast(source_ast: AST, source_file_name: str) -> AST:
    """
    Does obfuscation on a single AST. When obfuscating multiple ASTs that depend on each other, don't call this method
    on all of them separately. Use do_obfuscation_batch_ast, which can recognize import relations between them,
    and will consider them as well.
    :param source_ast: The source AST to transform
    :param source_file_name: The source file name
    :return: The transformed AST
    """
    transformers_to_run = list(filter(lambda x: x.config["enabled"].value, all_transformers))
    for x in transformers_to_run:
        source_ast = x.transform(source_ast, source_file_name, None, None)

    fix_missing_locations(source_ast)
    return source_ast


def do_post_run(output_location: pathlib.Path, output_files: list[pathlib.Path]) -> list[pathlib.Path]:
    """
    Transforms all output files
    :param output_location: The parent folder of the output files. Will be used to write any new files to
    :param output_files: All files to transform
    :return: The new output paths
    """
    transformers_to_run = list(filter(lambda x: x.config["enabled"].value, all_transformers))
    for x in transformers_to_run:
        output_files = x.transform_output(output_location, output_files)
    return output_files
