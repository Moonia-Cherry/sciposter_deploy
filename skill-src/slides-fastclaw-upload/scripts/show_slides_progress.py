#!/usr/bin/env python
import json
import sys
from pathlib import Path


def main():
    workspace = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    progress = workspace / "output" / "slides-progress.json"
    todo = workspace / "todo.md"
    if progress.exists():
        print(progress.read_text(encoding="utf-8"))
    elif todo.exists():
        print(todo.read_text(encoding="utf-8"))
    else:
        print("No slide progress found.")


if __name__ == "__main__":
    main()

