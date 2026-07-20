#!/usr/bin/env python
import argparse
import json
import re
from pathlib import Path


TERM_MAP_ZH = {
    "graph neural networks": "图神经网络",
    "graph neural network": "图神经网络",
    "drug discovery": "药物发现",
    "air quality": "空气质量",
    "risk forecasting": "风险预测",
    "multi-pollutant": "多污染物",
    "time series": "时间序列",
    "city managers": "城市管理者",
    "hit rate": "命中率",
    "screening cost": "筛选成本",
    "molecules": "分子",
    "molecule": "分子",
    "atoms": "原子",
    "atom": "原子",
    "chemical bonds": "化学键",
    "chemical bond": "化学键",
    "false alarms": "误报",
    "accuracy": "准确率",
    "pipeline": "流程",
    "dataset": "数据集",
    "datasets": "数据集",
    "baseline": "基线方法",
    "baselines": "基线方法",
    "experiment": "实验",
    "experiments": "实验",
    "results": "结果",
    "method": "方法",
    "methods": "方法",
    "model": "模型",
    "models": "模型",
}


def clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def preprocess_text(text, title):
    value = str(text or "")
    for token in [
        title,
        "Abstract",
        "Introduction",
        "Conclusion",
        "Results",
        "Discussion",
        "Method",
        "Methods",
        "摘要",
        "引言",
        "结论",
        "结果",
        "讨论",
        "方法",
    ]:
        token = clean(token)
        if token:
            value = value.replace(token, " ")
    return clean(value)


def split_sentences(text):
    normalized = clean(text)
    if not normalized:
        return []
    parts = re.split(r"(?<=[。！？!?\.])\s+|[。！？!?]+", normalized)
    return [clean(part) for part in parts if clean(part)]


def trim_sentence(text, max_len):
    value = clean(text)
    if len(value) <= max_len:
        return value
    return value[: max_len - 3].rstrip(" ,;:") + "..."


def unique_points(items, limit, max_len, forbidden=None):
    forbidden_set = set()
    for item in forbidden or []:
        token = clean(item).lower()
        if token:
            forbidden_set.add(token)

    result = []
    seen = set()
    for raw in items:
        value = trim_sentence(raw, max_len)
        lowered = value.lower()
        if not value:
            continue
        if re.fullmatch(r"[0-9\.\-\s]+", value):
            continue
        if lowered in seen or lowered in forbidden_set:
            continue
        if len(value) < 6:
            continue
        seen.add(lowered)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def points_from_text(text, limit, max_len, forbidden=None):
    return unique_points(split_sentences(text), limit, max_len, forbidden=forbidden)


def detect_source_language(parsed):
    return parsed.get("language") or "zh-CN"


def normalize_output_language(language):
    value = str(language or "").strip().lower()
    if value.startswith("en"):
        return "en"
    return "zh-CN"


def is_zh(lang):
    return str(lang or "").lower().startswith("zh")


def t(lang, zh, en):
    return zh if is_zh(lang) else en


def replace_terms_zh(text):
    result = clean(text)
    for source, target in sorted(TERM_MAP_ZH.items(), key=lambda item: len(item[0]), reverse=True):
        result = re.sub(re.escape(source), target, result, flags=re.IGNORECASE)
    return result


def heuristic_translate_to_zh(text):
    value = replace_terms_zh(text)
    replacements = [
        (r"^this paper proposes ", "本文提出"),
        (r"^this study proposes ", "本研究提出"),
        (r"^this study models ", "本研究围绕"),
        (r"^we present ", "本文提出"),
        (r"^we propose ", "本文提出"),
        (r"^we build ", "本文构建"),
        (r"^we study whether ", "本文研究"),
        (r"^our results suggest that ", "结果表明"),
        (r"^results show that ", "结果表明"),
        (r"^the model represents ", "该模型将"),
        (r"^by learning ", "通过学习"),
        (r"^this process is ", "这一过程"),
        (r"^drug discovery often requires ", "药物发现通常需要"),
        (r"^air pollution forecasting helps ", "空气污染预测有助于"),
    ]
    for pattern, replacement in replacements:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    value = value.replace(" improves ", "提升")
    value = value.replace(" improve ", "提升")
    value = value.replace(" reduces ", "降低")
    value = value.replace(" reduce ", "降低")
    value = value.replace(" helps ", "帮助")
    value = value.replace(" using ", "，使用")
    value = value.replace(" based on ", "，基于")
    value = value.replace(" and ", "，并")
    value = value.replace(" or ", "或")
    return clean(value)


