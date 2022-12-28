import ast
import opcode
import random
from ast import *

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
    def _str_literal_helper(
            self, string, *, quote_types=_ALL_QUOTES, escape_special_whitespace=False
    ):
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
        print(f"opcode {current} ({opcode.opname[current]}), {cache} cache slots")
        cache_bytes = cache * 2
        for off in range(cache_bytes):
            bc[reader + off] = random.randint(0, 255)
        reader += cache_bytes


def ast_import_full(name: str) -> Call:
    return Call(
        func=Name('__import__', Load()),
        args=[Constant(name)],
        keywords=[]
    )


def ast_import_from(name: str, *names) -> ImportFrom:
    return ImportFrom(
        module=name,
        names=[alias(name=x) for x in names],
        level=0
    )
