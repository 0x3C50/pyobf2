import os
from _ast import AST

from . import Transformer, compute_import_path
from ..cfg import ConfigValue
from ..renamer import MappingGenerator, MappingApplicator, OtherFileMappingApplicator


class MemberRenamer(Transformer):
    def __init__(self):
        super().__init__(
            "renamer",
            "Renames all members (methods, classes, fields, args)",
            rename_format=ConfigValue(
                "Format for the renamer. Will be queried using eval().\n"
                "'counter' is a variable incrementing with each name generated\n"
                "'kind' is either 'method', 'var', 'arg' or 'class', depending on the current element\n"
                "'get_counter(name)' is a method that increments a counter behind 'name', and returns its current "
                "value\n"
                "'random_identifier(length)' returns a valid python identifier, according to "
                "https://docs.python.org/3/reference/lexical_analysis.html#identifiers",
                "f'{kind}{get_counter(kind)}'",
            ),
        )

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        generator = MappingGenerator(self.config["rename_format"].value)
        generator.visit(ast)
        # generator.print_mappings()
        MappingApplicator(generator.mappings).visit(ast)
        if all_asts is not None:
            mappings1 = {}
            this_file_name = os.path.abspath(current_file_name)
            for x in generator.mappings.keys():
                n = x.split(".")
                if n[0] == "":
                    mappings1[n[1]] = generator.mappings[x]
            for i in range(len(all_asts)):
                that_ast = all_asts[i]
                if that_ast == ast:
                    continue
                that_file_name = os.path.abspath(all_file_names[i])
                required_import = compute_import_path(that_file_name, this_file_name)
                root_name = list(all_file_names)
                root_name.sort(key=lambda x: len(x.split(os.path.sep)))
                OtherFileMappingApplicator(
                    mappings1,
                    [required_import, compute_import_path(root_name[0], this_file_name)],
                    list(mappings1.keys()),
                ).visit(that_ast)
        return ast
