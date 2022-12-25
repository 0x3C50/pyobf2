from ast import *
from typing import Any

mapped_name_count = 0


def random_mapping_name() -> str:
    global mapped_name_count
    mapped_name_count += 1
    return "_" * mapped_name_count


class MappingGenerator(NodeVisitor):
    def remap_name_if_needed(self, old):
        sorted_names = list(self.mappings.keys())
        # Sort by longest (most specific) path first
        sorted_names.sort(key=lambda v: grade_name_order(v.split(".")[1]), reverse=True)
        for x in sorted_names:
            s_loc = x.split(".")[1]
            location_split = s_loc.split("|")
            if len(location_split) == 1 and location_split[0] == '':
                location_split = []
            loc_matches = True
            if len(self.location_stack) >= len(location_split):
                for i in range(len(location_split)):
                    current_loc_pos = self.location_stack[i]
                    existing_loc_pos = location_split[i]
                    if current_loc_pos != existing_loc_pos:
                        loc_matches = False
                        break
            else:
                loc_matches = False
            if loc_matches and x.split(".")[2] == old:
                return self.mappings[x]
        return old

    def __init__(self, methods, variables, args):
        self.config = {
            "methods": methods,
            "vars": variables,
            "args": args
        }
        self.mappings = {}
        self.location_stack = []

    def visit_Global(self, node: Global) -> Any:
        for i in range(len(node.names)):
            x = node.names[i]
            remapped_name = self.remap_name_if_needed(x)
            if remapped_name is not x:  # we have a mapping for this one? holy shit
                self.put_name_if_absent(x, remapped_name)
                node.names[i] = remapped_name
        self.generic_visit(node)

    def visit_Import(self, node: Import) -> Any:
        for x in node.names:
            if "." in x.name:  # BIG TODO
                continue
            if x.asname is None:
                x.asname = x.name
            self.put_name_if_absent(x.asname, random_mapping_name())
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ImportFrom) -> Any:
        for x in node.names:
            self.put_name_if_absent(x.asname, random_mapping_name())
        self.generic_visit(node)

    def print_mappings(self):
        for x in self.mappings.keys():
            print(f"{x} to {self.mappings[x]}")

    def put_name_if_absent(self, old, new):
        loc = "|".join(self.location_stack)
        full = f"var.{loc}.{old}"
        if full not in self.mappings:
            self.mappings[full] = new

    def start_visit(self, name):
        self.location_stack.append(name)

    def end_visit(self):
        self.location_stack.pop()

    def visit_FunctionDef(self, node: FunctionDef) -> Any:
        name = node.name
        # methods need to be enabled and none of the location elements need to be of a class
        if self.config["methods"] and not any(x.startswith("cl_") for x in self.location_stack):
            self.put_name_if_absent(name, random_mapping_name())
        self.start_visit("mt_" + name)
        self.generic_visit(node)
        self.end_visit()

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> Any:
        name = node.name
        if self.config["methods"]:
            self.put_name_if_absent(name, random_mapping_name())
        self.start_visit("mt_" + name)
        self.generic_visit(node)
        self.end_visit()

    def visit_arg(self, node: arg) -> Any:
        name = node.arg
        if name != "self" and self.config["args"]:  # maybe dont remap this one
            nn = random_mapping_name()
            self.put_name_if_absent(name, nn)
        # self.generic_visit(node)

    def visit_Lambda(self, node: Lambda) -> Any:
        self.start_visit("mt_<lambda>")
        self.generic_visit(node)
        self.end_visit()

    def visit_ClassDef(self, node: ClassDef) -> Any:
        self.start_visit("cl_" + node.name)
        self.generic_visit(node)
        self.end_visit()

    def visit_Expr(self, node: Expr) -> Any:
        self.start_visit("sp_expr")
        self.generic_visit(node)
        self.end_visit()

    def visit_Name(self, node: Name) -> Any:
        if isinstance(node.ctx, Store):
            if node.id != "self" and self.config["vars"]:
                self.put_name_if_absent(node.id, random_mapping_name())
        self.generic_visit(node)


def grade_name_order(name: str):
    if len(name) == 0:
        return 0
    return len(name.split("|")) + 1


class MappingApplicator(NodeVisitor):
    def __init__(self, mappings):
        self.mappings = mappings
        self.location_stack = []

    def visit_Import(self, node: Import) -> Any:
        for x in node.names:
            x.asname = self.remap_name_if_needed(x.asname)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ImportFrom) -> Any:
        for x in node.names:
            x.asname = self.remap_name_if_needed(x.asname)
        self.generic_visit(node)

    def remap_name_if_needed(self, old):
        sorted_names = list(self.mappings.keys())
        # Sort by longest (most specific) path first
        sorted_names.sort(key=lambda v: grade_name_order(v.split(".")[1]), reverse=True)
        for x in sorted_names:
            s_loc = x.split(".")[1]
            location_split = s_loc.split("|")
            if len(location_split) == 1 and location_split[0] == '':
                location_split = []
            loc_matches = True
            if len(self.location_stack) >= len(location_split):
                for i in range(len(location_split)):
                    current_loc_pos = self.location_stack[i]
                    existing_loc_pos = location_split[i]
                    if current_loc_pos != existing_loc_pos:
                        loc_matches = False
                        break
            else:
                loc_matches = False
            if loc_matches and x.split(".")[2] == old:
                return self.mappings[x]
        return old

    def start_visit(self, name):
        self.location_stack.append(name)

    def end_visit(self):
        self.location_stack.pop()

    def visit_FunctionDef(self, node: FunctionDef) -> Any:
        name = node.name
        node.name = self.remap_name_if_needed(node.name)
        self.start_visit("mt_" + name)
        self.generic_visit(node)
        self.end_visit()

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> Any:
        name = node.name
        node.name = self.remap_name_if_needed(name)
        self.start_visit("mt_" + name)
        self.generic_visit(node)
        self.end_visit()

    def visit_arg(self, node: arg) -> Any:
        node.arg = self.remap_name_if_needed(node.arg)
        self.generic_visit(node)

    def visit_Expr(self, node: Expr) -> Any:
        self.start_visit("sp_expr")
        self.generic_visit(node)
        self.end_visit()

    def visit_Lambda(self, node: Lambda) -> Any:
        self.start_visit("mt_<lambda>")
        self.generic_visit(node)
        self.end_visit()

    def visit_ClassDef(self, node: ClassDef) -> Any:
        self.start_visit("cl_" + node.name)
        self.generic_visit(node)
        self.end_visit()

    def visit_Name(self, node: Name) -> Any:
        node.id = self.remap_name_if_needed(node.id)
        self.generic_visit(node)
