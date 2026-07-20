#!/usr/bin/env python
import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    from PIL import Image
except Exception:
    Image = None


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".emf", ".wmf"}
VECTOR_EXTS = {".svg", ".emf", ".wmf"}

STYLE_MAP = {
    "classic-blue": {
        "id": "classic-blue",
        "background": "#F7FAFC",
        "panel_bg": "#FFFFFF",
        "headline": "#163A63",
        "accent": "#1E5AA8",
        "muted": "#5B6B7F",
        "title_font": "Aptos Display",
        "body_font": "Aptos",
    },
    "clean-light": {
        "id": "clean-light",
        "background": "#FAFAF7",
        "panel_bg": "#FFFFFF",
        "headline": "#1F2933",
        "accent": "#607D9B",
        "muted": "#6B7280",
        "title_font": "Aptos Display",
        "body_font": "Aptos",
    },
    "green-tech": {
        "id": "green-tech",
        "background": "#F4FBF7",
        "panel_bg": "#FFFFFF",
        "headline": "#184E3A",
        "accent": "#2F855A",
        "muted": "#5E7A6D",
        "title_font": "Aptos Display",
        "body_font": "Aptos",
    },
    "serif-journal": {
        "id": "serif-journal",
        "background": "#FBF8F2",
        "panel_bg": "#FFFDF8",
        "headline": "#231F20",
        "accent": "#7A3B3B",
        "muted": "#6A5F5B",
        "title_font": "Georgia",
        "body_font": "Aptos",
    },
    "ink-academic": {
        "id": "ink-academic",
        "background": "#F8F6F1",
        "panel_bg": "#FFFCF5",
        "headline": "#101828",
        "accent": "#273C75",
        "muted": "#667085",
        "title_font": "Georgia",
        "body_font": "Aptos",
    },
}

TEMPLATE_MAP = {
    "neurips-four-column": {
        "id": "neurips-four-column",
        "display_name": "NeurIPS Four Column",
        "description": "Dense landscape poster with balanced chart zones.",
        "limits": (2, 2, 3, 2),
        "orientation": "landscape",
        "columns": 4,
        "ratio": "16:9",
    },
    "icml-spotlight": {
        "id": "icml-spotlight",
        "display_name": "ICML Spotlight",
        "description": "Landscape layout centered on results and experiment comparisons.",
        "limits": (2, 2, 3, 2),
        "orientation": "landscape",
        "columns": 3,
        "ratio": "16:9",
    },
    "reference-red-landscape": {
        "id": "reference-red-landscape",
        "display_name": "Reference Red Landscape",
        "description": "Formal red-accented landscape poster.",
        "limits": (2, 2, 3, 2),
        "orientation": "landscape",
        "columns": 3,
        "ratio": "16:9",
    },
    "reference-portrait": {
        "id": "reference-portrait",
        "display_name": "Reference Portrait",
        "description": "Portrait academic poster suited for text-led research.",
        "limits": (2, 2, 3, 2),
        "orientation": "portrait",
        "columns": 2,
        "ratio": "3:4",
    },
    "royal-blue-math": {
        "id": "royal-blue-math",
        "display_name": "Royal Blue Math",
        "description": "Landscape poster with a structured academic tone.",
        "limits": (2, 2, 3, 2),
        "orientation": "landscape",
        "columns": 3,
        "ratio": "16:9",
    },
    "colorful-four-column": {
        "id": "colorful-four-column",
        "display_name": "Colorful Four Column",
        "description": "Visual four-column poster with modular blocks.",
        "limits": (2, 2, 3, 2),
        "orientation": "landscape",
        "columns": 4,
        "ratio": "16:9",
    },
}

SECTION_PATTERNS = [
    ("abstract", ["abstract", "摘要"]),
    ("introduction", ["introduction", "background", "intro", "引言", "研究背景"]),
    ("method", ["method", "methods", "methodology", "materials and methods", "approach", "方法", "研究方法"]),
    ("results", ["results", "findings", "experiments", "evaluation", "实验结果", "结果", "研究结果"]),
    ("discussion", ["discussion", "分析", "讨论"]),
    ("conclusion", ["conclusion", "conclusions", "结论", "总结"]),
    ("references", ["references", "bibliography", "参考文献"]),
]

