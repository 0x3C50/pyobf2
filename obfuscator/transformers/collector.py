import ast
import inspect
import marshal
import textwrap
import zlib
from _ast import Name, Load, Subscript, Constant, Assign, Store, Call, Attribute, AST, Module
from ast import NodeTransformer
from typing import Any

from . import Transformer, rnd_name, optimize_ast, ast_import_full
from ..assembler import Assembler


class Collector(Transformer, NodeTransformer):
    def __init__(self):
        self.vname = rnd_name()
        super().__init__("varCollector", "Converts var access to a hidden eval()")

    def visit_Name(self, node: Name) -> Any:
        if not type(node.ctx) == Load:  # we only want loads here, shit is getting too real
            return self.generic_visit(node)
        if node.id == "super":  # this will fuck with class context so lets skip this one
            return self.generic_visit(node)
        return Subscript(
            Name(self.vname, Load()), Constant(b"\x00" + zlib.compress(node.id.encode("utf8"), level=9)), Load()
        )

    @staticmethod
    def _create_co_obj():
        def getitem_method_real(_slf, item):
            """
            3 separate functions in one.
            If item starts with 0x00, item[1:] is decompressed with zlib and eval'd, the result is returned.
            If item starts with 0x01, item[1:] is decompressed with zlib and exec'd, the result is returned (usually None).
            Otherwise, item[1:] is decompressed with zlib and flipped, then returned
            :param _slf: Self
            :param item: Expression to evaluate
            :return: Resulting value. See docstring
            """
            import zlib as zlib1
            import codecs as codecs1
            import builtins as builtins1
            import sys as sys1
            from types import FrameType

            expr_to_eval = item
            codecs = codecs1.lookup("rot13")
            frame_above: FrameType = sys1._getframe(1)
            local_frames = {}
            depth = 1
            while True:
                try:
                    current_frame: FrameType = sys1._getframe(depth)
                    local_frames = {**current_frame.f_locals, **local_frames}
                    depth += 1
                    if not current_frame.f_code.co_name.startswith("<"):  # this is beyond our search range, cancel
                        break
                except ValueError:  # we hit the bottom
                    break
            frame = {**frame_above.f_globals, **local_frames}
            if expr_to_eval[0] == 0x00:
                # eval encoded with rot13
                return getattr(builtins1, codecs.decode("riny")[0])(zlib1.decompress(expr_to_eval[1:]), frame)
            elif expr_to_eval[0] == 0x01:
                # exec encoded with rot13
                return getattr(builtins1, codecs.decode("rkrp")[0])(zlib1.decompress(expr_to_eval[1:]), frame)
            else:
                return zlib1.decompress(expr_to_eval[1:])[::-1]

        gs = inspect.getsource(getitem_method_real.__code__)
        gs = textwrap.dedent(gs)
        getitem_ast = ast.parse(gs)
        getitem_ast = optimize_ast(getitem_ast)
        actual_co_obj = compile(getitem_ast, filename="", mode="exec", optimize=2)
        the_method = actual_co_obj.co_consts[
            0
        ]  # we have to do mental gymnastics here to get the actual method's code object back

        class_ctor = Assembler([])
        class_ctor.insn("resume", 0)

        class_ctor.insn("load_const", class_ctor.consts_create_or_get("0"))
        class_ctor.insn("store_name", class_ctor.names_create_or_get("__module__"))

        class_ctor.insn("load_const", class_ctor.consts_create_or_get("0"))
        class_ctor.insn("store_name", class_ctor.names_create_or_get("__qualname__"))

        # why write it manually when we can just use python to do it for us :^)
        class_ctor.insn("load_const", class_ctor.consts_create_or_get(the_method))
        class_ctor.insn("make_function", 0)
        class_ctor.insn("store_name", class_ctor.names_create_or_get("__getitem__"))

        class_ctor.insn("load_const", class_ctor.consts_create_or_get(None))
        class_ctor.insn("return_value")

        main = Assembler()
        main.insn("resume", 0)

        main.insn("push_null")
        main.insn("load_build_class")

        main.insn("load_const", main.consts_create_or_get(class_ctor.pack_code_object()))
        main.insn("make_function")

        main.insn("load_const", main.consts_create_or_get("0"))

        main.insn("precall", 2)
        main.insn("call", 2)
        main.insn("return_value")

        return main.pack_code_object()

    def create_loader(self):
        co = self._create_co_obj()
        the_funny = marshal.dumps(co)
        return Assign(  # {vname} = eval(__import__("marshal").loads(the_funny))()
            [Name(self.vname, Store())],
            Call(
                Call(
                    Name("eval", Load()),
                    [Call(Attribute(ast_import_full("marshal"), "loads", Load()), [Constant(the_funny)], [])],
                    [],
                ),
                [],
                [],
            ),
        )

    def transform(self, ast: AST, current_file_name, all_asts, all_file_names) -> AST:
        trafod_ast = self.visit(ast)
        if isinstance(trafod_ast, Module):  # just to make pycharm shut up, this will always be true
            trafod_ast.body.insert(0, self.create_loader())
        return trafod_ast
