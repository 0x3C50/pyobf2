import os.path
import pathlib
import shutil
import tempfile
import zipfile

from ..cfg import ConfigValue
from . import Transformer


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