SECTION_LABELS = {alias.lower() for _, aliases in SECTION_PATTERNS for alias in aliases}
AFFILIATION_KEYWORDS = [
    "university",
    "college",
    "institute",
    "laboratory",
    "lab",
    "school",
    "department",
    "center",
    "centre",
    "academy",
    "hospital",
    "大学",
    "学院",
    "研究所",
    "实验室",
    "中心",
    "医院",
]


def contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def clean_text(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_student_metadata(text: str) -> str:
    patterns = [
        r"姓名[:：]?\s*[^\s，。；;]+",
        r"学号[:：]?\s*\d+",
        r"班级[:：]?\s*[^\n]+",
    ]
    out = text
    for pattern in patterns:
        out = re.sub(pattern, "", out)
    out = re.sub(r"[ ]{2,}", " ", out)
    return clean_text(out)


def read_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        xml_bytes = zf.read("word/document.xml")
    root = ElementTree.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for para in root.findall(".//w:p", ns):
        texts = [node.text or "" for node in para.findall(".//w:t", ns)]
        joined = "".join(texts).strip()
        if joined:
            paragraphs.append(joined)
    return strip_student_metadata(clean_text("\n".join(paragraphs)))


def extract_docx_images(path: Path, asset_output_dir: Path):
    asset_output_dir.mkdir(parents=True, exist_ok=True)
    extracted = []
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if not name.startswith("word/media/"):
                continue
            suffix = Path(name).suffix.lower()
            if suffix not in IMAGE_EXTS:
                continue
            target = asset_output_dir / f"embedded_{len(extracted) + 1}{suffix}"
            with zf.open(name) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(target)
    return extracted


def image_quality_info(path: Path):
    suffix = path.suffix.lower()
    if suffix in VECTOR_EXTS:
        return {"width": 0, "height": 0, "long_edge": 10000, "quality": "vector"}
    if Image is None:
        return {"width": 0, "height": 0, "long_edge": 0, "quality": "unknown"}
    try:
        with Image.open(path) as img:
            width, height = img.size
    except Exception:
        return {"width": 0, "height": 0, "long_edge": 0, "quality": "unknown"}
    long_edge = max(width, height)
    if long_edge >= 1800:
        quality = "high"
    elif long_edge >= 1200:
        quality = "medium"
    elif long_edge >= 700:
        quality = "usable"
    else:
        quality = "low"
    return {"width": width, "height": height, "long_edge": long_edge, "quality": quality}


def rank_images(images):
    quality_rank = {"vector": 5, "high": 4, "medium": 3, "usable": 2, "low": 1, "unknown": 0}
    scored = []
    for image in images:
        info = image_quality_info(image)
        is_embedded = image.stem.startswith("embedded_") or "extracted_assets" in {part.lower() for part in image.parts}
        area = info["width"] * info["height"]
        scored.append((quality_rank.get(info["quality"], 0), 1 if is_embedded else 0, info["long_edge"], area, image, info))
    scored.sort(key=lambda item: (item[0], item[1], item[2], item[3]), reverse=True)
    return [(image, info) for _, __, ___, ____, image, info in scored]


def read_source(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        if PdfReader is None:
            raise RuntimeError("pypdf is not available, so PDF parsing cannot run.")
        reader = PdfReader(str(path))
        chunks = []
        for page in reader.pages:
            chunks.append(page.extract_text() or "")
        return strip_student_metadata(clean_text("\n".join(chunks)))
    if suffix == ".docx":
        return read_docx_text(path)
    return strip_student_metadata(clean_text(path.read_text(encoding="utf-8", errors="ignore")))


def first_nonempty(lines):
    for line in lines:
        value = line.strip()
        if value:
            return value
    return ""


def split_sentences(text: str):
    parts = re.split(r"(?<=[.!?。！？])\s*", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def shorten(line: str, limit: int = 140) -> str:
    line = re.sub(r"\s+", " ", line or "").strip()
    if len(line) <= limit:
        return line
    return line[: limit - 3].rstrip() + "..."


def shorten_title(line: str, limit: int = 88) -> str:
    line = re.sub(r"\s+", " ", line or "").strip()
    line = re.sub(r"^[\-\*\d\.\s]+", "", line)
    if len(line) <= limit:
        return line
    return line[: limit - 3].rstrip(" ,;:") + "..."


def squeeze_bullet(line: str, limit: int = 76) -> str:
    line = re.sub(r"\s+", " ", line or "").strip()
    line = re.sub(r"^\d+(\.\d+)*\s*", "", line)
    line = re.sub(r"^(figure|table|图|表)\s*\d+\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(r"^(姓名|学号|班级)[:：].*$", "", line)
    return shorten(line, limit)


def bulletize(text: str, limit: int = 4, max_chars: int = 88):
    sentences = split_sentences(text)
    if not sentences:
        sentences = [ln.strip("-* \t") for ln in (text or "").splitlines() if ln.strip()]
    items = []
    for sentence in sentences:
        item = squeeze_bullet(sentence, max_chars)
        if item and item not in items:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def detect_sections(text: str):
    lines = [ln.strip() for ln in text.splitlines()]
    positions = []
    for idx, line in enumerate(lines):
        lower = line.lower().strip(":：? ")
        for name, aliases in SECTION_PATTERNS:
            if lower in aliases:
                positions.append((idx, name))
                break
    if not positions:
        return {}
    sections = {}
    for pos_idx, (line_idx, name) in enumerate(positions):
        end_idx = positions[pos_idx + 1][0] if pos_idx + 1 < len(positions) else len(lines)
        body = "\n".join(lines[line_idx + 1 : end_idx]).strip()
        sections[name] = clean_text(body)
    return sections


def pick_style(style_request: str, template_id: str = ""):
    style_request = (style_request or "").strip().lower()
    if style_request in STYLE_MAP:
        return STYLE_MAP[style_request], style_request
    if template_id in {"reference-red-landscape"}:
        return STYLE_MAP["serif-journal"], style_request
    if template_id in {"royal-blue-math"}:
        return STYLE_MAP["ink-academic"], style_request
    if template_id in {"colorful-four-column"}:
        return STYLE_MAP["green-tech"], style_request
    if any(word in style_request for word in ["formal", "academic", "conference", "normal", "科研", "学术", "正式"]):
        return STYLE_MAP["classic-blue"], style_request
    if any(word in style_request for word in ["clean", "light", "minimal", "simple", "journal club", "简洁"]):
        return STYLE_MAP["clean-light"], style_request
    if any(word in style_request for word in ["green", "biology", "environment", "sustain", "eco", "绿色"]):
        return STYLE_MAP["green-tech"], style_request
    if any(word in style_request for word in ["serif", "editorial", "journal", "humanities", "social science", "期刊"]):
        return STYLE_MAP["serif-journal"], style_request
    return STYLE_MAP["classic-blue"], style_request


def pick_template(template_request: str):
    template_request = Path(template_request or "").stem.strip().lower()
    if template_request in TEMPLATE_MAP:
        return TEMPLATE_MAP[template_request], template_request
    aliases = {
        "conference-classic": "neurips-four-column",
        "data-focus": "icml-spotlight",
        "compact-journal": "reference-portrait",
        "visual-showcase": "colorful-four-column",
        "autofi-academic-poster": "neurips-four-column",
        "reference-academic-poster": "reference-red-landscape",
        "reference-style-academic-poster": "reference-portrait",
        "icml-spotlight-academic-poster": "icml-spotlight",
        "royal-blue-math-academic-poster": "royal-blue-math",
        "colorful-four-column-academic-poster": "colorful-four-column",
        "reference-academic-poster": "reference-red-landscape",
        "reference-style-academic-poster": "reference-portrait",
        "icml-spotlight-academic-poster": "icml-spotlight",
        "royal-blue-math-academic-poster": "royal-blue-math",
        "colorful-four-column-academic-poster": "colorful-four-column",
        "autofi-academic-poster": "neurips-four-column",
        "reference-academic-poster.png": "reference-red-landscape",
        "reference-style-academic-poster.png": "reference-portrait",
        "icml-spotlight-academic-poster.png": "icml-spotlight",
        "royal-blue-math-academic-poster.png": "royal-blue-math",
        "colorful-four-column-academic-poster.png": "colorful-four-column",
        "autofi-academic-poster.png": "neurips-four-column",
        "reference-academic-poster.jpg": "reference-red-landscape",
        "reference-style-academic-poster.jpg": "reference-portrait",
        "icml-spotlight-academic-poster.jpg": "icml-spotlight",
        "royal-blue-math-academic-poster.jpg": "royal-blue-math",
        "colorful-four-column-academic-poster.jpg": "colorful-four-column",
        "autofi-academic-poster.jpg": "neurips-four-column",
    }
    if template_request in aliases:
        return TEMPLATE_MAP[aliases[template_request]], template_request
    if any(word in template_request for word in ["icml", "spotlight", "ml", "machine learning"]):
        return TEMPLATE_MAP["icml-spotlight"], template_request
    if any(word in template_request for word in ["portrait", "vertical", "journal", "review", "竖版"]):
        return TEMPLATE_MAP["reference-portrait"], template_request
    if any(word in template_request for word in ["red", "reference", "formal"]):
        return TEMPLATE_MAP["reference-red-landscape"], template_request
    if any(word in template_request for word in ["math", "blue", "proof"]):
        return TEMPLATE_MAP["royal-blue-math"], template_request
    if any(word in template_request for word in ["colorful", "visual", "figure"]):
        return TEMPLATE_MAP["colorful-four-column"], template_request
    return TEMPLATE_MAP["neurips-four-column"], template_request


def find_images(images_dir: Path):
    if not images_dir.exists():
        return []
    return sorted([p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS], key=lambda p: p.name.lower())


def detect_language(text: str):
    return "zh" if contains_chinese(text) else "en"


def is_section_label(line: str) -> bool:
    return line.lower().strip(":： ").strip() in SECTION_LABELS


def is_probable_title(line: str) -> bool:
    text = re.sub(r"\s+", " ", line or "").strip()
    lower = text.lower()
    if len(text) < 12 or len(text) > 180:
        return False
    if is_section_label(text):
        return False
    if any(token in lower for token in ["email", "@", "doi", "keywords", "keyword", "作者", "author", "authors"]):
        return False
    if any(token in lower for token in AFFILIATION_KEYWORDS):
        return False
    return True


def is_probable_author_line(line: str) -> bool:
    text = re.sub(r"\s+", " ", line or "").strip()
    lower = text.lower()
    if not text or len(text) > 120 or "@" in text:
        return False
    if any(token in lower for token in AFFILIATION_KEYWORDS):
        return False
    if re.match(r"^(author|authors|姓名|作者)[:：]", text, re.IGNORECASE):
        return True
    if re.search(r"[A-Za-z]{2,}\s+[A-Za-z]{2,}", text) and ("," in text or " and " in lower):
        return True
    if re.search(r"[\u4e00-\u9fff]{2,4}[、，,][\u4e00-\u9fff]{2,4}", text):
        return True
    return False


def is_probable_affiliation_line(line: str) -> bool:
    text = re.sub(r"\s+", " ", line or "").strip()
    lower = text.lower()
    return bool(text) and any(token in lower for token in AFFILIATION_KEYWORDS)


def parse_author_line(author_line: str):
    cleaned = re.sub(r"^(author|authors|姓名|作者)[:：]\s*", "", author_line or "", flags=re.IGNORECASE).strip()
    parts = re.split(r",|;| and |、|，", cleaned)
    authors = []
    for part in parts:
        part = re.sub(r"\b\d+\b", "", part).strip()
        if not part or len(part) > 40:
            continue
        if part not in authors:
            authors.append(part)
    return authors


def extract_title_and_authors(text: str):
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines() if ln.strip()]
    title = ""
    title_index = 0
    for idx, line in enumerate(lines[:18]):
        if is_probable_title(line):
            title = line
            title_index = idx
            break
    if not title:
        title = first_nonempty(lines[:8])

    author_line = ""
    affiliation = ""
    for line in lines[title_index + 1 : title_index + 10]:
        if not author_line and is_probable_author_line(line):
            author_line = line
            continue
        if not affiliation and is_probable_affiliation_line(line):
            affiliation = line
            if author_line:
                break
    authors = parse_author_line(author_line) if author_line else []
    if affiliation == author_line:
        affiliation = ""
    return title, authors, affiliation


def localized_section_title(section_id: str, language: str) -> str:
    if language == "en":
        mapping = {
            "background": "Background",
            "method": "Method",
            "results": "Results",
            "conclusion": "Conclusion",
        }
        return mapping.get(section_id, section_id.title())
    mapping = {
        "background": "研究背景",
        "method": "研究方法",
        "results": "关键结果",
        "conclusion": "结论与贡献",
    }
    return mapping.get(section_id, section_id)


def build_sections(text: str, detected: dict, template_id: str, language: str):
    abstract = detected.get("abstract", "")
    intro = detected.get("introduction", "")
    method = detected.get("method", "")
    results = detected.get("results", "")
    conclusion = detected.get("conclusion", "") or detected.get("discussion", "")
    limits = TEMPLATE_MAP.get(template_id, TEMPLATE_MAP["neurips-four-column"])["limits"]
    bg_limit, method_limit, result_limit, conclusion_limit = limits
    bullet_chars = 56 if TEMPLATE_MAP[template_id]["orientation"] == "portrait" else 62
    summary_points = bulletize(text, 10, bullet_chars)
    return [
        {
            "id": "background",
            "title": localized_section_title("background", language),
            "kind": "bullets",
            "content": bulletize(intro or abstract or text, min(bg_limit, 2), bullet_chars),
            "layout_hints": {"priority": "medium", "column_span": 1},
        },
        {
            "id": "method",
            "title": localized_section_title("method", language),
            "kind": "bullets",
            "content": bulletize(method or "\n".join(summary_points[2:6]) or text, min(method_limit, 2), bullet_chars),
            "layout_hints": {"priority": "medium", "column_span": 1},
        },
        {
            "id": "results",
            "title": localized_section_title("results", language),
            "kind": "bullets",
            "content": bulletize(results or "\n".join(summary_points[4:8]) or text, min(result_limit, 3), bullet_chars),
            "layout_hints": {"priority": "high", "column_span": 1},
        },
        {
            "id": "conclusion",
            "title": localized_section_title("conclusion", language),
            "kind": "bullets",
            "content": bulletize(conclusion or "\n".join(summary_points[-3:]) or text, min(conclusion_limit, 2), bullet_chars),
            "layout_hints": {"priority": "high", "column_span": 1},
        },
    ]


def build_key_highlights(detected: dict, text: str, template_id: str):
    max_chars = 32 if TEMPLATE_MAP[template_id]["orientation"] == "portrait" else 40
    pool = []
    for key in ["results", "conclusion", "abstract", "introduction"]:
        value = detected.get(key, "")
        if value:
            pool.extend(bulletize(value, 3, max_chars))
    if not pool:
        pool = bulletize(text, 4, max_chars)
    unique = []
    for item in pool:
        if item and item not in unique:
            unique.append(item)
        if len(unique) >= 2:
            break
    return unique


def build_research_summary(detected: dict, text: str, language: str):
    candidates = []
    for key in ["abstract", "results", "conclusion", "introduction"]:
        value = detected.get(key, "")
        if value:
            candidates.extend(bulletize(value, 2, 82))
    unique = []
    for item in candidates:
        if item and item not in unique:
            unique.append(item)
        if len(unique) >= 1:
            break
    if unique:
        return " ".join(unique)
    fallback = bulletize(text, 1, 80)
    if fallback:
        return fallback[0]
    return "Academic poster summary." if language == "en" else "论文摘要将在这里显示。"


def build_figures(images):
    figures = []
    chosen = []
    for image, info in rank_images(images):
        file_size = image.stat().st_size if image.exists() else 0
        if info["quality"] not in {"vector", "high", "medium", "usable"}:
            continue
        if info["quality"] != "vector" and info["long_edge"] < 700:
            continue
        if info["width"] and info["height"]:
            aspect = max(info["width"], info["height"]) / max(1, min(info["width"], info["height"]))
            if aspect > 4.5:
                continue
        if image.suffix.lower() not in VECTOR_EXTS and file_size < 12 * 1024:
            continue
        chosen.append((image, info))
        if len(chosen) >= 3:
            break

    if chosen:
        for idx, (image, info) in enumerate(chosen, start=1):
            caption = image.stem.replace("_", " ")
            if image.stem.startswith("embedded_"):
                caption = f"Figure {idx}"
            figures.append(
                {
                    "id": f"fig{idx}",
                    "title": f"Figure {idx}",
                    "purpose": "Research figure or chart",
                    "source_needed": False,
                    "caption": caption,
                    "placement_hint": "image-slot",
                    "path": str(image.resolve()),
                    "quality": info["quality"],
                    "width": info["width"],
                    "height": info["height"],
                    "long_edge": info["long_edge"],
                    "preferred_scale": "large" if info["quality"] in {"vector", "high"} else "small",
                }
            )
    else:
        figures.append(
            {
                "id": "fig1",
                "title": "Main Figure",
                "purpose": "Primary evidence image or chart",
                "source_needed": True,
                "caption": "Upload a higher-quality research figure to replace this placeholder.",
                "placement_hint": "image-slot",
                "path": "",
                "quality": "placeholder",
                "preferred_scale": "small",
            }
        )
    return figures


def build_package(text: str, source_path: Path, style_request: str, template_request: str, images):
    detected = detect_sections(text)
    language = detect_language(text)
    title, authors, affiliation = extract_title_and_authors(text)
    template, raw_template = pick_template(template_request)
    style, raw_style = pick_style(style_request, template["id"])
    sections = build_sections(text, detected, template["id"], language)
    figures = build_figures(images)
    highlights = build_key_highlights(detected, text, template["id"])
    research_summary = build_research_summary(detected, text, language)
    references = bulletize(detected.get("references", ""), 3, 70 if language == "en" else 52)

    missing = []
    if not authors:
        missing.append("authors")
    if not affiliation:
        missing.append("affiliation")
    if not detected.get("results"):
        missing.append("explicit results section")
    if not any(fig.get("path") for fig in figures):
        missing.append("research figures/images")
    elif not any(fig.get("quality") in {"vector", "high", "medium"} for fig in figures):
        missing.append("higher-resolution figures recommended")

    return {
        "poster_type": "academic",
        "language": language,
        "theme": {
            "tone": "clean",
            "layout": "adaptive",
            "style_id": style["id"],
            "user_style_request": raw_style,
            "template_id": template["id"],
            "user_template_request": raw_template,
            "background": style["background"],
            "panel_bg": style["panel_bg"],
            "headline_color": style["headline"],
            "accent_color": style["accent"],
            "muted_color": style["muted"],
            "title_font": style["title_font"],
            "body_font": style["body_font"],
        },
        "paper": {
            "source_path": str(source_path.resolve()),
            "title": shorten_title(title or source_path.stem, 88),
            "authors": authors,
            "affiliation": shorten(affiliation, 120),
            "venue": "",
            "year": "",
            "keywords": [],
        },
        "hero": {
            "headline": shorten_title(title or source_path.stem, 88),
            "subheadline": research_summary,
            "key_findings": highlights,
        },
        "sections": sections,
        "figures": figures,
        "footer": {
            "references": references,
            "contact": "",
            "acknowledgements": "",
        },
        "layout": {
            "poster_ratio": template["ratio"],
            "poster_mode": "single-slide-editable-pptx",
            "columns": template["columns"],
            "orientation": template["orientation"],
            "template": {
                "id": template["id"],
                "display_name": template["display_name"],
                "description": template["description"],
            },
        },
        "source_excerpt": shorten(text[:1200], 1200),
        "missing_information": missing,
    }


def main():
    parser = argparse.ArgumentParser(description="Build a structured academic poster package from a paper and images.")
    parser.add_argument("--input", required=True, help="Path to the source paper (.pdf, .docx, .txt, .md).")
    parser.add_argument("--images-dir", default=".", help="Directory containing uploaded figure images.")
    parser.add_argument("--style", default="classic-blue", help="Requested poster style.")
    parser.add_argument("--template", default="neurips-four-column", help="Requested poster template.")
    parser.add_argument("--asset-output-dir", default="", help="Directory to place extracted images from the paper.")
    parser.add_argument("--output", required=True, help="Path to output JSON package.")
    args = parser.parse_args()

    source_path = Path(args.input)
    images_dir = Path(args.images_dir)
    output_path = Path(args.output)

    text = read_source(source_path)
    images = find_images(images_dir)
    if source_path.suffix.lower() == ".docx":
        asset_dir = Path(args.asset_output_dir) if args.asset_output_dir else output_path.parent / "extracted_assets"
        extracted = extract_docx_images(source_path, asset_dir)
        seen = {str(p.resolve()).lower() for p in extracted}
        images = extracted + [p for p in images if str(p.resolve()).lower() not in seen]
    package = build_package(text, source_path, args.style, args.template, images)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(output_path))


if __name__ == "__main__":
    main()