def localize_title_phrase(text, output_lang):
    value = clean(text)
    if not value:
        return "该研究"
    if not is_zh(output_lang):
        return value
    value = replace_terms_zh(value)
    match_for = re.match(r"(.+?)\s+for\s+(.+)", value, flags=re.IGNORECASE)
    if match_for:
        left = clean(match_for.group(1))
        right = clean(match_for.group(2))
        return "{0}中的{1}".format(right, left)
    match_with = re.match(r"(.+?)\s+with\s+(.+)", value, flags=re.IGNORECASE)
    if match_with:
        left = clean(match_with.group(1))
        right = clean(match_with.group(2))
        return "结合{1}的{0}".format(left, right)
    return value


def localize_point(text, output_lang):
    value = clean(text)
    if not value:
        return value
    if not is_zh(output_lang):
        return value
    if re.search(r"[\u4e00-\u9fff]", value):
        return value
    return heuristic_translate_to_zh(value)


def localize_points(items, output_lang, limit, max_len):
    localized = [trim_sentence(localize_point(item, output_lang), max_len) for item in items]
    return unique_points(localized, limit, max_len)


def pick_title(parsed):
    return clean(parsed.get("title") or "") or "Group Meeting Slides"


def compose_background_points(parsed, output_lang):
    if is_zh(output_lang) and not str(parsed.get("language", "")).lower().startswith("zh"):
        topic = localize_title_phrase(pick_title(parsed), output_lang)
        return [
            "论文聚焦“{0}”这一研究任务，核心是回应具体应用场景中的真实问题。".format(topic),
            "研究背景强调现有流程在效率、成本或准确性方面仍有改进空间。",
            "这一页汇报时建议先把任务场景讲清楚，再自然引到论文的研究目标。",
        ]
    sections = parsed.get("sections") or {}
    abstract = clean(parsed.get("abstract") or "")
    intro = clean(sections.get("introduction") or "")
    body = clean(parsed.get("body_excerpt") or "")
    highlights = parsed.get("highlights") or []
    title = pick_title(parsed)
    points = points_from_text(preprocess_text(intro or abstract or body, title), 3, 88, forbidden=[title])
    if len(points) < 3:
        points.extend(unique_points(highlights, 3 - len(points), 72, forbidden=points))
    if len(points) < 2:
        fallback = [
            t(output_lang, "这项研究聚焦一个有明确应用价值的真实问题。", "The paper addresses a concrete real-world problem."),
            t(output_lang, "核心目标是提升效果、效率或可解释性。", "The goal is to improve performance, efficiency, or interpretability."),
        ]
        points.extend(unique_points(fallback, 3 - len(points), 72, forbidden=points))
    return localize_points(points[:3], output_lang, 3, 90)


def compose_objective_points(parsed, output_lang):
    if is_zh(output_lang) and not str(parsed.get("language", "")).lower().startswith("zh"):
        topic = localize_title_phrase(pick_title(parsed), output_lang)
        return [
            "论文希望围绕“{0}”验证所提方法是否能够提升关键指标表现。".format(topic),
            "研究目标通常包括提升效果、降低成本，或改善流程中的稳定性与可解释性。",
            "组会汇报时可以把这一页作为“论文到底想证明什么”的集中回答。",
        ]
    abstract = clean(parsed.get("abstract") or "")
    highlights = parsed.get("highlights") or []
    body = clean(parsed.get("body_excerpt") or "")
    title = pick_title(parsed)
    points = unique_points(highlights, 3, 72, forbidden=[title])
    if len(points) < 3:
        points.extend(points_from_text(preprocess_text(abstract or body, title), 3 - len(points), 90, forbidden=points + [title]))
    if len(points) < 2:
        fallback = [
            t(output_lang, "明确研究问题、评价指标与预期收益。", "Define the research question, metrics, and expected gains."),
            t(output_lang, "验证方法是否优于已有方案。", "Test whether the method improves over existing baselines."),
        ]
        points.extend(unique_points(fallback, 3 - len(points), 72, forbidden=points))
    return localize_points(points[:3], output_lang, 3, 90)


