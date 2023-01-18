import marshal
import os.path
import pathlib
import struct
import sys
from types import CodeType

from . import Transformer
from ..util import strip_lnotab


def _pack_uint32(val):
    """Convert integer to 32-bit little-endian bytes"""
    return struct.pack("<I", val)


def _code_to_bytecode(code, compile_time=0, source_size=0):
    """
    Serialise the passed code object (PyCodeObject*) to bytecode as a .pyc file
    The args compile_time and source_size are inconsequential metadata in the .pyc file.
    """

    # Get the magic number for the running Python version
    from importlib.util import MAGIC_NUMBER

    magic_number = MAGIC_NUMBER

    # Add the magic number that indicates the version of Python the bytecode is for
    #
    # The .pyc may not decompile if this four-byte value is wrong. Either hardcode the
    # value for the target version (eg. b'\x33\x0D\x0D\x0A' instead of MAGIC_NUMBER)
    data = bytearray(magic_number)

    # Handle extra 32-bit field in header from Python 3.7 onwards
    # See: https://www.python.org/dev/peps/pep-0552
    if sys.version_info >= (3, 7):
        # Blank bit field value to indicate traditional pyc header
        data.extend(_pack_uint32(0))

    data.extend(_pack_uint32(int(compile_time)))

    # Handle extra 32-bit field for source size from Python 3.2 onwards
    # See: https://www.python.org/dev/peps/pep-3147/
    if sys.version_info >= (3, 2):
        data.extend(_pack_uint32(source_size))

    data.extend(code)

    return data


def do_compile(p_file: pathlib.Path):
    root_file = os.path.splitext(p_file)[0]
    with open(p_file, "rb") as f, open(root_file + ".pyc", "wb") as out:
        src = f.read()
        compiled: CodeType = compile(src, "", "exec", optimize=2)
        compiled = strip_lnotab(compiled)
        dumped = marshal.dumps(compiled)
        bc_content = _code_to_bytecode(dumped)
        out.write(bc_content)
    p_file.unlink()


class CompileFinalFiles(Transformer):
    def __init__(self):
        super().__init__("compileFinalFiles", "Compiles all output files to .pyc")

    def transform_output(self, output_location: pathlib.Path, all_files: list[pathlib.Path]):
        all_f_copy = all_files[:]
        all_f_copy = list(
            map(lambda x: pathlib.Path(os.path.splitext(x)[0] + ".pyc") if x.is_file() else x, all_f_copy)
        )
        for x in all_files:
            if x.is_file():
                do_compile(x)
        return all_f_copy
