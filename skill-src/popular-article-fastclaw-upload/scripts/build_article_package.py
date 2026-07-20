#!/usr/bin/env python
import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List


def normalize_sentence(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def split_sentences(text: str) -> List[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?。！？])\s+", normalize_sentence(text)) if item.strip()]


def truncate(text: str, limit: int = 140) -> str:
    text = normalize_sentence(text)
    return text if len(text) <= limit else f"{text[: limit - 3].rstrip()}..."


def parse_pdf_images(source_path: Path, asset_dir: Path) -> List[str]:
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(str(source_path))
    saved = []
    for page_index, page in enumerate(reader.pages):
        for image_index, image_file in enumerate(getattr(page, "images", [])):
            suffix = Path(image_file.name).suffix or ".png"
            target = asset_dir / f"page-{page_index + 1:02d}-image-{image_index + 1:02d}{suffix}"
            target.write_bytes(image_file.data)
            saved.append(target.name)
            if len(saved) >= 8:
                return saved
    return saved


def parse_docx_images(source_path: Path, asset_dir: Path) -> List[str]:
    saved = []
    with zipfile.ZipFile(source_path) as archive:
        for info in archive.infolist():
            if not info.filename.startswith("word/media/"):
                continue
            target = asset_dir / Path(info.filename).name
            with archive.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            saved.append(target.name)
            if len(saved) >= 8:
                return saved
    return saved


def extract_paper_assets(parsed_paper: Dict, output_dir: Path) -> Dict:
    source_path = parsed_paper.get("source_path", "")
    if not source_path:
        return {"images": [], "note": "未提供论文源文件路径，暂时无法自动提取论文配图。"}

    source = Path(source_path)
    if not source.exists():
        return {"images": [], "note": f"论文源文件不存在：{source_path}"}

    asset_dir = output_dir / "extracted-paper-assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    try:
        if source.suffix.lower() == ".pdf":
            images = parse_pdf_images(source, asset_dir)
        elif source.suffix.lower() in {".docx", ".doc"}:
            images = parse_docx_images(source, asset_dir)
        else:
            images = []
    except Exception as exc:
        return {"images": [], "note": f"论文配图提取失败：{exc}"}

    if images:
        return {"images": images, "note": "已从论文中提取可用配图，预览页和导出文档会优先使用这些图片。"}
    return {"images": [], "note": "论文中未发现可直接提取的内嵌图片，当前仍可生成成稿与预览。"}


def build_sections(parsed_paper: Dict) -> List[Dict]:
    abstract_text = normalize_sentence(parsed_paper.get("abstract", ""))
    body_excerpt = normalize_sentence(parsed_paper.get("body_excerpt", ""))
    sections = parsed_paper.get("sections", {}) or {}
    highlights = parsed_paper.get("highlights", []) or []
    abstract_sentences = split_sentences(abstract_text or body_excerpt)

    research_problem = abstract_sentences[0] if abstract_sentences else "这篇论文围绕一个明确的研究问题展开，适合改写成可传播的公众号文章。"
    method = normalize_sentence(sections.get("method")) or (abstract_sentences[1] if len(abstract_sentences) > 1 else "作者通过建模、实验或对比分析来回答研究问题。")
    results = normalize_sentence(sections.get("results")) or (abstract_sentences[2] if len(abstract_sentences) > 2 else "论文给出了关键实验结果，用来说明方法有效且具有实际意义。")
    conclusion = normalize_sentence(sections.get("conclusion") or sections.get("discussion")) or "论文的主要价值在于，把抽象研究问题转化为可验证、可解释的研究结论。"

    innovation_points = [truncate(item, 90) for item in highlights[:3]] or [
        "研究问题切得比较清晰，容易向非专业读者解释“为什么值得做”。",
        "方法部分有清晰的研究路径，适合做成流程图或机制图。",
        "实验结果具备转写成“结论 + 意义”的传播基础。",
    ]

    return [
        {
            "heading": "这篇论文到底在研究什么",
            "paragraphs": [
                f"先把问题说人话：{truncate(research_problem, 110)}",
                "如果公众号文章一开始就堆专业术语，读者很容易退出。所以更好的写法是，先把研究对象、现实困境和作者试图解决的问题讲清楚。",
            ],
        },
        {
            "heading": "作者具体是怎么做的",
            "paragraphs": [
                truncate(method, 180),
                "对于非专业读者，可以把这一部分理解成一条研究流程：先定义问题，再设计方法，最后用实验或案例去验证结论是否站得住。",
            ],
        },
        {
            "heading": "最值得记住的三个亮点",
            "paragraphs": [f"{idx + 1}. {point}" for idx, point in enumerate(innovation_points)],
        },
        {
            "heading": "结果说明了什么",
            "paragraphs": [
                truncate(results, 180),
                truncate(conclusion, 160),
                "公众号表达上，不建议只堆指标。更适合的做法是先解释“这个结果意味着什么”，再说明“为什么它对行业、社会或普通人有意义”。",
            ],
        },
        {
            "heading": "如果把它发成一篇公众号文章",
            "paragraphs": [
                "建议采用“问题切入 - 方法拆解 - 结果解释 - 现实意义”这条叙事线，让读者能顺着读下去，而不是像读论文摘要那样吃力。",
                "配图优先使用论文原图中的方法框架图、结果对比图、示意图；如果原图太复杂，可以在预览中保留原图，在正式发布时裁剪局部并补一句中文解释。",
            ],
        },
    ]