def compose_method_points(parsed, output_lang):
    if is_zh(output_lang) and not str(parsed.get("language", "")).lower().startswith("zh"):
        topic = localize_title_phrase(pick_title(parsed), output_lang)
        return [
            "方法部分以“{0}”为核心，构建了一条较完整的处理流程。".format(topic),
            "汇报时建议按“输入数据 - 核心模型 - 输出结果”的顺序介绍方法结构。",
            "如果论文包含模型结构图或流程图，应放在这一页作为主要视觉重点。",
            "这一页的讲解目标不是逐句复述，而是让听众快速理解方法为何成立。",
        ]
    sections = parsed.get("sections") or {}
    method = clean(sections.get("method") or "")
    body = clean(parsed.get("body_excerpt") or "")
    abstract = clean(parsed.get("abstract") or "")
    title = pick_title(parsed)
    points = points_from_text(preprocess_text(method or body or abstract, title), 4, 92, forbidden=[title])
    if len(points) < 3:
        fallback = [
            t(output_lang, "说明输入数据、关键模块和整体流程。", "Describe the inputs, main modules, and overall pipeline."),
            t(output_lang, "突出模型设计或算法步骤中的关键创新。", "Highlight the key design innovation in the method."),
            t(output_lang, "如果论文有结构图，这一页应优先展示。", "If the paper has a structure diagram, it should be shown here first."),
        ]
        points.extend(unique_points(fallback, 4 - len(points), 82, forbidden=points))
    return localize_points(points[:4], output_lang, 4, 92)


def compose_experiment_points(parsed, output_lang):
    if is_zh(output_lang) and not str(parsed.get("language", "")).lower().startswith("zh"):
        return [
            "实验设计需要说明所用数据集、评价指标以及基线方法的设置。",
            "如果论文有多组实验，建议优先突出最能验证核心观点的那一组。",
            "组会汇报时可以在这一页提前交代后续结果页将重点比较什么。",
        ]
    sections = parsed.get("sections") or {}
    results = clean(sections.get("results") or "")
    method = clean(sections.get("method") or "")
    body = clean(parsed.get("body_excerpt") or "")
    title = pick_title(parsed)
    points = points_from_text(preprocess_text(results or method or body, title), 3, 90, forbidden=[title])
    if len(points) < 3:
        fallback = [
            t(output_lang, "给出数据集、评价指标与对比基线。", "Summarize datasets, metrics, and baselines."),
            t(output_lang, "说明实验流程与关键设置。", "Explain the experimental setup and major settings."),
            t(output_lang, "如果有消融或对比实验，这里需要单独突出。", "Ablation or comparison settings should be highlighted here."),
        ]
        points.extend(unique_points(fallback, 3 - len(points), 82, forbidden=points))
    return localize_points(points[:3], output_lang, 3, 90)


def compose_result_points(parsed, output_lang):
    if is_zh(output_lang) and not str(parsed.get("language", "")).lower().startswith("zh"):
        return [
            "结果部分应聚焦最关键的提升点，而不是把所有指标逐项罗列。",
            "如果论文给出了对比实验或消融实验，这里建议优先展示最有说服力的证据。",
            "汇报时要把“结果意味着什么”说清楚，而不只是机械读数值。",
        ]
    sections = parsed.get("sections") or {}
    results = clean(sections.get("results") or "")
    discussion = clean(sections.get("discussion") or "")
    abstract = clean(parsed.get("abstract") or "")
    highlights = parsed.get("highlights") or []
    title = pick_title(parsed)
    points = unique_points(highlights, 3, 72, forbidden=[title])
    if len(points) < 3:
        points.extend(points_from_text(preprocess_text(results or discussion or abstract, title), 3 - len(points), 88, forbidden=points + [title]))
    if len(points) < 2:
        fallback = [
            t(output_lang, "结果页要突出最能支撑结论的关键对比。", "The results slide should emphasize the strongest supporting evidence."),
            t(output_lang, "建议补充与基线方法的清晰对照。", "Add a clear comparison against baselines."),
        ]
        points.extend(unique_points(fallback, 3 - len(points), 80, forbidden=points))
    return localize_points(points[:3], output_lang, 3, 88)


