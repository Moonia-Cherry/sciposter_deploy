#!/usr/bin/env python3
"""Generate and validate SciPoster deployment package manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


class ManifestError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _is_cache_file(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".pyo"}


def _iter_tree_files(path: Path) -> Iterable[Path]:
    candidates = (item for item in path.rglob("*") if item.is_file() and not _is_cache_file(item))
    return sorted(candidates, key=lambda item: item.relative_to(path).as_posix().lower())


def sha256_tree(path: Path) -> tuple[str, int]:
    """Hash a directory as sorted relative paths plus per-file SHA-256."""
    digest = hashlib.sha256()
    count = 0
    for item in _iter_tree_files(path):
        relative = item.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(item).encode("ascii"))
        digest.update(b"\n")
        count += 1
    return digest.hexdigest().upper(), count


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ManifestError(f"required file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError(f"JSON root must be an object: {path}")
    return value


def _safe_relative_path(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError("manifest path must be a non-empty string")
    normalized = value.replace("\\", "/")
    relative = PurePosixPath(normalized)
    if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
        raise ManifestError(f"manifest path must stay within the package: {value}")
    return relative


def _resolve_manifest_path(root: Path, value: Any) -> tuple[str, Path]:
    relative = _safe_relative_path(value)
    return relative.as_posix(), root.joinpath(*relative.parts)


def validate_manifest(root: Path) -> None:
    root = root.resolve()
    manifest = _load_json(root / "manifest.json")
    if manifest.get("schemaVersion") != 1:
        raise ManifestError("manifest schemaVersion must be 1")

    failures: list[str] = []
    seen: set[str] = set()
    for entry in manifest.get("files", []):
        if not isinstance(entry, dict):
            failures.append("invalid file entry")
            continue
        try:
            relative, path = _resolve_manifest_path(root, entry.get("path", ""))
        except ManifestError as exc:
            failures.append(str(exc))
            continue
        key = relative.lower()
        if key in seen:
            failures.append(f"duplicate manifest path: {relative}")
            continue
        seen.add(key)
        expected = str(entry.get("sha256", "")).upper()
        if not path.is_file():
            failures.append(f"missing: {relative}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            failures.append(f"hash mismatch: {relative} (expected {expected}, got {actual})")
        expected_size = int(entry.get("size", -1))
        if path.stat().st_size != expected_size:
            failures.append(
                f"size mismatch: {relative} (expected {expected_size}, got {path.stat().st_size})"
            )

    for entry in manifest.get("trees", []):
        if not isinstance(entry, dict):
            failures.append("invalid tree entry")
            continue
        try:
            relative, path = _resolve_manifest_path(root, entry.get("path", ""))
        except ManifestError as exc:
            failures.append(str(exc))
            continue
        key = relative.lower()
        if key in seen:
            failures.append(f"duplicate manifest path: {relative}")
            continue
        seen.add(key)
        expected = str(entry.get("sha256", "")).upper()
        expected_count = int(entry.get("fileCount", -1))
        if not path.is_dir():
            failures.append(f"missing directory: {relative}")
            continue
        actual, count = sha256_tree(path)
        if actual != expected or count != expected_count:
            failures.append(
                f"tree mismatch: {relative} (expected {expected}/{expected_count} files, "
                f"got {actual}/{count} files)"
            )

    if failures:
        raise ManifestError("manifest validation failed:\n  " + "\n  ".join(failures))


def _is_inside(relative: PurePosixPath, parent: PurePosixPath) -> bool:
    return relative == parent or parent in relative.parents


def _payload_files(root: Path, payload_path: Path | None) -> Iterable[Path]:
    if payload_path is None:
        return (item for item in root.rglob("*") if item.is_file())

    payload = _load_json(payload_path.resolve())
    if payload.get("schemaVersion") != 1 or not isinstance(payload.get("paths"), list):
        raise ManifestError(f"invalid release payload specification: {payload_path}")
    candidates: dict[str, Path] = {}
    declared = [*payload["paths"], "bin/fastclaw/fastclaw.exe"]
    for value in declared:
        relative = _safe_relative_path(value)
        path = root.joinpath(*relative.parts)
        if path.is_file():
            candidates[relative.as_posix().lower()] = path
        elif path.is_dir():
            for item in path.rglob("*"):
                if item.is_file():
                    item_relative = PurePosixPath(item.relative_to(root).as_posix())
                    candidates[item_relative.as_posix().lower()] = item
        else:
            raise ManifestError(f"declared release payload path is missing: {relative.as_posix()}")
    return candidates.values()


def generate_manifest(
    root: Path,
    package_version: str,
    metadata_path: Path,
    payload_path: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    metadata = _load_json(metadata_path.resolve())
    platform = metadata.get("platform")
    versions = metadata.get("components")
    if platform != "windows-amd64":
        raise ManifestError(f"unsupported platform in base lock: {platform!r}")
    if not isinstance(versions, dict) or not versions:
        raise ManifestError("base lock components must be a non-empty object")

    tree_paths = (PurePosixPath("runtime/python"), PurePosixPath("runtime/node"))
    for tree_path in tree_paths:
        path = root.joinpath(*tree_path.parts)
        if not path.is_dir():
            raise ManifestError(f"required runtime tree is missing: {tree_path.as_posix()}")

    files: list[dict[str, Any]] = []
    candidates = (
        item
        for item in _payload_files(root, payload_path)
        if item.name != "manifest.json" and not _is_cache_file(item)
    )
    for item in sorted(candidates, key=lambda value: value.relative_to(root).as_posix().lower()):
        relative = PurePosixPath(item.relative_to(root).as_posix())
        if any(_is_inside(relative, tree_path) for tree_path in tree_paths):
            continue
        files.append(
            {
                "path": relative.as_posix(),
                "sha256": sha256_file(item),
                "size": item.stat().st_size,
            }
        )

    trees: list[dict[str, Any]] = []
    for relative in tree_paths:
        digest, count = sha256_tree(root.joinpath(*relative.parts))
        trees.append({"path": relative.as_posix(), "sha256": digest, "fileCount": count})

    manifest = {
        "schemaVersion": 1,
        "packageVersion": package_version,
        "platform": platform,
        "versions": versions,
        "files": files,
        "trees": trees,
    }
    output = root / "manifest.json"
    temporary = output.with_suffix(f".json.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, output)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--root", required=True, type=Path)

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--root", required=True, type=Path)
    generate_parser.add_argument("--package-version", required=True)
    generate_parser.add_argument("--metadata", required=True, type=Path)
    generate_parser.add_argument("--payload", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "generate":
            generate_manifest(args.root, args.package_version, args.metadata, args.payload)
            print(f"[sciposter] generated package manifest: {args.root / 'manifest.json'}", flush=True)
        else:
            validate_manifest(args.root)
            print("[sciposter] package manifest is valid", flush=True)
        return 0
    except ManifestError as exc:
        print(f"[sciposter] ERROR: {exc}", file=os.sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
