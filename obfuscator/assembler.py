import math
import opcode
from types import CodeType
from typing import Any


class _insn:
    def __init__(self, opcode: int, arg: int):
        self.opc = opcode
        self.arg = arg

    def to_bc_seq(self):
        bl = self.arg.bit_length()
        if bl > 4 * 8:
            raise ValueError(f"Arg {self.arg} is too big to pack into 4 bytes")
        arg_bytes = self.arg.to_bytes(math.ceil(bl / 8), "big", signed=False)
        if len(arg_bytes) == 0:
            arg_bytes = b"\x00"
        constructed = []
        if len(arg_bytes) > 1:
            for x in arg_bytes[:-1]:
                constructed += [0x90, x]  # EXTENDED_ARG x
        constructed += [self.opc, arg_bytes[len(arg_bytes) - 1]]
        cache = opcode._inline_cache_entries[self.opc]
        constructed += [0x00] * cache * 2
        return bytes(constructed)


def _encode_varint(value) -> bytes:
    a = value
    v = 0
    while a > 0:  # reverse bytes of a
        v |= a & 63
        v = v << 6
        a = a >> 6
    b = []
    while v > 0:
        val = v & 0b11_11_11  # 6 bits at once
        v = v >> 6  # shift 6 bits right
        if v > 0:
            val = val | 0b1_00_00_00  # add cont bit, we have a next byte to encode
        b.append(val)  # add byte to the result
    if len(b) == 0:  # nothing encoded
        b = [0x00]
    return bytes(b)


class Assembler:
    """
    An assembler for python bytecode
    """

    class TryCatchBuilder:
        """
        Context manager for a try block
        """

        def __init__(self, assembler, depth: int, lasti: bool):
            self.assembler = assembler
            self.start = -1
            self.end = -1
            self.target = -1
            self.depth = depth
            self.li = lasti

        def __enter__(self):
            self.start = self.assembler.current_bytecode_index()

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.start == -1:
                raise ValueError("__exit__ called before __enter__ (?)")
            self.end = self.assembler.current_bytecode_index()
            self.target = self.end  # weird but it does work, assume handler is directly after
            self.assembler.add_exception_table_span(self.start, self.end, self.target, self.depth, self.li)

    class _exc_table_entry:
        def __init__(self, from_i: int, to_i: int, target: int, depth: int, is_lasti: bool):
            if from_i % 2 != 0 or to_i % 2 != 0 or target % 2 != 0:
                raise ValueError("Unexpected odd number in either from_i, to_i or target")
            self.from_i = from_i
            self.len = to_i - self.from_i
            self.target = target
            self.depth = depth
            self.lasti = is_lasti

        def to_bc_seq(self):
            bc = b""
            bc += _encode_varint(
                self.from_i // 2
            )  # since bytecode indexes are whole numbers, we can safely divide by 2 to "compress" the varints
            bc += _encode_varint(self.len // 2)
            bc += _encode_varint(self.target // 2)
            bc += _encode_varint(self.depth << 1 | int(self.lasti))
            return bc

    def __init__(self, arg_names: list[str] = None):
        """
        Creates a new assembler
        :param arg_names: The argument names, if this assembler describes a method. None otherwise (and by default).
        """
        if arg_names is None:
            arg_names = list()
        self._insns = []
        self._consts = []
        self._names = []
        self._varnames = []
        self._exctable = []
        self._argnames = arg_names
        for n in arg_names:
            self.locals_create_or_get(n)

    def current_bytecode_index(self):
        """
        Returns the length of the currently built bytecode sequence (aka the index of the next instruction)
        :return: the length of the currently built bytecode sequence
        """
        return len(self._build_co_str())

    def insn(self, name: str, arg: int = 0):
        """
        Adds an insn by name. See `opcode.py` for all opcodes.
        :param name: The name of the insn to add
        :param arg: The argument. 0 by default
        :raises ValueError: if the name of the insn couldn't be resolved
        :return: Nothing
        """
        name = name.upper()
        if name not in opcode.opmap:
            raise ValueError("Unknown insn " + name)
        opm = opcode.opmap[name]
        self.add_insn(opm, arg)

    def try_block(self, depth, lasti):
        """
        Creates a "try" block, and assumes that the handler follows immediately afterwards. Use in a `with` statement.
        :param depth: The depth of the handler
        :param lasti: Unknown
        :return: A try-catch builder
        """
        return self.TryCatchBuilder(self, depth, lasti)

    def add_insn(self, opcode: int, arg: int = 0):
        """
        Adds an insn by opcode. Use insn(str, int) for an easier-to-use implementation.
        :param opcode: The opcode (0-255)
        :param arg: The argument. 0 by default
        :return: Nothing
        :raises ValueError: If either the opcode is not within 0-255, or arg is below 0
        """
        if opcode > 255 or opcode < 0:
            raise ValueError("Opcode not in range 0-255")
        if arg < 0:
            raise ValueError("arg out of bounds")
        insn = _insn(opcode, arg)
        self._insns.append(insn)

    def add_exception_table_span(self, from_index: int, to_index: int, target_index: int, depth: int, is_lasti: bool):
        """
        Adds an exception table entry manually. Not recommended to be used instead of try_block(), but can be used if the exception handler does not
        follow immediately after the throwing block.
        :param from_index: The starting byte index
        :param to_index: The ending byte index (exclusive)
        :param target_index: The index of the start of the handler
        :param depth: The depth of the handler
        :param is_lasti: Unknown
        :return: Nothing
        """
        self._exctable.append(self._exc_table_entry(from_index, to_index, target_index, depth, is_lasti))

    def _build_co_str(self) -> bytes:
        b = b""
        for x in self._insns:
            b += x.to_bc_seq()
        return b

    def _build_exc_table(self) -> bytes:
        b = b""
        for x in self._exctable:
            b += x.to_bc_seq()
        return b

    def pack_code_object(self) -> CodeType:
        """
        Compiles this assembler into a code object
        :return: The constructed code object. Can be marshalled using marshal.dumps, or executed using eval() or exec()
        """
        return CodeType(
            len(self._argnames),
            0,
            0,
            len(self._varnames),
            30,
            0,
            self._build_co_str(),
            tuple(self._consts),
            tuple(self._names),
            tuple(self._varnames),
            "<asm>",
            "",
            "",
            0,
            b"",
            self._build_exc_table(),
        )

    def consts_create_or_get(self, value: Any) -> int:
        """
        Creates or gets an entry from the constant pool
        :param value: The desired value
        :return: An existing or new index to the constant pool, where the specified value is
        """
        if value in self._consts:
            return self._consts.index(value)
        else:
            i = len(self._consts)
            self._consts.append(value)
            return i

    def names_create_or_get(self, value: str) -> int:
        """
        Creates or gets an entry from the name pool
        :param value: The desired value
        :return: An existing or new index to the name pool, where the specified value is
        """
        if value in self._names:
            return self._names.index(value)
        else:
            i = len(self._names)
            self._names.append(value)
            return i

    def locals_create_or_get(self, value: str) -> int:
        """
        Creates or gets an entry from the local pool
        :param value: The desired value
        :return: An existing or new index to the local pool, where the specified value is
        """
        if value in self._varnames:
            return self._varnames.index(value)
        else:
            i = len(self._varnames)
            self._varnames.append(value)
            return i
