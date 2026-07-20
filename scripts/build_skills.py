#!/usr/bin/env python
"""Build deterministic FastClaw skill archives from version-controlled sources."""

from __future__ import annotations

import argparse
import hashlib
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
EXCLUDED_DIRS = {"vendor", "node_modules", "__pycache__", ".git", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp", ".temp", ".log"}


def should_include(relative_path: Path) -> bool:
    parts = {part.casefold() for part in relative_path.parts}
    if parts & EXCLUDED_DIRS:
        return False
    return relative_path.suffix.casefold() not in EXCLUDED_SUFFIXES


def source_files(source_dir: Path) -> list[tuple[PurePosixPath, Path]]:
    skill_file = source_dir / "SKILL.md"
    if not skill_file.is_file():
        raise ValueError(f"Skill source is missing root SKILL.md: {source_dir}")

    files = []
    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source_dir)
        if should_include(relative):
            files.append((PurePosixPath(*relative.parts), path))
    return sorted(files, key=lambda item: item[0].as_posix())


def build_skill(source_dir: Path, output_path: Path) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for archive_path, source_path in source_files(source_dir):
            info = zipfile.ZipInfo(archive_path.as_posix(), FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.flag_bits |= 0x800
            archive.writestr(info, source_path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return hashlib.sha256(output_path.read_bytes()).hexdigest()


def build_all(source_root: Path, output_root: Path) -> dict[str, str]:
    sources = sorted(path for path in source_root.iterdir() if path.is_dir())
    if not sources:
        raise ValueError(f"No skill sources found under {source_root}")
    return {
        source.name: build_skill(source, output_root / f"{source.name}.zip")
        for source in sources
    }


def assert_reproducible(source_root: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="sciposter-skills-a-") as first_dir, tempfile.TemporaryDirectory(
        prefix="sciposter-skills-b-"
    ) as second_dir:
        first = build_all(source_root, Path(first_dir))
        second = build_all(source_root, Path(second_dir))
    if first != second:
        raise RuntimeError(f"Skill archives are not reproducible: {first!r} != {second!r}")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=repo_root / "skill-src")
    parser.add_argument("--output-root", type=Path, default=repo_root / "skills")
    parser.add_argument("--check-reproducible", action="store_true")
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    if args.check_reproducible:
        assert_reproducible(source_root)
    hashes = build_all(source_root, args.output_root.resolve())
    for name, digest in hashes.items():
        print(f"{digest}  {name}.zip")


if __name__ == "__main__":
    main()
