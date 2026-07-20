#!/usr/bin/env python
import argparse
import json
import shutil
import zipfile
from pathlib import Path


PAPER_EXTS = [".docx", ".doc", ".pdf", ".md", ".txt"]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".emf", ".wmf"}
SAFE_STEMS = {
    ".docx": "paper",
    ".doc": "paper",
    ".pdf": "paper",
    ".md": "paper",
    ".txt": "paper",
}
IGNORED_NAMES = {
    "todo.md",
    "workspace-inputs.json",
    "parsed-paper.json",
    "paper-body.txt",
    "popular-article-package.json",
    "popular-article.md",
    "article-title-options.md",
    "chart-briefs.md",
    "animation-briefs.md",
    "popular-article-preview.html",
    "final-response.json",
    "final-response.md",
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


def collect_paper_candidates(workspace: Path):
    out = []
    for p in workspace.rglob("*"):
        if not p.is_file() or is_ignored_path(p):
            continue
        detected = detect_file_type(p)
        if detected:
            out.append((p, detected))
    return out


def choose_paper(workspace: Path) -> Path:
    candidates = [p for p, _ in collect_paper_candidates(workspace)]
    if not candidates:
        raise FileNotFoundError("No paper file (.pdf, .doc, .docx, .md, .txt) found in workspace.")
    scored = []
    for candidate in candidates:
        parts_lower = [part.lower() for part in candidate.parts]
        hint_score = sum(1 for part in parts_lower for hint in PREFERRED_DIR_HINTS if hint in part)
        scored.append((hint_score, candidate.stat().st_mtime, candidate.name.lower(), candidate))
    scored.sort(reverse=True)
    return scored[0][3]


def copy_paper_to_safe_name(workspace: Path, source: Path) -> Path:
    suffix = detect_file_type(source) or source.suffix.lower() or ".txt"
    target = workspace / f"{SAFE_STEMS.get(suffix, 'paper')}{suffix}"
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    return target


def build_scan_report(workspace: Path):
    detected_candidates = collect_paper_candidates(workspace)
    image_candidates = [
        p for p in workspace.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS and not is_ignored_path(p)
    ]
    other_files = [
        p for p in workspace.rglob("*")
        if p.is_file() and not is_ignored_path(p)
    ]
    return {
        "workspace": str(workspace),
        "paper_candidate_count": len(detected_candidates),
        "paper_candidates": [
            {"path": str(p.resolve()), "detected_type": detected}
            for p, detected in sorted(detected_candidates, key=lambda item: str(item[0]).lower())
        ],
        "image_candidate_count": len(image_candidates),
        "image_candidates": [str(p.resolve()) for p in sorted(image_candidates)],
        "other_file_count": len(other_files),
        "other_files": [str(p.resolve()) for p in sorted(other_files)[:30]],
        "session_like_directories": [
            str(p.resolve())
            for p in sorted(
                [
                    p for p in workspace.rglob("*")
                    if p.is_dir() and any(hint in p.name.lower() for hint in PREFERRED_DIR_HINTS)
                ],
                key=lambda item: str(item).lower(),
            )[:20]
        ],
        "preferred_dir_hints": list(PREFERRED_DIR_HINTS),
        "hint": "If the attachment bubble shows a file but this list is empty, the uploaded paper did not land in the current FastClaw workspace or landed in a different chat/project scope.",
    }


def main():
    parser = argparse.ArgumentParser(description="Normalize uploaded workspace inputs into safe ASCII filenames.")
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
    }

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
