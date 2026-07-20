#!/usr/bin/env python
import argparse
import json
from pathlib import Path


def first_items(items, limit):
    out = []
    for item in items or []:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def main():
    parser = argparse.ArgumentParser(description="Summarize parsed paper metadata for FastClaw inspection flows.")
    parser.add_argument("--input", required=True, help="Path to parsed-paper.json")
    parser.add_argument("--output", default="", help="Optional output markdown path")
    args = parser.parse_args()

    parsed = json.loads(Path(args.input).read_text(encoding="utf-8"))
    title = str(parsed.get("title") or "").strip() or "未识别到明确标题"
    abstract = str(parsed.get("abstract") or "").strip() or "未识别到明确摘要"
    highlights = first_items(parsed.get("highlights") or [], 3)
    if not highlights:
        body = str(parsed.get("body_excerpt") or "").strip()
        if body:
            chunks = [line.strip() for line in body.splitlines() if line.strip()]
            highlights = first_items(chunks, 3)
    if not highlights:
        highlights = ["未识别到明确核心结论", "建议补充更规范的论文正文结构", "可继续基于全文手动抽取研究贡献"]

    lines = [
        "# 论文检查结果",
        "",
        f"标题：{title}",
        "",
        "摘要：",
        abstract,
        "",
        "3条核心结论：",
    ]
    lines.extend([f"{idx + 1}. {item}" for idx, item in enumerate(highlights[:3])])
    text = "\n".join(lines).strip() + "\n"

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")

    print(text)


if __name__ == "__main__":
    main()
