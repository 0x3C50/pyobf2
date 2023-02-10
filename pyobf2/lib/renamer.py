import random
import string
from ast import *
from typing import Any


def random_identifier(length: int):
    if length <= 0:
        raise ValueError("length expected to be <= 1, got " + str(length))
    valid_chars = string.ascii_letters + "_"
    built = ""
    built += random.choice(valid_chars)
    for i in range(length - 1):
        built += random.choice(valid_chars + string.digits)
    return built


class MappingGenerator(NodeVisitor):
    """
    A generator for mappings
    """

    def remap_name_if_needed(self, old):
        sorted_names = list(self.mappings.keys())
        # Sort by longest (most specific) path first
        sorted_names.sort(key=lambda v: grade_name_order(v.split(".")[0]), reverse=True)
        for x in sorted_names:
            s_loc = x.split(".")[0]
            location_split = s_loc.split("|")
            if len(location_split) == 1 and location_split[0] == "":
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
            if loc_matches and x.split(".")[1] == old:
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
        generated_name = eval(
            fmt,
            {
                "counter": self.counter_shit("cnt"),
                "kind": for_type,
                "get_counter": self.counter_shit,
                "random_identifier": random_identifier,
            },
        )
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
                # this global statement defines a var at module level
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

    def print_mappings(self):
        """
        Prints all mappings
        :return: Nothing
        """
        for x in self.mappings.keys():
            print(f"{x} to {self.mappings[x]}")

    def put_name_at_module_level(self, old, new):
        full = f".{old}"
        if full not in self.mappings:
            self.mappings[full] = new

    def put_name_if_absent(self, old, new):
        """
        Puts a new name if it doesn't already exist
        :param old:  The old name
        :param new:  The new name
        :return: Nothing
        """
        if old is None:
            raise ValueError("none")
        loc = "|".join(self.location_stack)
        full = f"{loc}.{old}"
        if full not in self.mappings:
            self.mappings[full] = new

    def start_visit(self, name):
        self.location_stack.append(name)

    def end_visit(self):
        return self.location_stack.pop()

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
        nn = self.mapping_name("arg")
        self.put_name_if_absent(name, nn)
        old_stack = self.end_visit()
        self.put_name_if_absent(old_stack + "_arg_" + name, nn)
        self.start_visit(old_stack)

    def visit_Lambda(self, node: Lambda) -> Any:
        self.start_visit("mt_<lambda>")
        self.generic_visit(node)
        self.end_visit()

    def visit_ClassDef(self, node: ClassDef) -> Any:
        if not any(x.startswith("cl_") for x in self.location_stack):
            self.put_name_if_absent(node.name, self.mapping_name("class"))
        self.start_visit("cl_" + node.name)
        self.generic_visit(node)
        self.end_visit()

    def visit_ListComp(self, node: ListComp) -> Any:
        self.start_visit("sp_lc")
        self.generic_visit(node)
        self.end_visit()

    def visit_Name(self, node: Name) -> Any:
        if isinstance(node.ctx, Store):
            if node.id != "self":
                if len(self.location_stack) == 0 or not self.location_stack[len(self.location_stack) - 1].startswith(
                    "cl_"
                ):
                    self.put_name_if_absent(node.id, self.mapping_name("var"))
        self.generic_visit(node)


def grade_name_order(name: str):
    if len(name) == 0:
        return 0
    return len(name.split("|")) + 1


