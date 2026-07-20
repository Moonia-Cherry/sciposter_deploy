#!/usr/bin/env python
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    package_path = output_dir / "popular-article-package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))

    report = {
        "status": "ok",
        "summary": f"微信公众号文章已生成完成，标题为《{package.get('title', '')}》，预览页、正文导出和公众号头图均已准备完成。",
        "deliverables": [
            str(output_dir / "popular-article-preview.html"),
            str(output_dir / "popular-article.md"),
            str(output_dir / "popular-article.docx"),
            str(output_dir / "popular-article.pdf"),
            str(output_dir / "wechat-cover.png"),
            str(output_dir / "wechat-cover.pptx"),
            str(output_dir / "article-title-options.md"),
            str(output_dir / "chart-briefs.md"),
            str(output_dir / "animation-briefs.md"),
            str(output_dir / "popular-article-package.json"),
        ],
        "has_extracted_assets": bool(package.get("asset_images")),
        "next_steps": package.get("next_steps", []),
    }

    (output_dir / "final-response.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "final-response.md").write_text(
        "\n".join(
            [
                "# 微信公众号文章已完成",
                "",
                report["summary"],
                "",
                "## 交付文件",
                *[f"- {item}" for item in report["deliverables"]],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(str(output_dir / "final-response.json"))


if __name__ == "__main__":
    main()
