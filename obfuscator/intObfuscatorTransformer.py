import math
import random
from _ast import Constant, Call, Attribute, Name, Load, Lambda, arguments, arg, BinOp, Sub, Add, Starred, List, Mult, keyword, AST
from ast import NodeTransformer
from typing import Any

from transformers import Transformer


class IntObfuscator(Transformer, NodeTransformer):
    def __init__(self):
        super().__init__("intObfuscator", "Obscures int constants")

    def visit_Constant(self, node: Constant) -> Any:
        s = self.generic_visit(node)
        if type(node.value) == int:
            ic: int = node.value
            is_signed = ic < 0  # signed bit needs to be set only if ic is negative
            rdx = math.ceil((ic.bit_length() + (1 if is_signed else 0)) / 8)  # add said sign bit if the int is signed
            int_bytes = ic.to_bytes(rdx, "little", signed=is_signed)
            off = random.randint(255 + rdx, 999)  # need to keep at least rdx indexes free
            encoded = "".join([format(off - (x + i), "03d") for (x, i) in zip(int_bytes, range(len(int_bytes)))])
            return Call(  # int.from_bytes(..., "little", signed=is_signed)
                func=Attribute(Name('int', Load()), 'from_bytes', Load()),  # int.from_bytes
                args=[
                    Call(  # map(lambda O: 255-int(O), map(''.join, zip(*[iter(encoded)]*3)))
                        func=Name('map', Load()),
                        args=[
                            Lambda(  # lambda O, i: ...
                                args=arguments(
                                    posonlyargs=[],
                                    args=[
                                        arg('O'),
                                        arg('i')
                                    ],
                                    kwonlyargs=[],
                                    kw_defaults=[],
                                    defaults=[]),
                                body=BinOp(  # off - int(O)
                                    left=Constant(value=off),
                                    op=Sub(),
                                    right=BinOp(
                                        left=Call(  # int(O)
                                            func=Name('int', Load()),
                                            args=[
                                                Name('O', Load())],
                                            keywords=[]),
                                        op=Add(),
                                        right=Name('i', Load())
                                    )
                                )),
                            Call(
                                func=Name('map', Load()),
                                args=[
                                    Attribute(
                                        value=Constant(value=''),
                                        attr='join',
                                        ctx=Load()),
                                    Call(
                                        func=Name('zip', Load()),
                                        args=[
                                            Starred(
                                                value=BinOp(
                                                    left=List(
                                                        elts=[
                                                            Call(
                                                                func=Name('iter', Load()),
                                                                args=[
                                                                    Constant(encoded)
                                                                ],
                                                                keywords=[])],
                                                        ctx=Load()),
                                                    op=Mult(),
                                                    right=Constant(value=3)),
                                                ctx=Load())],
                                        keywords=[])],
                                keywords=[]),
                            Call(
                                func=Name('range', Load()),  # range(math.floor(len(encoded)/3))
                                args=[
                                    Constant(math.floor(len(encoded) / 3))
                                ],
                                keywords=[]
                            )
                        ],
                        keywords=[]),
                    Constant(value='little')],
                keywords=[
                    keyword(
                        arg='signed',
                        value=Constant(is_signed)
                    )
                ])
        return s

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        return self.visit(ast)
