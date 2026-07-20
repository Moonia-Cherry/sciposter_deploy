#!/usr/bin/env python
import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Single-entry FastClaw poster workflow.")
    parser.add_argument("--workspace", default=".", help="Workspace directory.")
    parser.add_argument("--output-dir", default="output", help="Output directory.")
    parser.add_argument("--style", default="classic-blue", help="Poster style request.")
    parser.add_argument("--template", default="conference-classic", help="Poster template request.")
    parser.add_argument("--python", default=sys.executable, help="Python executable path.")
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parent
    workspace_dir = Path(args.workspace).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        args.python,
        str(skill_dir / "run_academic_poster_pipeline.py"),
        "--workspace",
        str(workspace_dir),
        "--output-dir",
        str(output_dir),
        "--style",
        args.style,
        "--template",
        args.template,
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
