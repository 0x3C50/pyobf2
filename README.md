# PyObf 2

A "continuation" of sorts of the old, private pyobf.

## Installing
The package now has a pypi! https://pypi.org/project/pyobf2/

Install with `python3 -m pip install pyobf2`

## Usage

The obfuscator has an API, to allow you to integrate it into your own projects. For example, it can be used to obfuscate the output of a code generator automatically. An example usages of the API can be found in `examples/api/`. If you end up using the API, please credit this repository.

If you just want to run the obfuscator, run `pyobf2` or `python3 -m pyobf2` after installing it

## API usage
As previously mentioned, the `examples/api/` directory contains examples on how the api works. Some notes are required, though:
- When obfuscating multiple files that depend on each other, use `do_obfuscation_batch_ast`, instead of calling `do_obfuscation_single_ast` on all of them separately. This will allow the obfuscator to draw conclusions on which file depends on which other file, and allows it to understand the structure between them.
- `do_obfuscation_batch_ast` is a generator. It will progressively yield each step it does, to allow for progress bar rendering. It will do nothing when not iterated through.
- Some transformers (eg. `packInPyz`, `compileFinalFiles`) only act on the **output files** of the obfuscation process, and do nothing in the standard run. To invoke them, use `do_post_run`. This will require you to write the obfuscated AST into a file, though.

## Feedback & bugs

The obfuscator is in no way perfect as of now, so feedback is encouraged. Please tell me how bad my code is in the
issues tab.