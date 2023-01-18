# PyObf 2

A "continuation" of sorts of the old, private pyobf.

## Usage

The obfuscator has 2 modes of operation.
1. Standalone<br>The obfuscator runs on its own, with it's own config system. This is the default. Run with `python3.11 main.py`. A configuration file, `config.toml`, will be generated with the default values. Edit it, and run main.py again to run the obfuscator with the config.
2. API<br>The obfuscator has an API, to allow you to integrate it into your own projects. For example, it can be used to obfuscate the output of a code generator automatically. An example of this API being used can be seen in `api_example.py`.<br>If you end up using the API, please credit this repository.

## API usage
As previously mentioned, the `api_example.py` file contains examples on how the api works. Some notes are required, though:
- When obfuscating multiple files that depend on each other, use `do_obfuscation_batch_ast`, instead of calling `do_obfuscation_single_ast` on all of them separately. This will allow the obfuscator to draw conclusions on which file depends on which other file, and allows it to understand the structure between them.
- `do_obfuscation_batch_ast` is a generator. It will progressively yield each step it does, to allow for progress bar rendering. It will do nothing when not iterated through.
- Some transformers (eg. `packInPyz`, `compileFinalFiles`) only act on the **output files** of the obfuscation process, and do nothing in the standard run. To invoke them, use `do_post_run`. This will require you to write the obfuscated AST into a file, though.

## Feedback & bugs

The obfuscator is in no way perfect as of now, so feedback is encouraged. Please tell me how bad my code is in the
issues tab.