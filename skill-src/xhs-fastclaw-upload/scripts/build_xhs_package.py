#!/usr/bin/env python
import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def split_sentences(text: str) -> List[str]:
    normalized = clean(text)
    if not normalized:
        return []
    parts = re.split(r"(?<=[。！？!?\.])\s*|[；;]\s*", normalized)
    return [clean(item) for item in parts if clean(item)]


def truncate(text: str, limit: int = 90) -> str:
    value = clean(text)
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip(" ，。；;,:：") + "..."


def unique_items(items: List[str], limit: int, max_len: int) -> List[str]:
    result: List[str] = []
    seen = set()
    for raw in items:
        item = truncate(raw, max_len)
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


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
            name = Path(info.filename).name
            if name.lower() == "media":
                continue
            target = asset_dir / name
            with archive.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            saved.append(target.name)
            if len(saved) >= 8:
                return saved
    return saved


def extract_paper_assets(parsed_paper: dict, output_dir: Path) -> Dict:
    source_path = parsed_paper.get("source_path", "")
    if not source_path:
        return {"images": [], "note": "未提供论文源文件路径，暂时无法自动提取论文配图。"}

    source = Path(source_path)
    if not source.exists():
        return {"images": [], "note": "论文源文件不存在，暂时无法自动提取论文配图。"}

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
        return {"images": images, "note": "已从论文中提取到可用图片，封面或结果页会优先使用这些素材。"}
    return {"images": [], "note": "论文中没有检测到可直接提取的图片，将使用知识卡片版式完成图文生成。"}