def compose_conclusion_points(parsed, output_lang):
    if is_zh(output_lang) and not str(parsed.get("language", "")).lower().startswith("zh"):
        topic = localize_title_phrase(pick_title(parsed), output_lang)
        return [
            "这篇论文围绕“{0}”给出了一条较清晰的方法路径和结果支撑。".format(topic),
            "从组会角度，结论页应回到“贡献是什么、价值在哪里、还能怎么做”这三个问题。",
            "如果后续要复现或拓展，这一页也适合自然引出下一步工作方向。",
        ]
    sections = parsed.get("sections") or {}
    conclusion = clean(sections.get("conclusion") or "")
    discussion = clean(sections.get("discussion") or "")
    abstract = clean(parsed.get("abstract") or "")
    title = pick_title(parsed)
    points = points_from_text(preprocess_text(conclusion or discussion or abstract, title), 3, 88, forbidden=[title])
    if len(points) < 2:
        fallback = [
            t(output_lang, "总结核心贡献与可迁移价值。", "Summarize the core contribution and transfer value."),
            t(output_lang, "给出下一步实验或改进方向。", "State the next experiment or improvement direction."),
        ]
        points.extend(unique_points(fallback, 3 - len(points), 80, forbidden=points))
    return localize_points(points[:3], output_lang, 3, 88)