class OtherFileMappingApplicator(NodeVisitor):
    def __init__(self, mappings: dict[str, str], owning_module_names: list[str], all_els_in_other_file: list[str]):
        self.mappings = mappings
        self.all_els = all_els_in_other_file
        self.owning_modules = owning_module_names
        self.names_containing_module = []

    def _resolve_attr(self, node: Attribute) -> str | None:
        first_part = (
            self._resolve_attr(node.value)
            if isinstance(node.value, Attribute)
            else (node.value.id if isinstance(node.value, Name) else None)
        )
        second_part = node.attr
        if first_part is None:
            return None
        return first_part + "." + second_part

    def _get_attr_parts(self, node: Attribute) -> list[str] | None:
        parts = []
        s = node.value
        if isinstance(s, Attribute):
            s = self._get_attr_parts(s)
            if s is None:
                return None
            parts.extend(s)
            parts.append(node.attr)
        elif isinstance(s, Name):
            parts.append(s.id)
            parts.append(node.attr)
        else:
            return None
        return parts

    def _map_name(self, m: str) -> str:
        return self.mappings[m] if m in self.mappings else m

    def visit_ImportFrom(self, node: ImportFrom) -> Any:
        resolved_mod = node.module
        if resolved_mod is None:
            resolved_mod = ""
        resolved_mod = "." * node.level + resolved_mod
        if self._import_matches(resolved_mod):
            if len(node.names) == 1 and node.names[0].name == "*":  # why the fuck
                node.names = [alias(name=self._map_name(x), asname=x) for x in self.all_els]
            for x in node.names:
                if x.asname is None:
                    x.asname = x.name
                x.name = self._map_name(x.name)

    def _import_matches(self, import_name: str) -> bool:
        return import_name in self.owning_modules

    def visit_Import(self, node: Import) -> Any:
        for x in node.names:
            if self._import_matches(x.name):
                target_name = x.asname if x.asname is not None else x.name
                if target_name not in self.names_containing_module:
                    self.names_containing_module.append(target_name)
        self.generic_visit(node)

    def visit_Attribute(self, node: Attribute) -> Any:
        attr_parts = self._get_attr_parts(node)
        if attr_parts is None:
            return
        matched_name = []
        for n in self.names_containing_module:
            attr_res = n.split(".")
            matches_verdict = True
            if len(attr_res) < len(attr_parts):
                for i in range(len(attr_res)):
                    if attr_res[i] != attr_parts[i]:
                        matches_verdict = False
            if matches_verdict:
                matched_name = attr_res
                attr_parts = attr_parts[len(attr_res) :]
                break

        if len(matched_name) > 0 and len(attr_parts) > 0:
            remapped_names = [*matched_name, self._map_name(attr_parts[0])]
            remapped_names.extend(attr_parts[1:])
            built_attribute = Attribute(value=Name(remapped_names[0], Load()), attr=remapped_names[1], ctx=Load())
            if len(remapped_names) > 2:
                for x in remapped_names[2:]:
                    built_attribute = Attribute(value=built_attribute, attr=x, ctx=Load())
            node.value = built_attribute.value
            node.attr = built_attribute.attr

    def visit_Assign(self, node: Assign) -> Any:
        """
        jesus fucking christ
        """
        if (
            isinstance(node.value, Call)
            and isinstance(node.value.func, Name)
            and node.value.func.id == "__import__"
            and len(node.value.args) > 0
            and isinstance(node.value.args[0], Constant)
            and node.value.args[0].value in self.owning_modules
        ):  # aka __import__("our module name")
            for x in node.targets:
                name = self._resolve_attr(x) if isinstance(x, Attribute) else (x.id if isinstance(x, Name) else None)
                if name is None:
                    continue
                if name not in self.names_containing_module:
                    self.names_containing_module.append(name)
        elif (isinstance(node.value, Attribute) or isinstance(node.value, Name)) and (
            self._resolve_attr(node.value)
            if isinstance(node.value, Attribute)
            else (node.value.id if isinstance(node.value, Name) else None)
        ) in self.names_containing_module:  # aka something = something_that_we_know_is_our_module
            for x in node.targets:
                name2 = self._resolve_attr(x) if isinstance(x, Attribute) else (x.id if isinstance(x, Name) else None)
                if name2 is None:
                    continue
                if name2 not in self.names_containing_module:
                    self.names_containing_module.append(name2)
        else:
            for (
                x
            ) in (
                node.targets
            ):  # we know these are being assigned something else, so remove them from the names we know are the module
                name2 = self._resolve_attr(x) if isinstance(x, Attribute) else (x.id if isinstance(x, Name) else None)
                if name2 is None:
                    continue
                if name2 in self.names_containing_module:
                    self.names_containing_module.remove(name2)
        self.generic_visit(node)


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

    def remap_name_if_needed(self, old, loc_stack=None):
        if loc_stack is None:
            loc_stack = self.location_stack
        sorted_names = list(self.mappings.keys())
        # Sort by longest (most specific) path first
        sorted_names.sort(key=lambda v: grade_name_order(v.split(".")[0]), reverse=True)
        for x in sorted_names:
            s_loc = x.split(".")[0]
            location_split = s_loc.split("|")
            if len(location_split) == 1 and location_split[0] == "":
                location_split = []
            loc_matches = True
            if len(loc_stack) >= len(location_split):
                for i in range(len(location_split)):
                    current_loc_pos = loc_stack[i]
                    existing_loc_pos = location_split[i]
                    if current_loc_pos != existing_loc_pos:
                        loc_matches = False
                        break
            else:
                loc_matches = False
            if loc_matches and x.split(".")[1] == old:
                return self.mappings[x]
        return old

    def start_visit(self, name):
        self.location_stack.append(name)

    def end_visit(self):
        return self.location_stack.pop()

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

    def visit_ListComp(self, node: ListComp) -> Any:
        self.start_visit("sp_lc")
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

    def visit_Call(self, node: Call) -> Any:
        if isinstance(node.func, Name):
            # self.start_visit("mt_" + node.func.id)
            # print(self.location_stack)
            # prev = self.end_visit() if len(self.location_stack) > 0 else None
            for k in node.keywords:
                search_str = "mt_" + node.func.id + "_arg_" + k.arg
                # print(self.location_stack, search_str)
                res = self.remap_name_if_needed(search_str)
                if res == search_str:
                    res = k.arg
                k.arg = res
            # if prev is not None:
            #     self.start_visit(prev)
            # self.end_visit()
        self.generic_visit(node)

    def visit_Name(self, node: Name) -> Any:
        node.id = self.remap_name_if_needed(node.id)
        self.generic_visit(node)
