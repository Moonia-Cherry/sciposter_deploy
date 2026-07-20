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
    progress_path = workspace_dir / "output" / "xhs-progress.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for index, label in enumerate(stages):
        mark = "x" if index < active_index else " "
        lines.append("- [{0}] {1}".format(mark, label))
    if active_index < len(stages):
        lines.append("")
        lines.append("当前步骤: {0}".format(stages[active_index]))
    lines.append("说明: {0}".format(note))
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
    print("[progress] {0}: {1}".format(payload["current"], note), flush=True)


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
                "等待 {0} 秒后重试，确保上传论文已经写入当前工作区。".format(delay),
                {"attempt": attempt, "max_attempts": len(retry_delays)},
            )
            time.sleep(delay)
        write_progress(
            workspace_dir,
            stages,
            0,
            "正在扫描工作区中的 PDF / DOC / DOCX / TXT 论文文件（第 {0}/{1} 次）。".format(attempt, len(retry_delays)),
            {"attempt": attempt, "max_attempts": len(retry_delays)},
        )
        last_result = subprocess.run(normalize_cmd, capture_output=True, text=True)
        if last_result.returncode == 0:
            return last_result
    return last_result


def main():
    parser = argparse.ArgumentParser(description="Run the Xiaohongshu pipeline end-to-end.")
    parser.add_argument("--workspace", default=".", help="Workspace directory.")
    parser.add_argument("--input", default="", help="Optional path to parsed-paper.json.")
    parser.add_argument("--output-dir", required=True, help="Directory for generated files.")
    parser.add_argument("--python", default=sys.executable, help="Python executable path.")
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parent
    workspace_dir = Path(args.workspace).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    parsed_input = Path(args.input).resolve() if args.input else (output_dir / "parsed-paper.json").resolve()

    stages = [
        "定位并规范化上传论文",
        "解析论文结构化内容",
        "生成小红书图文方案",
        "导出卡片图片与 DOCX",
        "生成预览页",
        "整理最终交付结果",
    ]

    write_progress(workspace_dir, stages, 0, "开始处理上传论文，准备生成小红书图文包。")

    if not parsed_input.exists():
        write_progress(workspace_dir, stages, 0, "尚未发现解析结果，先执行论文定位与规范化。")
        normalize_result = run_normalization_with_retry(args, skill_dir, workspace_dir, output_dir, stages)
        if normalize_result.returncode != 0:
            reason = normalize_result.stderr.strip() or normalize_result.stdout.strip() or "当前工作区中未检测到可用论文文件。"
            write_progress(workspace_dir, stages, 0, "未检测到论文文件，正在写入缺失上传诊断报告。", {"error": reason})
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
        parse_cmd = [
            args.python,
            str(skill_dir / "parse_paper.py"),
            "--input",
            str(output_dir / "workspace-inputs.json"),
            "--output-dir",
            str(output_dir),
        ]
        write_progress(workspace_dir, stages, 1, "已找到论文文件，正在提取标题、摘要、正文与章节信息。")
        subprocess.run(parse_cmd, check=True)
        parsed_input = output_dir / "parsed-paper.json"

    write_progress(workspace_dir, stages, 2, "正在生成适合小红书发布的图文文案和卡片结构。", {"input": str(parsed_input)})
    package_cmd = [
        args.python,
        str(skill_dir / "build_xhs_package.py"),
        "--input",
        str(parsed_input),
        "--output-dir",
        str(output_dir),
    ]
    subprocess.run(package_cmd, check=True)

    export_cmd = [
        args.python,
        str(skill_dir / "render_article_exports.py"),
        "--input",
        str(output_dir / "xiaohongshu-package.json"),
        "--output-dir",
        str(output_dir),
    ]
    write_progress(
        workspace_dir,
        stages,
        3,
        "正在导出 DOCX 总说明，并生成可直接保存发布的小红书卡片图片。",
        {
            "docx": str(output_dir / "xiaohongshu-package.docx"),
            "images_dir": str(output_dir / "xiaohongshu-images"),
        },
    )
    subprocess.run(export_cmd, check=True)

    preview_cmd = [
        args.python,
        str(skill_dir / "build_xhs_preview_page.py"),
        "--input",
        str(output_dir / "xiaohongshu-package.json"),
        "--output",
        str(output_dir / "xiaohongshu-preview.html"),
    ]
    write_progress(
        workspace_dir,
        stages,
        4,
        "卡片图片和 DOCX 已生成，正在构建可直接查看的预览页。",
        {
            "preview_html": str(output_dir / "xiaohongshu-preview.html"),
            "images_dir": str(output_dir / "xiaohongshu-images"),
        },
    )
    subprocess.run(preview_cmd, check=True)

    report_cmd = [
        args.python,
        str(skill_dir / "build_final_report.py"),
        "--output-dir",
        str(output_dir),
    ]
    write_progress(workspace_dir, stages, 5, "正在整理最终交付内容。")
    subprocess.run(report_cmd, check=True)

    write_progress(
        workspace_dir,
        stages,
        len(stages),
        "小红书图文包已经生成完成，预览页、卡片图片、DOCX 和最终回复内容均已就绪。",
        {
            "preview_html": str(output_dir / "xiaohongshu-preview.html"),
            "markdown": str(output_dir / "xiaohongshu-post.md"),
            "docx": str(output_dir / "xiaohongshu-package.docx"),
            "images_dir": str(output_dir / "xiaohongshu-images"),
            "package": str(output_dir / "xiaohongshu-package.json"),
            "final_report": str(output_dir / "final-response.json"),
        },
    )
    print(str(output_dir / "final-response.json"))


if __name__ == "__main__":
    main()
