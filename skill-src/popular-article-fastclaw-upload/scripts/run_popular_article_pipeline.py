#!/usr/bin/env python
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


def write_progress(workspace_dir: Path, stages, active_index: int, note: str, extra: Optional[dict] = None) -> None:
    todo_path = workspace_dir / "todo.md"
    progress_path = workspace_dir / "output" / "popular-article-progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for index, label in enumerate(stages):
        mark = "x" if index < active_index else " "
        lines.append(f"- [{mark}] {label}")
    if active_index < len(stages):
        lines.append("")
        lines.append(f"当前步骤: {stages[active_index]}")
    lines.append(f"说明: {note}")
    todo_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    payload = {
        "active_index": active_index,
        "total": len(stages),
        "current": stages[active_index] if active_index < len(stages) else "已完成",
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
                f"检测到上传文件可能仍在落地，等待 {delay} 秒后重新扫描。",
                {"attempt": attempt, "max_attempts": len(retry_delays)},
            )
            time.sleep(delay)
        write_progress(
            workspace_dir,
            stages,
            0,
            f"正在扫描工作区中的论文文件（第 {attempt}/{len(retry_delays)} 次）。",
            {"attempt": attempt, "max_attempts": len(retry_delays)},
        )
        last_result = subprocess.run(normalize_cmd, capture_output=True, text=True)
        if last_result.returncode == 0:
            return last_result
    return last_result


def main():
    parser = argparse.ArgumentParser(description="Run the popular article pipeline end-to-end.")
    parser.add_argument("--workspace", default=".", help="Workspace directory.")
    parser.add_argument("--input", default="", help="Optional path to parsed-paper.json.")
    parser.add_argument("--output-dir", required=True, help="Directory for generated files.")
    parser.add_argument("--python", default=sys.executable, help="Python executable path.")
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parent
    workspace_dir = Path(args.workspace).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    parsed_input = Path(args.input).resolve() if args.input else output_dir / "parsed-paper.json"

    stages = [
        "定位并规范化上传论文",
        "解析论文结构化内容",
        "生成微信公众号中文成稿",
        "生成预览页与论文配图",
        "导出正文与公众号头图",
        "写入最终交付报告",
    ]

    parse_cmd = [
        args.python,
        str(skill_dir / "parse_paper.py"),
        "--input",
        str(output_dir / "workspace-inputs.json"),
        "--output-dir",
        str(output_dir),
    ]

    write_progress(workspace_dir, stages, 0, "开始处理上传论文，准备生成微信公众号文章。")

    if not parsed_input.exists():
        write_progress(workspace_dir, stages, 0, "尚未发现 parsed-paper.json，先执行论文定位与规范化。")
        normalize_result = run_normalization_with_retry(args, skill_dir, workspace_dir, output_dir, stages)
        if normalize_result.returncode != 0:
            reason = normalize_result.stderr.strip() or normalize_result.stdout.strip() or "当前工作区中未检测到可用论文文件。"
            write_progress(workspace_dir, stages, 0, "未检测到论文文件，正在写入本地诊断报告。", {"error": reason})
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
        write_progress(workspace_dir, stages, 1, "已找到论文文件，正在解析标题、摘要和正文结构。")
        subprocess.run(parse_cmd, check=True)
        parsed_input = output_dir / "parsed-paper.json"

    write_progress(workspace_dir, stages, 1, "论文结构化解析已完成。", {"input": str(parsed_input)})

    package_cmd = [
        args.python,
        str(skill_dir / "build_article_package.py"),
        "--input",
        str(parsed_input),
        "--output-dir",
        str(output_dir),
    ]
    write_progress(workspace_dir, stages, 2, "正在生成适合微信公众号发布的中文成稿与栏目结构。")
    subprocess.run(package_cmd, check=True)

    preview_cmd = [
        args.python,
        str(skill_dir / "build_preview_page.py"),
        "--input",
        str(output_dir / "popular-article-package.json"),
        "--output",
        str(output_dir / "popular-article-preview.html"),
    ]
    write_progress(
        workspace_dir,
        stages,
        3,
        "正在生成预览页，并整理从论文中提取的可用配图。",
        {"preview_html": str(output_dir / "popular-article-preview.html")},
    )
    subprocess.run(preview_cmd, check=True)

    export_cmd = [
        args.python,
        str(skill_dir / "render_article_exports.py"),
        "--input",
        str(output_dir / "popular-article-package.json"),
        "--output-dir",
        str(output_dir),
    ]
    cover_cmd = [
        args.python,
        str(skill_dir / "render_wechat_cover.py"),
        "--input",
        str(output_dir / "popular-article-package.json"),
        "--output-dir",
        str(output_dir),
    ]
    write_progress(
        workspace_dir,
        stages,
        4,
        "正在导出 DOCX 和真实 PDF，并额外生成公众号头图 PNG / PPT。",
        {
            "docx": str(output_dir / "popular-article.docx"),
            "pdf": str(output_dir / "popular-article.pdf"),
            "cover_png": str(output_dir / "wechat-cover.png"),
            "cover_pptx": str(output_dir / "wechat-cover.pptx"),
        },
    )
    subprocess.run(export_cmd, check=True)
    subprocess.run(cover_cmd, check=True)

    report_cmd = [
        args.python,
        str(skill_dir / "build_final_report.py"),
        "--output-dir",
        str(output_dir),
    ]
    write_progress(workspace_dir, stages, 5, "正在写入最终交付报告，完成后即可直接展示结果。")
    subprocess.run(report_cmd, check=True)

    write_progress(
        workspace_dir,
        stages,
        len(stages),
        "公众号成稿、预览页、正文导出和头图文件均已准备完成。",
        {
            "preview_html": str(output_dir / "popular-article-preview.html"),
            "markdown": str(output_dir / "popular-article.md"),
            "docx": str(output_dir / "popular-article.docx"),
            "pdf": str(output_dir / "popular-article.pdf"),
            "cover_png": str(output_dir / "wechat-cover.png"),
            "cover_pptx": str(output_dir / "wechat-cover.pptx"),
            "package": str(output_dir / "popular-article-package.json"),
            "final_report": str(output_dir / "final-response.json"),
        },
    )
    print(str(output_dir / "final-response.json"))


if __name__ == "__main__":
    main()