def build_slides(parsed, output_lang):
    title = pick_title(parsed)
    abstract = clean(parsed.get("abstract") or "")
    source_text = abstract or clean(parsed.get("body_excerpt") or "")
    topic = localize_title_phrase(title, output_lang)

    if is_zh(output_lang) and not str(parsed.get("language", "")).lower().startswith("zh"):
        title_points = [
            "本次汇报围绕“{0}”展开，重点梳理研究背景、方法设计与核心结果。".format(topic),
            "整体内容按照“问题提出 - 方法实现 - 结果分析 - 讨论总结”的顺序组织。",
            "这套 PPT 适合作为组会精读汇报底稿，后续可继续替换真实图表完善展示。",
        ]
    else:
        title_points = points_from_text(preprocess_text(source_text, title), 3, 92, forbidden=[title])
        if len(title_points) < 2:
            title_points.extend(
                unique_points(
                    [
                        t(output_lang, "围绕论文内容快速梳理研究背景、方法与结果。", "A concise walk-through of the paper background, method, and results."),
                        t(output_lang, "适合组会汇报的多页结构化讲解。", "Structured for a multi-slide lab meeting presentation."),
                    ],
                    3 - len(title_points),
                    78,
                    forbidden=title_points,
                )
            )
        title_points = localize_points(title_points[:3], output_lang, 3, 92)

    slides = [
        {
            "id": "title",
            "layout": "title",
            "title": title,
            "subtitle": t(output_lang, "组会汇报 / 论文精读", "Lab Meeting / Paper Review"),
            "bullets": title_points,
            "figure_hint": t(output_lang, "论文首页、核心图或研究场景图", "Paper first page, key figure, or application scene"),
        },
        {
            "id": "agenda",
            "layout": "agenda",
            "title": t(output_lang, "汇报结构", "Agenda"),
            "subtitle": t(output_lang, "先交代问题，再讲方法和结果", "Problem first, then method and findings"),
            "bullets": [
                t(output_lang, "1. 研究背景与问题定义", "1. Background and problem setup"),
                t(output_lang, "2. 方法设计与实验流程", "2. Method design and experiment setup"),
                t(output_lang, "3. 核心结果、结论与讨论", "3. Results, conclusions, and discussion"),
            ],
            "figure_hint": t(output_lang, "正式汇报时可替换为目录页视觉元素", "Optional agenda visual or lab template image"),
        },
        {
            "id": "background",
            "layout": "content",
            "title": t(output_lang, "研究背景", "Background"),
            "subtitle": t(output_lang, "为什么这个问题值得研究", "Why this problem matters"),
            "bullets": compose_background_points(parsed, output_lang),
            "figure_hint": t(output_lang, "应用场景图、任务示意图或数据来源图", "Application scene, task diagram, or data source image"),
        },
        {
            "id": "objective",
            "layout": "content",
            "title": t(output_lang, "研究问题与目标", "Research Objective"),
            "subtitle": t(output_lang, "论文想解决什么、如何衡量", "What the paper aims to solve"),
            "bullets": compose_objective_points(parsed, output_lang),
            "figure_hint": t(output_lang, "研究问题框架图或目标定义图", "Problem framing or objective definition figure"),
        },
        {
            "id": "method",
            "layout": "content",
            "title": t(output_lang, "方法概览", "Method Overview"),
            "subtitle": t(output_lang, "核心模型、流程或算法设计", "Core model, pipeline, or algorithm"),
            "bullets": compose_method_points(parsed, output_lang),
            "figure_hint": t(output_lang, "模型结构图、流程图或模块图", "Model architecture, workflow, or module diagram"),
        },
        {
            "id": "experiment",
            "layout": "content",
            "title": t(output_lang, "实验设计", "Experiment Setup"),
            "subtitle": t(output_lang, "数据、指标与对比方式", "Data, metrics, and baselines"),
            "bullets": compose_experiment_points(parsed, output_lang),
            "figure_hint": t(output_lang, "实验流程、指标表或数据集说明图", "Experiment flow, metric table, or dataset summary"),
        },
        {
            "id": "results",
            "layout": "content",
            "title": t(output_lang, "核心结果", "Key Results"),
            "subtitle": t(output_lang, "最能支撑论文结论的证据", "Evidence that supports the paper's claims"),
            "bullets": compose_result_points(parsed, output_lang),
            "figure_hint": t(output_lang, "结果对比图、消融实验图或关键表格", "Comparison chart, ablation figure, or key table"),
        },
        {
            "id": "conclusion",
            "layout": "content",
            "title": t(output_lang, "结论与启发", "Conclusion and Takeaways"),
            "subtitle": t(output_lang, "这篇论文给我们什么启发", "What we can take away"),
            "bullets": compose_conclusion_points(parsed, output_lang),
            "figure_hint": t(output_lang, "总结图、结论框或未来工作示意", "Summary block, conclusion figure, or future work visual"),
        },
        {
            "id": "discussion",
            "layout": "qa",
            "title": t(output_lang, "讨论与提问", "Discussion and Q&A"),
            "subtitle": t(output_lang, "适合组会上继续展开的问题", "Questions for lab discussion"),
            "bullets": [
                t(output_lang, "论文最核心的创新点是什么？", "What is the key innovation of this paper?"),
                t(output_lang, "结果里哪一部分最值得进一步验证？", "Which result deserves the strongest follow-up validation?"),
                t(output_lang, "如果复现或扩展，这项工作下一步怎么做？", "If we reproduce or extend it, what should be the next step?"),
            ],
            "figure_hint": t(output_lang, "问答页或讨论关键词卡片", "Q&A page or discussion keyword cards"),
        },
    ]

    return title, slides


def attach_slide_images(parsed, slides):
    extracted_images = parsed.get("extracted_images") or []
    if not extracted_images:
        return slides

    preferred_slide_ids = ["title", "background", "objective", "method", "experiment", "results", "conclusion"]
    image_map = {}
    for idx, slide_id in enumerate(preferred_slide_ids):
        if idx < len(extracted_images):
            image_map[slide_id] = extracted_images[idx]

    enriched = []
    for slide in slides:
        next_slide = dict(slide)
        image_meta = image_map.get(slide.get("id"))
        if image_meta:
            next_slide["figure_image"] = image_meta.get("path") or image_meta.get("name")
            next_slide["figure_image_name"] = image_meta.get("name", "")
        enriched.append(next_slide)
    return enriched


