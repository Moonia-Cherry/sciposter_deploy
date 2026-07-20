#!/usr/bin/env python
import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    package_path = output_dir / "xiaohongshu-package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))

    image_names = package.get("generated_images", []) or []
    image_links = [{"label": name, "path": f"./xiaohongshu-images/{name}"} for name in image_names]

    report = {
        "status": "ok",
        "summary": f"已完成《{package.get('paper_title', '') or package.get('chosen_title', '小红书图文方案')}》的小红书图文包生成。",
        "copy_ready": {
            "title": package.get("chosen_title", ""),
            "post_copy": package.get("post_copy", package.get("summary", "")),
            "hashtags": package.get("hashtags", []),
            "pinned_comment": package.get("pinned_comment", ""),
        },
        "docx": {
            "label": "xiaohongshu-package.docx",
            "path": "./xiaohongshu-package.docx",
        },
        "cards": image_links,
        "preview": {
            "label": "xiaohongshu-preview.html",
            "path": "./xiaohongshu-preview.html",
        },
        "recommended_reply": "卡片图片、预览页和 DOCX 都已经生成完成，直接使用本地结果即可，不需要再让模型重新改写一遍。",
    }

    (output_dir / "final-response.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 小红书图文包已完成",
        "",
        report["summary"],
        "",
        "## 可直接复制",
        "",
        f"标题：{report['copy_ready']['title']}",
        "",
        "正文：",
        report["copy_ready"]["post_copy"],
        "",
        "标签：",
        " ".join(report["copy_ready"]["hashtags"]),
        "",
        "置顶评论：",
        report["copy_ready"]["pinned_comment"],
        "",
        f"- [打开 DOCX 总说明]({report['docx']['path']})",
        f"- [打开预览页]({report['preview']['path']})",
    ]
    lines.extend(f"- [打开 {item['label']}]({item['path']})" for item in image_links)

    (output_dir / "final-response.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(output_dir / "final-response.json"))


if __name__ == "__main__":
    main()
