#!/usr/bin/env python
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Show the latest poster progress status.")
    parser.add_argument("--workspace", default=".", help="Workspace root containing output/poster-progress.json.")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    progress_path = workspace / "output" / "poster-progress.json"
    todo_path = workspace / "todo.md"

    if progress_path.exists():
      payload = json.loads(progress_path.read_text(encoding="utf-8"))
      print(json.dumps(payload, ensure_ascii=False, indent=2))
      return

    if todo_path.exists():
      print(todo_path.read_text(encoding="utf-8"))
      return

    print("No poster progress file found yet.")


if __name__ == "__main__":
    main()
