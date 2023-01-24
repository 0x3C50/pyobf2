import pathlib
import os
import sys

if __name__ == "__main__":
    if os.environ.get("ADD_PATH"):
        sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    from pyobf2 import main

    main()
