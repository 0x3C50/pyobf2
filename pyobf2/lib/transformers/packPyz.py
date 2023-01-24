import atexit
import inspect
import os.path
import pathlib
import shutil
import string
import tempfile
import textwrap
import zipfile

from . import *


def _lhandler(key_passphrase, mainfile):
    import Crypto.PublicKey.RSA as RSA
    from Crypto.Cipher import PKCS1_OAEP as PKCS1_OAEP
    from zipfile import ZipFile as ZipFile, ZIP_DEFLATED as ZIP_DEFLATED
    from io import BytesIO as BytesIO
    import tempfile as tmpf
    import sys as sys
    import os.path as pth
    import pathlib as pthlib

    root = pthlib.Path(__file__).parent

    root_dir_a = pthlib.Path(tmpf.mkdtemp())
    this_dir = root_dir_a.joinpath("b")

    with ZipFile(root, "r", ZIP_DEFLATED) as f:
        f.extractall(this_dir)

    with open(this_dir.joinpath("0"), "rb") as f, open(this_dir.joinpath("id.rsa"), "rb") as f1:
        enc_content = f.read()
        key_bytes = f1.read()
    key = RSA.import_key(key_bytes, key_passphrase)
    decrypted_dir = root_dir_a.joinpath("a")
    res = PKCS1_OAEP.new(key).decrypt(enc_content)
    with ZipFile(BytesIO(res), "r", ZIP_DEFLATED) as f:
        f.extractall(decrypted_dir)
    sys.path.insert(0, str(decrypted_dir))  # add to search path
    atexit.register(lambda v: __import__("shutil").rmtree(root_dir_a))

    with open(pth.join(decrypted_dir, mainfile), "r") as f:
        exec(f.read())


class PackInPyz(Transformer):
    def __init__(self):
        super().__init__(
            "packInPyz",
            'Packs all of the scripts into a .pyz file, creating an one file "executable". '
            "Specifically effective when used with multiple input files",
            bootstrap_file=ConfigValue(
                "The file to start when the .pyz is started. File will be renamed to __main__.py inside the .pyz",
                "__main__.py",
            ),
            encrypt=ConfigValue("Encrypts all contents of the .pyz using a random RSA256 key", True),
        )

    def transform_output(self, output_location: pathlib.Path, all_files: list[pathlib.Path]) -> list[pathlib.Path]:
        if len(all_files) > 1:
            commom_prefix = os.path.commonpath(all_files)
            mapped_file_names = [str(x)[len(commom_prefix) + 1 :] for x in all_files]
        else:
            commom_prefix = str(all_files[0].parent)
            mapped_file_names = [x.name for x in all_files]
        bs_file = self.config["bootstrap_file"].value
        if bs_file not in mapped_file_names:
            print(
                "Cannot locate bootstrap file",
                bs_file,
                "in output paths. Available files are:",
                mapped_file_names,
            )
            print("Skipping packInPyz")
            return all_files
        tempdir = pathlib.Path(tempfile.mkdtemp())
        out_path = tempdir.joinpath("archive.pyz")
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as f:
            for x in all_files:
                c_name = str(x)[len(commom_prefix) + 1 :]
                if c_name == bs_file:
                    f.write(x, "__main__" + os.path.splitext(c_name)[1])
                else:
                    f.write(x, c_name)
        shutil.rmtree(
            output_location,
            ignore_errors=False,
            onerror=None,
        )
        if self.config["encrypt"].value:
            import Crypto.PublicKey.RSA as RSA
            from Crypto.Cipher import PKCS1_OAEP

            k = RSA.generate(2048)
            passphr = "".join(random.choices(string.printable, k=16))
            enc_key = k.export_key("PEM", passphr, 8, "scryptAndAES128-CBC")
            with open(out_path, "rb") as f:
                orig_bytes = f.read()
            pk = PKCS1_OAEP.new(k)

            launcher_bc = _lhandler.__code__

            gs = inspect.getsource(launcher_bc)
            gs = textwrap.dedent(gs)
            generted_ast = ast.parse(gs)
            generted_ast = optimize_ast(generted_ast)

            gn_ast = Module(
                body=[
                    *generted_ast.body,
                    Expr(Call(func=Name("m0", Load()), args=[Constant(passphr), Constant("__main__.py")], keywords=[])),
                ],
                type_ignores=[],
            )
            with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as f:
                f.writestr("0", pk.encrypt(orig_bytes))
                f.writestr("id.rsa", enc_key)
                f.writestr("__main__.py", ast.unparse(ast.fix_missing_locations(gn_ast)))

        output_location.mkdir(parents=True, exist_ok=True)
        fin = output_location.joinpath("archive.pyz")
        with open(fin, "wb") as outfile, open(out_path, "rb") as infile:
            while infile.readable():
                t = infile.read(1024)
                if len(t) == 0:  # we're done
                    break
                outfile.write(t)
        out_path.unlink()
        tempdir.rmdir()

        return [fin]
