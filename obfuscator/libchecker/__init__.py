###############################################################
# Copyright (c) 0x150, 2022. BY-SA 4.0 License                #
# https://github.com/0x3C50/libchecker                        #
#                                                             #
# "This project" or "this library" refers to everything       #
# inside this folder.                                         #
# You are free to copy, modify and use this library           #
# in any project, if this note, in its entirety, stays        #
# unmodified, and the creator (0x150) is attributed,          #
# and all changes are noted below.                            #
# You may not change the license, if you modify this project. #
# https://creativecommons.org/licenses/by-sa/4.0/             #
###############################################################

import os.path


def _install_libraries(deps: list[str]):
    bruh = ["install"]
    for dep in deps:
        bruh.append(dep)
    _call_pip(bruh)


def _call_pip(args: list[str]):
    pip_internal = __import__("importlib").import_module(
        "pip._internal.cli.main"
    )  # zero top level imports
    pip_internal.main(args)


def is_import_available(name: str) -> bool:
    """
    Checks if the given import is available

    :param name: The import name
    :return: True if the import exists, False otherwise
    """
    try:
        __import__(name)
        return True
    except ModuleNotFoundError:
        return False


def _get_uninstalled_libraries(libraries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    uninstalled_libs = []
    for lib_to_check in libraries:
        if not is_import_available(lib_to_check[0]):
            uninstalled_libs.append(lib_to_check)
    return uninstalled_libs


def check_if_libraries_exist(libraries: list[tuple[str, str]], install_if_missing: bool = True) -> bool:
    """
    Checks if the libraries given are installed, and optionally installs them for you

    :param libraries: A list of tuples describing what the import for the module is, and what the package name is, respectively
    :param install_if_missing: Installs the dependencies for you if they're missing
    :return: True if it is safe to continue with the script and all modules are ready, False if not. Will always be True when install_if_missing is True
    """
    uninstalled = _get_uninstalled_libraries(libraries)
    if len(uninstalled) == 0:
        return True
    if not install_if_missing:  # Can't do anything about it, tell the user "no" and move on
        return False
    _install_libraries([x[1] for x in uninstalled])  # We want to install them anyways, so let's just do it
    return True


def install_all_from_requirements_txt(requirements_txt_path: str = "requirements.txt"):
    """
    Installs all requirements from a requirements.txt file

    :param requirements_txt_path: The path to the requirements.txt file
    :return: Nothing
    """
    if not os.path.exists(requirements_txt_path):
        raise FileNotFoundError("File "+requirements_txt_path+" not found")
    _call_pip(["install", "-r", requirements_txt_path])
