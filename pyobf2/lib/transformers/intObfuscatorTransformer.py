import math
import random
from _ast import *
from ast import NodeTransformer
from typing import Any

from . import Transformer
from ..cfg import ConfigValue


def bt():
    return Constant(True)


def transform_complement(node: Constant):
    ic: int = node.value
    radix = random.randint(3, 16)
    ic = ic << radix
    oc = ~ic
    return BinOp(
        left=BinOp(
            left=BinOp(
                left=UnaryOp(
                    op=Invert(),
                    operand=UnaryOp(
                        op=Invert(),
                        operand=Constant(oc))),
                op=Add(),
                right=Constant(True)),
            op=Mult(),
            right=UnaryOp(
                op=Invert(),
                operand=Constant(False))),
        op=RShift(),
        right=Constant(radix)
    )


def transform_bits(node: Constant):
    ic: int = node.value
    if ic == 0:
        # True >> True, effectively 0
        return BinOp(left=bt(), op=RShift(), right=bt())
    if ic == 1:
        return BinOp(  # True << True >> True
            left=BinOp(left=bt(), op=LShift(), right=bt()), op=RShift(), right=bt()
        )
    bits = []
    while ic > 0:
        msk = ic & 0b1
        bits.append(msk)
        ic >>= 1
    conv_bits = zip(bits, range(len(bits)))
    conv_bits = list(filter(lambda x: x[0] == 1, list(conv_bits)))
    if len(conv_bits) == 0:
        conv_bits = [(0, 0)]
    sm = (
        BinOp(left=bt(), op=LShift(), right=Constant(conv_bits[0][1]))  # this will always be true
        if conv_bits[0][1] != 0
        else bt()
    )
    for x in conv_bits[1:]:
        sm = BinOp(
            left=sm,
            op=BitOr(),
            right=BinOp(left=bt(), op=LShift(), right=Constant(x[1])),  # this will always be true
        )
    return sm


def transform_decode(node: Constant):
    ic: int = node.value
    is_signed = ic < 0  # signed bit needs to be set only if ic is negative
    rdx = math.ceil((ic.bit_length() + (1 if is_signed else 0)) / 8)  # add said sign bit if the int is signed
    int_bytes = ic.to_bytes(rdx, "little", signed=is_signed)
    off = random.randint(255 + rdx, 999)  # need to keep at least rdx indexes free
    encoded = "".join([format(off - (x + i), "03d") for (x, i) in zip(int_bytes, range(len(int_bytes)))])
    return Call(  # int.from_bytes(..., "little", signed=is_signed)
        func=Attribute(Name("int", Load()), "from_bytes", Load()),  # int.from_bytes
        args=[
            Call(  # map(lambda O: 255-int(O), map(''.join, zip(*[iter(encoded)]*3)))
                func=Name("map", Load()),
                args=[
                    Lambda(  # lambda O, i: ...
                        args=arguments(
                            posonlyargs=[],
                            args=[arg("O"), arg("i")],
                            kwonlyargs=[],
                            kw_defaults=[],
                            defaults=[],
                        ),
                        body=BinOp(  # off - int(O)
                            left=Constant(value=off),
                            op=Sub(),
                            right=BinOp(
                                left=Call(func=Name("int", Load()), args=[Name("O", Load())], keywords=[]),  # int(O)
                                op=Add(),
                                right=Name("i", Load()),
                            ),
                        ),
                    ),
                    Call(
                        func=Name("map", Load()),
                        args=[
                            Attribute(value=Constant(value=""), attr="join", ctx=Load()),
                            Call(
                                func=Name("zip", Load()),
                                args=[
                                    Starred(
                                        value=BinOp(
                                            left=List(
                                                elts=[
                                                    Call(
                                                        func=Name("iter", Load()),
                                                        args=[Constant(encoded)],
                                                        keywords=[],
                                                    )
                                                ],
                                                ctx=Load(),
                                            ),
                                            op=Mult(),
                                            right=Constant(value=3),
                                        ),
                                        ctx=Load(),
                                    )
                                ],
                                keywords=[],
                            ),
                        ],
                        keywords=[],
                    ),
                    Call(
                        func=Name("range", Load()),  # range(math.floor(len(encoded)/3))
                        args=[Constant(math.floor(len(encoded) / 3))],
                        keywords=[],
                    ),
                ],
                keywords=[],
            ),
            Constant(value="little"),
        ],
        keywords=[keyword(arg="signed", value=Constant(is_signed))],
    )


class IntObfuscator(Transformer, NodeTransformer):
    def __init__(self):
        super().__init__(
            "intObfuscator",
            "Obscures int constants",
            mode=ConfigValue("How to obfuscate int constants\nPossible values: bits, complement, decode", "bits"),
        )

    def visit_Constant(self, node: Constant) -> Any:
        s = self.generic_visit(node)
        if type(node.value) == int:
            val = self.config["mode"].value
            if val == "decode":
                return transform_decode(node)
            elif val == "bits":
                tfb = transform_bits(node)
                return self.generic_visit(tfb)
            elif val == "complement":
                return transform_complement(node)
        return s

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        if self.config["mode"].value not in ("bits", "decode", "complement"):
            raise ValueError("Invalid mode " + self.config["mode"].value)
        return self.visit(ast)