def write_markdown_files(output_dir: Path, title: str, sections: List[Dict], summary: str) -> None:
    article_lines = [f"# {title}", "", summary, ""]
    for section in sections:
        article_lines.append(f"## {section['heading']}")
        article_lines.append("")
        article_lines.extend(section["paragraphs"])
        article_lines.append("")
    (output_dir / "popular-article.md").write_text("\n".join(article_lines).strip() + "\n", encoding="utf-8")

    title_options = [
        f"这篇论文到底解决了什么问题？一文读懂《{title}》",
        f"把论文讲明白：{truncate(title, 26)}",
        f"适合公众号发布的论文解读：{truncate(title, 24)}",
        f"{truncate(title, 22)}，它真正的价值在哪里？",
        "从研究问题到实验结论，快速读懂这篇论文",
    ]
    (output_dir / "article-title-options.md").write_text(
        "# 标题备选\n\n" + "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(title_options)) + "\n",
        encoding="utf-8",
    )

    (output_dir / "chart-briefs.md").write_text(
        "\n".join(
            [
                "# 配图建议",
                "",
                "## 1. 问题与研究路径图",
                "- 用一张流程图说明研究背景、作者方法、实验验证和结论之间的关系。",
                "",
                "## 2. 关键结果对比图",
                "- 如论文中有指标提升，优先直接截取原论文结果图，并补一句通俗解释。",
                "",
                "## 3. 方法框架图简化版",
                "- 适合从论文原图里裁出关键模块，减少复杂小字，强调读者可读性。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (output_dir / "animation-briefs.md").write_text(
        "\n".join(
            [
                "# 动效建议",
                "",
                "- 头图可做轻微渐变和卡片浮层，不建议复杂炫技动画。",
                "- 若做 H5 预览，可让“研究问题 -> 方法 -> 结果”三段依次出现。",
                "- 图片建议仍以论文原图为主，保证正式发布时加载稳定。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build_package(parsed_paper: Dict, assets: Dict) -> Dict:
    title = parsed_paper.get("title", "未命名论文")
    sections = build_sections(parsed_paper)
    summary = truncate(
        parsed_paper.get("abstract") or parsed_paper.get("body_excerpt") or "这篇论文适合整理成一篇兼顾信息密度和可读性的公众号文章。",
        180,
    )
    return {
        "title": title,
        "summary": summary,
        "sections": sections,
        "asset_note": assets["note"],
        "asset_images": assets["images"],
        "source_path": parsed_paper.get("source_path", ""),
        "next_steps": [
            "检查 extracted-paper-assets 中的图片是否适合直接用于公众号正文。",
            "如果论文原图文字过小，建议裁剪局部并加一行中文解释。",
            "如果需要更强的公众号风格，可以继续在当前结构上润色导语和结尾。",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Build a popular article package from parsed paper JSON.")
    parser.add_argument("--input", required=True, help="Path to parsed-paper.json.")
    parser.add_argument("--output-dir", required=True, help="Directory for generated files.")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    parsed_paper = json.loads(input_path.read_text(encoding="utf-8"))
    assets = extract_paper_assets(parsed_paper, output_dir)
    package = build_package(parsed_paper, assets)
    write_markdown_files(output_dir, package["title"], package["sections"], package["summary"])

    package_path = output_dir / "popular-article-package.json"
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(package_path))


if __name__ == "__main__":
    main()