def extract_fact(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return clean(match.group(1)) if match else ""


def extract_metric_value(text: str, keyword: str) -> str:
    patterns = [
        rf"取得\s*([0-9]+\.[0-9]+)\s*的\s*{keyword}",
        rf"([0-9]+\.[0-9]+)\s*的\s*{keyword}",
        rf"{keyword}[^\d]*([0-9]+\.[0-9]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean(match.group(1))
    return ""


def extract_facts(parsed: dict) -> dict:
    text = "\n".join(
        [
            clean(parsed.get("title", "")),
            clean(parsed.get("abstract", "")),
            clean(parsed.get("body_excerpt", "")),
        ]
    )
    lowered = text.lower()

    facts = {
        "dataset": "",
        "horizon": "",
        "features": "",
        "risk_levels": "",
        "best_model": "",
        "accuracy": "",
        "balanced_accuracy": "",
        "macro_f1": "",
        "pollutants": "",
        "task": "",
        "value": "",
    }

    if "uci" in lowered and ("空气质量" in text or "airqualityuci" in lowered):
        facts["dataset"] = "UCI 马德里空气质量数据集"
    elif "uci" in lowered:
        facts["dataset"] = "UCI 数据集"

    horizon = extract_fact(r"未来\s*([0-9]+)\s*小时", text) or extract_fact(r"([0-9]+)\s*小时风险预测", text)
    if horizon:
        facts["horizon"] = f"未来 {horizon} 小时"

    features = extract_fact(r"构建\s*([0-9]+)\s*个时序特征", text) or extract_fact(r"生成\s*([0-9]+)\s*个.*?特征", text)
    if features:
        facts["features"] = f"{features} 个时序特征"

    if "四级风险" in text or "四类风险" in text or "四级标签" in text:
        facts["risk_levels"] = "四级风险标签"

    if "直方图梯度提升" in text:
        facts["best_model"] = "直方图梯度提升模型"
    elif "histgradientboosting" in lowered:
        facts["best_model"] = "HistGradientBoosting"
    elif "随机森林" in text:
        facts["best_model"] = "随机森林"

    facts["accuracy"] = extract_metric_value(text, "准确率") or extract_metric_value(text, "Accuracy")
    facts["balanced_accuracy"] = extract_metric_value(text, "平衡准确率") or extract_metric_value(text, "Balanced Accuracy")
    facts["macro_f1"] = extract_metric_value(text, "Macro-F1")

    pollutant_tokens = []
    for token in ["CO", "NO2", "NOx", "C6H6", "PM2.5", "PM10", "O3", "SO2"]:
        if token.lower() in lowered:
            pollutant_tokens.append(token)
    if pollutant_tokens:
        facts["pollutants"] = "、".join(pollutant_tokens[:4])

    if facts["dataset"] and facts["horizon"]:
        facts["task"] = f"基于 {facts['dataset']} 做 {facts['horizon']} 风险预测"
    elif facts["horizon"]:
        facts["task"] = f"做 {facts['horizon']} 风险预测"
    else:
        facts["task"] = "把论文任务讲清楚"

    if facts["best_model"] and facts["balanced_accuracy"]:
        facts["value"] = f"{facts['best_model']} 综合表现最好，平衡准确率 {facts['balanced_accuracy']}"
    elif facts["best_model"]:
        facts["value"] = f"{facts['best_model']} 是论文里表现最好的模型"
    else:
        facts["value"] = "重点是把研究问题、方法和结果讲清楚"

    return facts


def metric_text(facts: dict) -> str:
    chunks = []
    if facts.get("accuracy"):
        chunks.append(f"Accuracy {facts['accuracy']}")
    if facts.get("balanced_accuracy"):
        chunks.append(f"Balanced Accuracy {facts['balanced_accuracy']}")
    if facts.get("macro_f1"):
        chunks.append(f"Macro-F1 {facts['macro_f1']}")
    return " / ".join(chunks)


def build_short_title(title: str, facts: dict) -> str:
    if facts.get("horizon"):
        compact_horizon = facts["horizon"].replace("未来 ", "").replace(" ", "")
        return f"空气质量{compact_horizon}风险预测怎么做？"
    if "风险预测" in title:
        return "一篇论文讲清风险预测怎么做"
    return truncate(title or "这篇论文到底讲了什么？", 24)


def build_summary(parsed: dict, facts: dict) -> str:
    chunks = []
    if facts.get("dataset"):
        chunks.append(f"论文把 {facts['dataset']} 重新组织成更贴近真实场景的时序预测任务")
    if facts.get("horizon"):
        chunks.append(f"核心目标不是判断当前空气好不好，而是提前预测{facts['horizon']}的综合污染风险")
    if facts.get("best_model"):
        chunks.append(f"结果上 {facts['best_model']} 的综合表现最好")
    if facts.get("balanced_accuracy"):
        chunks.append(f"平衡准确率达到 {facts['balanced_accuracy']}")
    if not chunks:
        sentences = split_sentences(parsed.get("abstract", "") or parsed.get("body_excerpt", ""))
        return truncate("；".join(sentences[:2]), 110)
    return truncate("；".join(chunks), 110)


def build_post_paragraphs(facts: dict) -> List[str]:
    dataset = facts.get("dataset") or "这份公开数据集"
    horizon = facts.get("horizon") or "未来短时"
    features = facts.get("features") or "多维时序特征"
    risk_levels = facts.get("risk_levels") or "分级风险标签"
    best_model = facts.get("best_model") or "表现最好的模型"
    metrics = metric_text(facts)

    paragraphs = [
        f"这篇论文最有意思的地方，不是单纯比了几种模型，而是把 {dataset} 从“静态分类练习”改造成了更合理的时序风险预测任务。",
        f"作者真正想回答的问题是：能不能利用历史监测序列，提前预测 {horizon} 的综合污染风险，而不是只看当前时刻是否超标。",
        f"方法上，论文先完成数据清洗，再围绕污染物、传感器和气象变量构建 {features}，并据此定义 {risk_levels}，让建模逻辑和真实预警场景保持一致。",
        f"结果部分最值得记住的是：{best_model} 的综合表现最好。{metrics if metrics else '论文强调它在多种传统机器学习模型对比中胜出。'}",
        "如果把它当成一篇适合拆解的科研内容，它的价值就在于：研究问题明确、方法链路完整、结果也能解释为什么这样建模更合理。",
    ]
    return unique_items(paragraphs, 5, 130)


def build_cards(parsed: dict, facts: dict) -> List[dict]:
    dataset = facts.get("dataset") or "公开空气质量数据集"
    horizon = facts.get("horizon") or "未来短时"
    features = facts.get("features") or "多维时序特征"
    risk_levels = facts.get("risk_levels") or "分级风险标签"
    best_model = facts.get("best_model") or "综合表现最好的模型"
    pollutants = facts.get("pollutants") or "多污染物联合信息"
    metrics = metric_text(facts) or "论文报告了准确率、平衡准确率和 Macro-F1 等综合指标"

    return [
        {
            "kind": "cover",
            "title": build_short_title(parsed.get("title", ""), facts),
            "subtitle": "把论文内容拆成可直接发布的小红书知识卡片",
            "body": [build_summary(parsed, facts)],
        },
        {
            "kind": "intro",
            "title": "这篇论文到底在研究什么？",
            "lead": "先别急着看模型，先把研究问题讲明白。",
            "paragraphs": [
                f"这篇论文不是简单判断某一时刻的空气质量，而是基于 {dataset} 重新定义了一个更真实的预测任务。",
                f"作者关注的是：能不能利用历史监测序列，提前预测 {horizon} 的综合污染风险。",
                "这一步很关键，因为它把“科研任务怎么定义”这件事先做对了，后面的模型比较才有意义。",
            ],
            "quote": "重点不是做一个分类器，而是把公开数据改造成真正合理的时序预测任务。",
            "note": "读者先理解研究问题，再看方法和结果，会更容易跟上整篇论文。",
        },
        {
            "kind": "bullet_explain",
            "title": "01 研究对象",
            "lead": "这一页回答三个问题：研究什么、预测什么、为什么重要。",
            "bullets": [
                {"term": "数据", "desc": f"论文使用的是 {dataset}，研究对象是 {pollutants} 等空气污染相关变量。"},
                {"term": "目标", "desc": f"模型不是看当前时刻，而是提前预测 {horizon} 的综合污染风险。"},
                {"term": "意义", "desc": "这样的设定更贴近真实预警场景，也能避免把未来信息提前泄露给模型。"},
            ],
        },
        {
            "kind": "bullet_explain",
            "title": "02 方法设计",
            "lead": "这篇论文的方法亮点，不只是哪种模型，而是整条研究流程搭得比较完整。",
            "bullets": [
                {"term": "清洗", "desc": "先处理缺失值和高缺失变量，尽量保留连续时序数据，保证后续建模能稳定进行。"},
                {"term": "特征", "desc": f"围绕污染物、传感器和气象变量构建 {features}，把时间依赖关系显式放进特征里。"},
                {"term": "标签", "desc": f"再根据未来窗口的污染水平构造 {risk_levels}，让标签和预测任务真正对齐。"},
            ],
        },
        {
            "kind": "insight",
            "title": "03 核心结果",
            "lead": "结果页最重要的，不是“跑了很多模型”，而是哪一个结论真正站得住。",
            "paragraphs": [
                f"论文在多种传统机器学习模型之间做了系统比较，最后 {best_model} 的综合表现最好。",
                f"关键指标可以记成一句话：{metrics}。",
                "这说明把多污染物联合信息和时序结构一起纳入建模，确实比静态分类思路更接近真实风险演化过程。",
            ],
            "callout": "如果只记一个结论，那就是：任务定义做对了，结果才更可信。",
        },
        {
            "kind": "bullet_explain",
            "title": "04 这篇论文的亮点",
            "lead": "适合传播的亮点，不需要铺太满，抓住三件事就够了。",
            "bullets": [
                {"term": "亮点1", "desc": "把公开数据集从课堂式静态分类，改造成更严谨的时序风险预测任务。"},
                {"term": "亮点2", "desc": f"通过 {features} 和 {risk_levels}，把研究问题、特征工程和标签定义连成一条完整链路。"},
                {"term": "亮点3", "desc": "最终结果不仅有最优模型，还能解释为什么这种建模方式更适合真实预警场景。"},
            ],
        },
        {
            "kind": "bullet_explain",
            "title": "05 我们该怎么理解它",
            "lead": "这页不是复述结果，而是告诉读者这篇论文值不值得看。",
            "bullets": [
                {"term": "教学", "desc": "它是一个很好的课程论文示例，展示了如何把公开数据集做成逻辑完整的时序研究。"},
                {"term": "应用", "desc": "如果后续接入更多城市、站点或实时数据流，这套思路可以继续扩展到短时空气污染预警。"},
                {"term": "边界", "desc": "它更像一个方法框架和研究样板，不是已经落地的工业级系统。"},
            ],
        },
        {
            "kind": "ending",
            "title": "一句话怎么总结？",
            "lead": "最后一页要把价值讲完整，也给评论区留下讨论空间。",
            "paragraphs": [
                f"一句话概括：这篇论文把 {dataset} 从静态分类练习，升级成了更贴近真实业务的 {horizon} 风险预测任务。",
                "如果把这套时序建模思路迁移到更多城市或更多监测站点，你觉得最先该验证哪一步？这个问题很适合继续讨论。",
            ],
        },
    ]


def attach_card_visuals(cards: List[dict], asset_images: List[str]) -> List[dict]:
    if not asset_images:
        return cards
    for idx, card in enumerate(cards):
        card["visual_image"] = asset_images[min(idx, len(asset_images) - 1)]
    return cards


def build_cover_meta(parsed: dict, facts: dict) -> dict:
    text_length = int(parsed.get("text_length") or 0)
    meta_parts = []
    if facts.get("dataset"):
        meta_parts.append(facts["dataset"])
    if facts.get("horizon"):
        meta_parts.append(facts["horizon"])
    if facts.get("features"):
        meta_parts.append(facts["features"])
    meta_tail = " / ".join(meta_parts[:3]) if meta_parts else "论文图文化输出"

    return {
        "cover_title": build_short_title(parsed.get("title", ""), facts),
        "cover_subtitle": "把论文内容讲成适合直接发布的小红书图文",
        "badge_left": "论文拆解",
        "badge_right": "适合收藏复习",
        "summary": build_summary(parsed, facts),
        "meta_line": f"全文约 {max(text_length // 2, 1200)} 字 / 预计阅读 {10 if text_length > 7000 else 8} 分钟 / {meta_tail}",
    }


def write_text(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Xiaohongshu package from parsed paper JSON.")
    parser.add_argument("--input", required=True, help="Path to parsed-paper.json.")
    parser.add_argument("--output-dir", required=True, help="Directory for generated files.")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    parsed = json.loads(input_path.read_text(encoding="utf-8"))
    assets = extract_paper_assets(parsed, output_dir)
    facts = extract_facts(parsed)

    paper_title = clean(parsed.get("title") or "未命名论文")
    cover_meta = build_cover_meta(parsed, facts)
    chosen_title = cover_meta["cover_title"]
    cards = build_cards(parsed, facts)
    cards = attach_card_visuals(cards, assets["images"])
    post_paragraphs = build_post_paragraphs(facts)
    post_copy = "\n\n".join(post_paragraphs)

    title_options = unique_items(
        [
            chosen_title,
            "空气质量时序风险预测怎么做？",
            "一篇论文讲清空气质量风险预测",
            "公开数据集也能做出完整时序研究吗？",
            "把论文讲成能直接发的小红书图文",
        ],
        5,
        28,
    )

    hashtags = unique_items(
        [
            "#论文解读",
            "#空气质量",
            "#时序预测",
            "#机器学习",
            "#科研科普",
            "#小红书图文",
            "#数据分析",
        ],
        7,
        18,
    )

    pinned_comment = "如果把这套时序风险预测思路迁移到更多城市或更多监测站点，你觉得最先该补哪一步？欢迎一起讨论。"

    write_text(
        output_dir / "title-options.md",
        "# 标题备选\n\n" + "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(title_options)),
    )

    cover_copy = "\n".join(
        [
            "## 封面标题",
            chosen_title,
            "",
            "## 封面副标题",
            cover_meta["cover_subtitle"],
            "",
            "## 封面摘要",
            cover_meta["summary"],
            "",
            "## 元信息",
            cover_meta["meta_line"],
        ]
    )
    write_text(output_dir / "cover-copy.md", cover_copy)

    card_blocks = []
    for card in cards:
        card_blocks.append(f"## {card['title']}")
        if card.get("lead"):
            card_blocks.append(card["lead"])
        for paragraph in card.get("paragraphs", []):
            card_blocks.append(f"- {paragraph}")
        for bullet in card.get("bullets", []):
            card_blocks.append(f"- {bullet['term']}：{bullet['desc']}")
        if card.get("callout"):
            card_blocks.append(f"- 强调：{card['callout']}")
        card_blocks.append("")
    write_text(output_dir / "carousel-cards.md", "# 小红书卡片文案\n\n" + "\n".join(card_blocks))

    write_text(output_dir / "hashtags.md", "\n".join(["## 推荐标签", " ".join(hashtags)]))

    post_markdown_lines = [f"# {chosen_title}", ""]
    post_markdown_lines.extend(post_paragraphs)
    post_markdown_lines.append("")
    write_text(output_dir / "xiaohongshu-post.md", "\n".join(post_markdown_lines))

    package_payload = {
        "paper_title": paper_title,
        "chosen_title": chosen_title,
        "title": chosen_title,
        "summary": truncate(cover_meta["summary"], 120),
        "post_copy": post_copy,
        "pinned_comment": pinned_comment,
        "cover_copy": cover_copy,
        "title_options": title_options,
        "hashtags": hashtags,
        "cards": cards,
        "cover_meta": cover_meta,
        "asset_images": assets["images"],
        "asset_note": assets["note"],
        "next_steps": [
            "优先确认封面标题是否足够短，确保手机端第一屏就能看清。",
            "如果论文里有清晰原图，可以优先替换到封面或结果页里。",
            "发布前通读每张卡片，确认语气统一、适合移动端阅读。",
        ],
    }
    package_path = output_dir / "xiaohongshu-package.json"
    package_path.write_text(json.dumps(package_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result_payload = {
        "summary": package_payload["summary"],
        "outline": [card["title"] for card in cards],
        "assets": {
            "figures": [card.get("title", "") for card in cards],
            "paper_images": assets["images"],
        },
        "deliverables": [
            {"name": "title-options.md", "format": "markdown", "content": (output_dir / "title-options.md").read_text(encoding="utf-8")},
            {"name": "cover-copy.md", "format": "markdown", "content": (output_dir / "cover-copy.md").read_text(encoding="utf-8")},
            {"name": "carousel-cards.md", "format": "markdown", "content": (output_dir / "carousel-cards.md").read_text(encoding="utf-8")},
            {"name": "hashtags.md", "format": "markdown", "content": (output_dir / "hashtags.md").read_text(encoding="utf-8")},
            {"name": "xiaohongshu-post.md", "format": "markdown", "content": (output_dir / "xiaohongshu-post.md").read_text(encoding="utf-8")},
        ],
        "nextSteps": package_payload["next_steps"],
    }
    result_path = output_dir / "xiaohongshu-result.json"
    result_path.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(result_path))


if __name__ == "__main__":
    main()
