#!/usr/bin/env python
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build a compact final report for FastClaw poster runs.")
    parser.add_argument("--output-dir", required=True, help="Output directory containing generated files.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    report_json = output_dir / "final-response.json"
    report_md = output_dir / "final-response.md"

    payload = {
        "status": "ok",
        "message": "学术海报已生成完成。",
        "downloads": [
            {"label": "academic-poster.pptx", "path": "./academic-poster.pptx"},
            {"label": "academic-poster.svg", "path": "./academic-poster.svg"},
            {"label": "academic-poster.png", "path": "./academic-poster.png"},
            {"label": "poster-preview.html", "path": "./poster-preview.html"},
            {"label": "poster-package.json", "path": "./poster-package.json"},
            {"label": "poster-spec.json", "path": "./poster-spec.json"},
        ],
        "recommended_reply": "海报文件已经准备完成，可以先打开 poster-preview.html 预览，再下载 academic-poster.pptx 继续编辑。",
    }

    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_md.write_text(
        "\n".join(
            [
                "# 学术海报已完成",
                "",
                "海报文件已经准备完成。",
                "",
                "- [academic-poster.pptx](./academic-poster.pptx)",
                "- [academic-poster.svg](./academic-poster.svg)",
                "- [academic-poster.png](./academic-poster.png)",
                "- [poster-preview.html](./poster-preview.html)",
                "- [poster-package.json](./poster-package.json)",
                "- [poster-spec.json](./poster-spec.json)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(str(report_json))


if __name__ == "__main__":
    main()
