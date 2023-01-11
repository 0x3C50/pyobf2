import ast
import dataclasses
import importlib.util
import opcode
import os.path
import random
from ast import *
from types import CodeType

_SINGLE_QUOTES = ("'", '"')
_MULTI_QUOTES = ('"""', "'''")
_ALL_QUOTES = (*_SINGLE_QUOTES, *_MULTI_QUOTES)


class NonEscapingUnparser(getattr(ast, "_Unparser")):
    """
    This class only exists because the default implementation of the unparser escapes unicode characters,
    which breaks f-strings in some cases.
    This is a very hacky fix, but it's the only one I was able to make so far.
    """

    # noinspection PyMethodMayBeStatic
    def _str_literal_helper(self, string, *, quote_types=_ALL_QUOTES, escape_special_whitespace=False):
        """Helper for writing string literals, minimizing escapes.
        Returns the tuple (string literal to write, possible quote types).
        """

        def escape_char(c):
            # \n and \t are non-printable, but we only escape them if
            # escape_special_whitespace is True
            if not escape_special_whitespace and c in "\n\t":
                return c
            # Always escape backslashes and other non-printable characters
            if c == "\\":
                return c.encode("unicode_escape").decode("ascii")
            return c

        escaped_string = "".join(map(escape_char, string))
        possible_quotes = quote_types
        if "\n" in escaped_string:
            possible_quotes = [q for q in possible_quotes if q in _MULTI_QUOTES]
        possible_quotes = [q for q in possible_quotes if q not in escaped_string]
        if not possible_quotes:
            # If there aren't any possible_quotes, fallback to using repr
            # on the original string. Try to use a quote from quote_types,
            # e.g., so that we use triple quotes for docstrings.
            string = repr(string)
            quote = next((q for q in quote_types if string[0] in q), string[0])
            return string[1:-1], [quote]
        if escaped_string:
            # Sort so that we prefer '''"''' over """\""""
            possible_quotes.sort(key=lambda q: q[0] == escaped_string[-1])
            # If we're using triple quotes and we'd need to escape a final
            # quote, escape it
            if possible_quotes[0][0] == escaped_string[-1]:
                assert len(possible_quotes[0]) == 3
                escaped_string = escaped_string[:-1] + "\\" + escaped_string[-1]
        return escaped_string, possible_quotes


def randomize_cache(bc: list[int]):
    """
    Randomizes empty "cache" slots after instructions. Assume the following bytecode:

    116 1  ; LG 1 "print"

    0 0 0 0 0 0 0 0 0 0 ; CACHE

    100 3  ; LC 3 "abc"

    166 1  ; PRECALL N_ARG 1

    0 0    ; CACHE

    171 1  ; CALL N_ARG 1

    0 0 0 0 0 0 0 0 ; CACHE

    Some instructions have designated "cache" slots after them, which are filled by the python interpreter to cache
    information. These slots are not used otherwise, and can be anything, going into the interpreter. We set these slots
    to random bytes, to confuse the reader.
    :param bc: The bytecode
    :return: Nothing
    """
    reader = 0
    while reader < len(bc):
        current = bc[reader]
        reader += 2  # skip insn and arg, now at first cache
        cache = opcode._inline_cache_entries[current]
        cache_bytes = cache * 2
        for off in range(cache_bytes):
            bc[reader + off] = random.randint(0, 255)
        reader += cache_bytes


def get_file_from_import0(name: str, parent: str, path: list[str]):
    """
    debug version
    """
    print(parent, name, end="", flush=True)
    gfi = get_file_from_import(name, parent, path)
    print(" ->" + str(gfi))
    return gfi


@dataclasses.dataclass
class Imported:
    origin: str
    parent: str


def get_file_from_import(name: str, parent: str, path: list[str]):
    try:
        resname = importlib.util.resolve_name(name, parent)
        searchfor = resname.split(".")
        for p in path:
            current_path = p
            visited_path = []
            for x in searchfor:
                visited_path.append(x)
                current_path = os.path.join(current_path, x)
                if os.path.isdir(current_path):  # this segment points to a folder, continue
                    continue
                elif os.path.isfile(current_path + ".py"):  # we reached an end, the rest is speculation
                    return Imported(current_path + ".py", ".".join(visited_path[:-1]))
                else:  # this doesn't exist as a file
                    prevpath = os.path.dirname(current_path)  # this is, based on previous checks, a directory
                    if os.path.isfile(
                        os.path.join(prevpath, "__init__.py")
                    ):  # dir above has __init__, assume we're inside of it
                        return Imported(os.path.join(prevpath, "__init__.py"), ".".join(visited_path[:-1]))
                    return None  # dir above has no __init__, this one is bogus
            if os.path.isdir(current_path):  # this is a directory, do we have an __init__?
                if os.path.isfile(os.path.join(current_path, "__init__.py")):
                    # we do, but in this case, the module is its own parent
                    return Imported(os.path.join(current_path, "__init__.py"), ".".join(searchfor))
                else:
                    return None  # points to a folder, no __init__, cant import
        return None
    except Exception as e:
        raise e


path_blacklist = ["site-packages"]


def _walk_deptree(
    namespace: str,
    current_file: str,
    current_package: str,
    search_path: list[str],
    start: AST,
    lst: dict[str, list[str]],
):
    # print("-- FILE " + current_file + " --")
    if current_file in lst:
        return  # already visited
    for node in ast.walk(start):
        if isinstance(node, Import):
            discorvered_specs = list(
                filter(
                    lambda x: x is not None,
                    [get_file_from_import(x.name, current_package, search_path) for x in node.names],
                )
            )
            if current_file not in lst:
                lst[current_file] = []

            for x in discorvered_specs:
                p = x.origin
                if not p.startswith(namespace):
                    continue  # unwanted
                sep_split = p.split(os.path.sep)
                if any([x in path_blacklist for x in sep_split]):
                    continue  # also unwanted
                lst[current_file].append(p)
                with open(p, "r", encoding="utf8") as f:
                    _walk_deptree(namespace, p, x.parent, search_path, ast.parse(f.read()), lst)
        if isinstance(node, ImportFrom):
            modu = node.module
            if modu is None:
                modu = ""
            modu = "." * node.level + modu
            discovered_spec = get_file_from_import(modu, current_package, search_path)
            if discovered_spec is not None:
                discovered_file = discovered_spec.origin
                if not discovered_file.startswith(namespace):
                    continue  # unwanted
                sep_split = discovered_file.split(os.path.sep)
                if any([x in path_blacklist for x in sep_split]):
                    continue  # also unwanted
                if current_file not in lst:
                    lst[current_file] = []
                if discovered_file in lst[current_file]:
                    continue
                lst[current_file].append(discovered_file)
                with open(discovered_file, "r", encoding="utf8") as f:
                    _walk_deptree(
                        namespace, discovered_file, discovered_spec.parent, search_path, ast.parse(f.read()), lst
                    )


def get_dependency_tree(start: str):
    resolved_files = {}
    ns = os.path.dirname(os.path.abspath(start))
    path = [ns]
    with open(start, "r", encoding="utf8") as f:
        _walk_deptree(ns, os.path.abspath(start), "", path, ast.parse(f.read()), resolved_files)
    return resolved_files


def strip_lnotab(c: CodeType) -> CodeType:
    consts = []
    for item in c.co_consts:
        if isinstance(item, CodeType):
            item = strip_lnotab(item)
        consts.append(item)
    return c.replace(co_linetable=b"", co_consts=tuple(consts))
