#!/usr/bin/env python
import argparse
import json
import os
import shutil
import zipfile
from pathlib import Path


PAPER_EXTS = [".docx", ".doc", ".pdf", ".md", ".txt"]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".emf", ".wmf"}
IGNORED_NAMES = {
    "todo.md",
    "workspace-inputs.json",
    "parsed-paper.json",
    "paper-body.txt",
    "slides-package.json",
    "slides-outline.md",
    "speaker-notes.md",
    "figure-plan.md",
    "discussion-questions.md",
    "slides.pptx",
    "slides-preview.html",
    "final-response.json",
    "final-response.md",
    "missing-upload-report.json",
    "missing-upload-report.md",
}
IGNORED_DIRS = {"output", ".git", "__pycache__", "node_modules", ".next"}
PREFERRED_DIR_HINTS = ("sessions", "uploads", "files", "open-files", "attachments")


def newest_file(paths):
    return sorted(paths, key=lambda p: (p.stat().st_mtime, p.name.lower()), reverse=True)[0]


def is_ignored_path(path: Path) -> bool:
    lower_parts = {part.lower() for part in path.parts}
    if lower_parts & IGNORED_DIRS:
        return True
    return path.name.lower() in IGNORED_NAMES


def detect_file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in PAPER_EXTS:
        return suffix
    try:
        with path.open("rb") as fh:
            head = fh.read(4096)
    except Exception:
        return ""
    if head.startswith(b"%PDF"):
        return ".pdf"
    if head.startswith(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"):
        return ".doc"
    if zipfile.is_zipfile(path):
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
            if "word/document.xml" in names:
                return ".docx"
        except Exception:
            return ""
    try:
        text_head = head.decode("utf-8")
    except Exception:
        return ""
    if text_head.strip():
        return ".txt"
    return ""


def iter_workspace_files(workspace: Path):
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [name for name in dirs if name.lower() not in IGNORED_DIRS]
        root_path = Path(root)
        for file_name in files:
            path = root_path / file_name
            if is_ignored_path(path):
                continue
            yield path


def candidate_scan_roots(workspace: Path):
    # Never escape the agent workspace: parent traversal could ingest another
    # chat's attachment or an unrelated host file.
    return [workspace.resolve()]


def candidate_directories(workspace: Path):
    dirs = []
    seen = set()

    def add_dir(path: Path):
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        key = str(resolved).lower()
        if key in seen or not resolved.exists() or not resolved.is_dir():
            return
        seen.add(key)
        dirs.append(resolved)

    add_dir(workspace)
    for root in candidate_scan_roots(workspace):
        add_dir(root)
        for hint in PREFERRED_DIR_HINTS:
            add_dir(root / hint)
        try:
            children = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
        except Exception:
            children = []
        for child in children[:12]:
            lower_name = child.name.lower()
            if any(hint in lower_name for hint in PREFERRED_DIR_HINTS):
                add_dir(child)
    return dirs


def quick_paper_candidates(workspace: Path):
    found = []
    seen = set()
    for directory in candidate_directories(workspace):
        try:
            entries = sorted([p for p in directory.iterdir() if p.is_file()], key=lambda p: p.name.lower())
        except Exception:
            continue
        for path in entries:
            if is_ignored_path(path):
                continue
            detected = detect_file_type(path)
            if not detected:
                continue
            key = str(path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            found.append((path, detected, directory))
    return found


def collect_paper_candidates(workspace: Path):
    fast = quick_paper_candidates(workspace)
    if fast:
        return fast
    out = []
    for root in candidate_scan_roots(workspace):
        for p in iter_workspace_files(root):
            detected = detect_file_type(p)
            if detected:
                out.append((p, detected, root))
    return out


def choose_paper(workspace: Path) -> Path:
    candidates = collect_paper_candidates(workspace)
    if not candidates:
        raise FileNotFoundError("No paper file (.pdf, .doc, .docx, .md, .txt) found in workspace.")
    workspace_resolved = workspace.resolve()
    scored = []
    for candidate, _, root in candidates:
        parts_lower = [part.lower() for part in candidate.parts]
        hint_score = sum(1 for part in parts_lower for hint in PREFERRED_DIR_HINTS if hint in part)
        same_root_bonus = 2 if root == workspace_resolved else 0
        workspace_name_bonus = 1 if any(part.lower() == "workspace" for part in parts_lower) else 0
        scored.append((hint_score, same_root_bonus, workspace_name_bonus, candidate.stat().st_mtime, candidate.name.lower(), candidate))
    scored.sort(reverse=True)
    return scored[0][5]


def copy_paper_to_safe_name(workspace: Path, source: Path) -> Path:
    suffix = detect_file_type(source) or source.suffix.lower() or ".txt"
    target = workspace / f"paper{suffix}"
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    return target


def build_scan_report(workspace: Path):
    paper_candidates = collect_paper_candidates(workspace)
    scan_roots = candidate_scan_roots(workspace)
    image_candidates = []
    visible_files = []
    seen_images = set()
    seen_files = set()
    for root in scan_roots:
        for path in iter_workspace_files(root):
            file_key = str(path.resolve()).lower()
            if file_key not in seen_files:
                seen_files.add(file_key)
                visible_files.append(path)
            if path.suffix.lower() in IMAGE_EXTS and file_key not in seen_images:
                seen_images.add(file_key)
                image_candidates.append(path)
    return {
        "workspace": str(workspace),
        "scan_roots": [str(root) for root in scan_roots],
        "paper_candidate_count": len(paper_candidates),
        "paper_candidates": [
            {"path": str(path.resolve()), "detected_type": detected_type, "found_under": str(root)}
            for path, detected_type, root in sorted(paper_candidates, key=lambda item: str(item[0]).lower())
        ],
        "image_candidate_count": len(image_candidates),
        "image_candidates": [str(path.resolve()) for path in sorted(image_candidates)],
        "other_file_count": len(visible_files),
        "other_files": [str(path.resolve()) for path in sorted(visible_files)[:30]],
        "preferred_dir_hints": list(PREFERRED_DIR_HINTS),
        "hint": "If the FastClaw attachment bubble shows a file but this report is empty, the uploaded paper did not land in the current workspace/session.",
    }


def main():
    parser = argparse.ArgumentParser(description="Normalize uploaded workspace inputs into a safe ASCII filename.")
    parser.add_argument("--workspace", default=".", help="Workspace directory containing uploaded files.")
    parser.add_argument("--output", default="", help="Optional JSON output path.")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    try:
        paper_src = choose_paper(workspace)
    except FileNotFoundError:
        report = build_scan_report(workspace)
        if args.output:
            output_path = Path(args.output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        raise
    safe_paper = copy_paper_to_safe_name(workspace, paper_src)

    result = {
        "workspace": str(workspace),
        "paper_original": str(paper_src.resolve()),
        "paper_safe": str(safe_paper.resolve()),
        "paper_extension": safe_paper.suffix.lower(),
        "image_candidates": build_scan_report(workspace).get("image_candidates", []),
    }

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
