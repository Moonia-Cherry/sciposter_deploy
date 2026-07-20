#!/usr/bin/env python
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build the final response payload for the group-meeting slides workflow.")
    parser.add_argument("--output-dir", required=True, help="Output directory containing generated files.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    report_json = output_dir / "final-response.json"
    report_md = output_dir / "final-response.md"
    package_path = output_dir / "slides-package.json"
    package = {}
    if package_path.exists():
        package = json.loads(package_path.read_text(encoding="utf-8"))

    payload = {
        "status": "ok",
        "message": "组会 PPT 已生成完成。",
        "downloads": [
            {"label": "slides.pptx", "path": "./slides.pptx"},
            {"label": "slides-preview.html", "path": "./slides-preview.html"},
            {"label": "slides-preview.png", "path": "./slides-preview.png"},
            {"label": "slides-outline.md", "path": "./slides-outline.md"},
            {"label": "speaker-notes.md", "path": "./speaker-notes.md"},
            {"label": "figure-plan.md", "path": "./figure-plan.md"},
            {"label": "discussion-questions.md", "path": "./discussion-questions.md"},
        ],
        "preview_image": "./slides-preview.png",
        "preview_html": "./slides-preview.html",
        "slide_count": len(package.get("slides", []) or []),
        "recommended_reply": "组会 PPT 和预览文件已经准备完成。右侧的 slides-preview.png 是整套缩略总览，逐页查看请打开 slides-preview.html，再下载 slides.pptx 继续编辑。",
    }

    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 组会 PPT 已完成",
        "",
        "![Slides Preview](./slides-preview.png)",
        "",
        "当前共生成 {0} 页。".format(payload["slide_count"]),
        "",
        "- [打开逐页预览页面](./slides-preview.html)",
        "- [下载可编辑 PPTX](./slides.pptx)",
        "- [查看大纲](./slides-outline.md)",
        "- [查看讲稿备注](./speaker-notes.md)",
        "- [查看配图建议](./figure-plan.md)",
        "- [查看讨论问题](./discussion-questions.md)",
    ]
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(report_json))


if __name__ == "__main__":
    main()
