#!/usr/bin/env python
"""Static repository, skill archive, and release payload checks."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path, PurePosixPath


FORBIDDEN_SKILL_PARTS = {"vendor", "node_modules", "__pycache__", "fonts"}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "release" / "payload.json").read_text(encoding="utf-8"))
    paths = set(payload["paths"])
    if "docs/deployment.md" not in paths:
        raise AssertionError("Release payload must include docs/deployment.md")
    forbidden_payload = {"skill-src", "dist", "agent-skill.md"}
    if paths & forbidden_payload:
        raise AssertionError(f"Forbidden release payload declarations: {sorted(paths & forbidden_payload)}")
    for declared in paths:
        if not (root / Path(declared)).exists():
            raise AssertionError(f"Release payload path does not exist: {declared}")

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("packageVersion") != "1.1.0":
        raise AssertionError("manifest.json packageVersion must be 1.1.0")
    manifest_paths = {entry["path"] for entry in manifest.get("files", [])}
    if "docs/deployment.md" not in manifest_paths:
        raise AssertionError("Manifest must cover docs/deployment.md")

    for source in sorted((root / "skill-src").iterdir()):
        if not source.is_dir():
            continue
        archive_path = root / "skills" / f"{source.name}.zip"
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if "SKILL.md" not in names:
                raise AssertionError(f"Archive lacks root SKILL.md: {archive_path}")
            if names != sorted(names):
                raise AssertionError(f"Archive paths are not sorted: {archive_path}")
            for name in names:
                if "\\" in name:
                    raise AssertionError(f"Archive contains a non-POSIX path: {name}")
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts:
                    raise AssertionError(f"Archive path escapes skill root: {name}")
                if {part.casefold() for part in path.parts} & FORBIDDEN_SKILL_PARTS:
                    raise AssertionError(f"Archive contains forbidden content: {name}")
                if path.suffix.casefold() in {".pyc", ".pyo"}:
                    raise AssertionError(f"Archive contains Python bytecode: {name}")
    print("PASS repository, skill archive, and release payload checks")


if __name__ == "__main__":
    main()
