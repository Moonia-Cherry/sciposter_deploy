#!/usr/bin/env python
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


def summarize_error(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return "No uploaded paper was detected in the current workspace."
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if "No paper file" in line:
            return line
    return lines[-1]


def write_progress(workspace_dir: Path, stages, active_index: int, note: str, extra: Optional[dict] = None) -> None:
    todo_path = workspace_dir / "todo.md"
    progress_path = workspace_dir / "output" / "poster-progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for index, label in enumerate(stages):
        mark = "x" if index < active_index else " "
        lines.append(f"- [{mark}] {label}")
    if active_index < len(stages):
        lines.append("")
        lines.append(f"Current: {stages[active_index]}")
    lines.append(f"Note: {note}")
    todo_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload = {
        "active_index": active_index,
        "total": len(stages),
        "current": stages[active_index] if active_index < len(stages) else "Done",
        "note": note,
    }
    if extra:
        payload.update(extra)
    progress_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[progress] {payload['current']}: {note}", flush=True)


def run_normalization_with_retry(args, skill_dir: Path, workspace_dir: Path, output_dir: Path, stages):
    normalize_cmd = [
        args.python,
        str(skill_dir / "prepare_workspace_inputs.py"),
        "--workspace",
        str(workspace_dir),
        "--output",
        str(output_dir / "workspace-inputs.json"),
    ]
    retry_delays = [0, 2, 4]
    last_result = None
    for attempt, delay in enumerate(retry_delays, start=1):
        if delay:
            write_progress(
                workspace_dir,
                stages,
                0,
                f"Waiting {delay}s for uploaded files to finish landing in the workspace before rescanning.",
                {"attempt": attempt, "max_attempts": len(retry_delays)},
            )
            time.sleep(delay)
        write_progress(
            workspace_dir,
            stages,
            0,
            f"Scanning workspace for uploaded paper files (attempt {attempt}/{len(retry_delays)}).",
            {"attempt": attempt, "max_attempts": len(retry_delays)},
        )
        last_result = subprocess.run(normalize_cmd, capture_output=True, text=True)
        if last_result.returncode == 0:
            return last_result
    return last_result


def build_cache_fingerprint(prepared_input: Path, style: str, template: str, images_dir: Path) -> str:
    payload = {
        "input_path": str(prepared_input),
        "input_mtime_ns": prepared_input.stat().st_mtime_ns if prepared_input.exists() else 0,
        "input_size": prepared_input.stat().st_size if prepared_input.exists() else 0,
        "style": style,
        "template": template,
        "images": [],
    }
    if images_dir.exists():
        for image_path in sorted(p for p in images_dir.iterdir() if p.is_file()):
            payload["images"].append(
                {
                    "name": image_path.name,
                    "mtime_ns": image_path.stat().st_mtime_ns,
                    "size": image_path.stat().st_size,
                }
            )
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Run the academic poster pipeline end-to-end.")
    parser.add_argument("--workspace", default=".", help="Workspace directory.")
    parser.add_argument("--input", default="", help="Path to workspace-inputs.json.")
    parser.add_argument("--images-dir", default=".", help="Directory containing figure images.")
    parser.add_argument("--style", default="classic-blue", help="Poster style request.")
    parser.add_argument("--template", default="conference-classic", help="Poster template request.")
    parser.add_argument("--output-dir", required=True, help="Directory for generated files.")
    parser.add_argument("--node", default=shutil.which("node") or "", help="Node executable path.")
    parser.add_argument("--python", default=sys.executable, help="Python executable path.")
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parent
    workspace_dir = Path(args.workspace).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    workspace_input_path = Path(args.input).resolve() if args.input else (output_dir / "workspace-inputs.json").resolve()

    package_path = output_dir / "poster-package.json"
    spec_path = output_dir / "poster-spec.json"
    svg_path = output_dir / "academic-poster.svg"
    pptx_path = output_dir / "academic-poster.pptx"
    png_path = output_dir / "academic-poster.png"
    preview_html_path = output_dir / "poster-preview.html"
    extracted_asset_dir = output_dir / "extracted_assets"
    cache_manifest_path = output_dir / "poster-build-cache.json"

    stages = [
        "Locate and normalize the uploaded paper",
        "Build the structured poster package",
        "Render a quick SVG preview",
        "Render the editable PPTX poster",
        "Build the preview page and final report",
    ]

    write_progress(
        workspace_dir,
        stages,
        0,
        "Poster workflow started. Running fast upload detection before paper parsing.",
        {"workspace": str(workspace_dir)},
    )

    if not workspace_input_path.exists():
        write_progress(workspace_dir, stages, 0, "Workspace input description is missing, running normalization first.")
        normalize_result = run_normalization_with_retry(args, skill_dir, workspace_dir, output_dir, stages)
        if normalize_result.returncode != 0:
            reason = summarize_error(normalize_result.stderr.strip() or normalize_result.stdout.strip())
            write_progress(workspace_dir, stages, 0, "No uploaded paper was detected. Writing a local diagnostic report.", {"error": reason})
            report_cmd = [
                args.python,
                str(skill_dir / "build_missing_upload_report.py"),
                "--workspace",
                str(workspace_dir),
                "--output-dir",
                str(output_dir),
                "--reason",
                reason,
            ]
            subprocess.run(report_cmd, check=True)
            print(str(output_dir / "missing-upload-report.json"))
            return
        workspace_input_path = output_dir / "workspace-inputs.json"

    workspace_inputs = json.loads(workspace_input_path.read_text(encoding="utf-8"))
    prepared_input = Path(workspace_inputs["paper_safe"]).resolve()
    images_dir = Path(args.images_dir).resolve()
    safe_images = workspace_inputs.get("safe_images") or []
    if safe_images:
        images_dir = Path(safe_images[0]).resolve().parent

    write_progress(
        workspace_dir,
        stages,
        0,
        "Uploaded paper has been normalized to a safe local filename.",
        {"input": str(prepared_input)},
    )

    build_cmd = [
        args.python,
        str(skill_dir / "build_poster_package.py"),
        "--input",
        str(prepared_input),
        "--images-dir",
        str(images_dir),
        "--style",
        args.style,
        "--template",
        args.template,
        "--asset-output-dir",
        str(extracted_asset_dir),
        "--output",
        str(package_path),
    ]
    cache_fingerprint = build_cache_fingerprint(prepared_input, args.style, args.template, images_dir)
    should_rebuild_package = True
    if package_path.exists() and cache_manifest_path.exists():
        try:
            cache_manifest = json.loads(cache_manifest_path.read_text(encoding="utf-8"))
            should_rebuild_package = cache_manifest.get("fingerprint") != cache_fingerprint
        except Exception:
            should_rebuild_package = True
    write_progress(
        workspace_dir,
        stages,
        1,
        "Extracting paper structure, figures, and layout metadata. Cached package data will be reused when possible.",
        {"output": str(package_path)},
    )
    if should_rebuild_package:
        subprocess.run(build_cmd, check=True)
        cache_manifest_path.write_text(
            json.dumps(
                {
                    "fingerprint": cache_fingerprint,
                    "package": str(package_path),
                    "style": args.style,
                    "template": args.template,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        write_progress(
            workspace_dir,
            stages,
            1,
            "Detected matching paper content and template settings, so the cached poster package is being reused.",
            {"output": str(package_path), "cache_hit": True},
        )
    spec_path.write_text(package_path.read_text(encoding="utf-8"), encoding="utf-8")

    svg_cmd = [
        args.python,
        str(skill_dir / "render_academic_poster_svg.py"),
        "--spec",
        str(package_path),
        "--output",
        str(svg_path),
    ]
    write_progress(
        workspace_dir,
        stages,
        2,
        "Rendering SVG preview first so the user can inspect the layout before PPTX export finishes.",
        {"preview_svg": str(svg_path)},
    )
    subprocess.run(svg_cmd, check=True)

    node_path = args.node or shutil.which("node")
    if not node_path:
        raise RuntimeError("Node executable not found. Pass --node explicitly.")

    render_cmd = [
        node_path,
        str(skill_dir / "render_academic_poster.mjs"),
        "--spec",
        str(package_path),
        "--output",
        str(pptx_path),
        "--preview",
        str(png_path),
        "--workspace",
        str(output_dir / "_poster_build"),
    ]
    env = os.environ.copy()
    env.setdefault("HOME", str(Path.home()))
    env.setdefault("USERPROFILE", str(Path.home()))
    write_progress(
        workspace_dir,
        stages,
        3,
        "Rendering the editable PPTX poster. This is the slowest step, but the SVG preview is already ready.",
        {"pptx": str(pptx_path)},
    )
    subprocess.run(render_cmd, check=True, env=env)

    html_cmd = [
        args.python,
        str(skill_dir / "build_preview_page.py"),
        "--output",
        str(preview_html_path),
    ]
    write_progress(
        workspace_dir,
        stages,
        4,
        "Building preview page and final download links.",
        {"preview_html": str(preview_html_path)},
    )
    subprocess.run(html_cmd, check=True)

    report_cmd = [
        args.python,
        str(skill_dir / "build_final_report.py"),
        "--output-dir",
        str(output_dir),
    ]
    subprocess.run(report_cmd, check=True)

    write_progress(
        workspace_dir,
        stages,
        len(stages),
        "Poster generation finished. PPTX, SVG, PNG, spec, preview page, and final report are ready.",
        {
            "pptx": str(pptx_path),
            "svg": str(svg_path),
            "png": str(png_path),
            "preview_html": str(preview_html_path),
            "final_report": str(output_dir / "final-response.json"),
        },
    )

    print(str(pptx_path))


if __name__ == "__main__":
    main()
