import ast
from ast import *
from typing import Any


class MappingGenerator(NodeVisitor):
    """
    A generator for mappings
    """

    def remap_name_if_needed(self, old):
        """
        Remaps the given name to a new one, if the mappings contain a name for it
        :param old: The old name
        :return:    The remapped name or old if no mapping was found
        """
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

    def counter_shit(self, name: str):
        if name not in self.counters:
            self.counters[name] = 0
            return 0
        self.counters[name] += 1
        return self.counters[name]

    def mapping_name(self, for_type: str):
        fmt = self.fmt
        generated_name = eval(fmt, {
            "counter": self.counter_shit("cnt"),
            "kind": for_type,
            "get_counter": self.counter_shit
        })
        if type(generated_name) != str:
            generated_name = str(generated_name)
        return generated_name

    def __init__(self, fmt):
        self.fmt = fmt
        self.counters = {}
        self.mappings = {}
        self.location_stack = []

    def visit_Global(self, node: Global) -> Any:
        for i in range(len(node.names)):
            x = node.names[i]
            remapped_name = self.remap_name_if_needed(x)
            if remapped_name is not x:  # we have a mapping for this one? good
                self.put_name_if_absent(x, remapped_name)
                node.names[i] = remapped_name
            else:
                # this global statemenet defines a var at module level
                # this is straight up evil coding practise but some fucked up people do it so it has to be supported
                remapped_name = self.mapping_name("var")
                self.put_name_at_module_level(x, remapped_name)
                self.put_name_if_absent(x, remapped_name)
                node.names[i] = remapped_name

        self.generic_visit(node)

    def visit_Import(self, node: Import) -> Any:
        for x in node.names:
            if "." in x.name:  # BIG TODO
                continue
            if x.asname is None:
                x.asname = x.name
            self.put_name_if_absent(x.asname, self.mapping_name("var"))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ImportFrom) -> Any:
        for x in node.names:
            self.put_name_if_absent(x.asname, self.mapping_name("var"))
        self.generic_visit(node)

    def print_mappings(self):
        """
        Prints all mappings
        :return: Nothing
        """
        for x in self.mappings.keys():
            print(f"{x} to {self.mappings[x]}")

    def put_name_at_module_level(self, old, new):
        full = f"var..{old}"
        if full not in self.mappings:
            self.mappings[full] = new

    def put_name_if_absent(self, old, new):
        """
        Puts a new name if it doesn't already exist
        :param old:  The old name
        :param new:  The new name
        :return: Nothing
        """
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
        if not any(x.startswith("cl_") for x in self.location_stack):
            self.put_name_if_absent(name, self.mapping_name("method"))
        self.start_visit("mt_" + name)
        self.generic_visit(node)
        self.end_visit()

    def visit_AsyncFunctionDef(self, node: AsyncFunctionDef) -> Any:
        name = node.name
        self.put_name_if_absent(name, self.mapping_name("method"))
        self.start_visit("mt_" + name)
        self.generic_visit(node)
        self.end_visit()

    def visit_arg(self, node: arg) -> Any:
        name = node.arg
        if name != "self":  # maybe dont remap this one
            nn = self.mapping_name("arg")
            self.put_name_if_absent(name, nn)
        # self.generic_visit(node)

    def visit_Lambda(self, node: Lambda) -> Any:
        self.start_visit("mt_<lambda>")
        self.generic_visit(node)
        self.end_visit()

    def visit_ClassDef(self, node: ClassDef) -> Any:
        self.put_name_if_absent(node.name, self.mapping_name("class"))
        self.start_visit("cl_" + node.name)
        self.generic_visit(node)
        self.end_visit()

    def visit_Expr(self, node: Expr) -> Any:
        self.start_visit("sp_expr")
        self.generic_visit(node)
        self.end_visit()

    def visit_Name(self, node: Name) -> Any:
        if isinstance(node.ctx, Store):
            if node.id != "self":
                self.put_name_if_absent(node.id, self.mapping_name("var"))
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
        node.name = self.remap_name_if_needed(node.name)
        self.generic_visit(node)
        self.end_visit()

    def visit_Name(self, node: Name) -> Any:
        node.id = self.remap_name_if_needed(node.id)
        self.generic_visit(node)