def build_package(parsed, source_path, style_request, output_lang):
    title, slides = build_slides(parsed, output_lang)
    slides = attach_slide_images(parsed, slides)
    summary = clean(parsed.get("abstract") or parsed.get("body_excerpt") or title)
    package = {
        "jobType": "slides",
        "provider": "local-deterministic",
        "source_language": detect_source_language(parsed),
        "language": output_lang,
        "summary": localize_point(summary[:320], output_lang),
        "title": title,
        "source_path": source_path,
        "asset_images": parsed.get("extracted_images", []),
        "style_request": style_request,
        "deck_type": "group-meeting",
        "slides": slides,
        "deliverables": [
            {"name": "slides-outline.md", "format": "markdown"},
            {"name": "speaker-notes.md", "format": "markdown"},
            {"name": "figure-plan.md", "format": "markdown"},
            {"name": "discussion-questions.md", "format": "markdown"},
            {"name": "slides-preview.png", "format": "png"},
            {"name": "slides-preview.html", "format": "html"},
            {"name": "slides.pptx", "format": "pptx"},
        ],
        "nextSteps": [
            t(output_lang, "如果论文图片提取成功，PPT 会优先自动放入对应页面；正式汇报前仍可继续手动微调。", "If paper figures were extracted successfully, the deck will place them automatically; you can still fine-tune them before the final talk."),
            t(output_lang, "如果需要更长汇报，可在实验和讨论部分继续补页。", "Add extra slides for experiments or discussion if you need a longer talk."),
        ],
    }
    return package


def main():
    parser = argparse.ArgumentParser(description="Build a structured group-meeting slide package from parsed paper JSON.")
    parser.add_argument("--input", required=True, help="Path to parsed-paper.json.")
    parser.add_argument("--output-dir", required=True, help="Output directory for slide files.")
    parser.add_argument("--style", default="classic-blue", help="Style request.")
    parser.add_argument("--language", default="zh-CN", help="Output language, such as zh-CN or en.")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    parsed = json.loads(input_path.read_text(encoding="utf-8"))
    output_lang = normalize_output_language(args.language)
    package = build_package(parsed, parsed.get("source_path", str(input_path)), args.style, output_lang)

    package_path = output_dir / "slides-package.json"
    outline_path = output_dir / "slides-outline.md"
    notes_path = output_dir / "speaker-notes.md"
    figure_path = output_dir / "figure-plan.md"
    questions_path = output_dir / "discussion-questions.md"

    outline_lines = ["# {0}".format(package["title"])]
    notes_lines = ["# {0}".format(t(output_lang, "讲稿备注：{0}".format(package["title"]), "Speaker Notes: {0}".format(package["title"])))]
    figure_lines = ["# {0}".format(t(output_lang, "配图建议", "Figure Plan"))]
    question_lines = ["# {0}".format(t(output_lang, "讨论问题", "Discussion Questions"))]

    for idx, slide in enumerate(package["slides"], start=1):
        outline_lines.append("\n## {0}".format(t(output_lang, "第 {0} 页：{1}".format(idx, slide["title"]), "Slide {0}: {1}".format(idx, slide["title"]))))
        outline_lines.append("- {0}".format(slide.get("subtitle", "")))
        for item in slide["bullets"]:
            outline_lines.append("- {0}".format(item))
        outline_lines.append("- {0}{1}".format(t(output_lang, "配图建议：", "Figure suggestion: "), slide["figure_hint"]))

        notes_lines.append("\n## {0}".format(t(output_lang, "第 {0} 页：{1}".format(idx, slide["title"]), "Slide {0}: {1}".format(idx, slide["title"]))))
        notes_lines.append("{0}{1}".format(t(output_lang, "开场说明：", "Opening: "), slide.get("subtitle", "")))
        notes_lines.append("{0}{1}".format(t(output_lang, "讲解要点：", "Talk track: "), " ".join(slide["bullets"])))

        figure_lines.append("\n## {0}".format(t(output_lang, "第 {0} 页：{1}".format(idx, slide["title"]), "Slide {0}: {1}".format(idx, slide["title"]))))
        figure_lines.append("- {0}".format(slide["figure_hint"]))

    for question in package["slides"][-1]["bullets"]:
        question_lines.append("- {0}".format(question))

    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    outline_path.write_text("\n".join(outline_lines) + "\n", encoding="utf-8")
    notes_path.write_text("\n".join(notes_lines) + "\n", encoding="utf-8")
    figure_path.write_text("\n".join(figure_lines) + "\n", encoding="utf-8")
    questions_path.write_text("\n".join(question_lines) + "\n", encoding="utf-8")

    print(str(package_path))


if __name__ == "__main__":
    main()
