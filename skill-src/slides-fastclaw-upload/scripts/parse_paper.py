#!/usr/bin/env python
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree


MAX_TEXT_LENGTH = 60000
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def split_paragraphs(text: str):
    return [item.strip() for item in normalize_whitespace(text).split("\n\n") if item.strip()]


def detect_language(text: str) -> str:
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return "zh-CN" if chinese > latin * 0.2 else "en"


def infer_title(paragraphs, fallback_name: str) -> str:
    for item in paragraphs[:12]:
        if 8 <= len(item) <= 220:
            return re.sub(r"\s+", " ", item).strip()
    return Path(fallback_name).stem


def infer_abstract(paragraphs, language: str):
    for idx, item in enumerate(paragraphs[:20]):
        lower = item.lower().strip()
        if language == "zh-CN" and lower.startswith("摘要"):
            cleaned = re.sub(r"^摘要[:：]?\s*", "", item).strip()
            return cleaned or (paragraphs[idx + 1] if idx + 1 < len(paragraphs) else "")
        if language == "en" and lower.startswith("abstract"):
            cleaned = re.sub(r"^abstract[:：]?\s*", "", item, flags=re.IGNORECASE).strip()
            return cleaned or (paragraphs[idx + 1] if idx + 1 < len(paragraphs) else "")
    for item in paragraphs[1:8]:
        if 120 <= len(item) <= 2400:
            return item
    return ""


def infer_highlights(paragraphs, abstract_text: str):
    items = []
    for item in paragraphs:
        cleaned = re.sub(r"\s+", " ", item).strip()
        if cleaned == abstract_text:
            continue
        if 20 <= len(cleaned) <= 160 and cleaned not in items:
            items.append(cleaned)
        if len(items) >= 4:
            break
    return items


def detect_sections(text: str):
    lines = [line.strip() for line in normalize_whitespace(text).splitlines()]
    aliases = {
        "introduction": ["introduction", "background", "intro", "引言", "研究背景"],
        "method": ["method", "methods", "methodology", "approach", "materials and methods", "方法", "研究方法"],
        "results": ["results", "findings", "experiments", "evaluation", "结果", "实验结果", "研究结果"],
        "discussion": ["discussion", "analysis", "讨论", "分析"],
        "conclusion": ["conclusion", "conclusions", "summary and outlook", "结论", "总结"],
    }
    headers = []
    for idx, line in enumerate(lines):
        lower = line.lower().strip(":：?.")
        for key, options in aliases.items():
            if lower in options:
                headers.append((idx, key))
                break
    sections = {}
    for pos, (start, key) in enumerate(headers):
        end = headers[pos + 1][0] if pos + 1 < len(headers) else len(lines)
        body = "\n".join(lines[start + 1 : end]).strip()
        if body:
            sections[key] = body[:4000]
    return sections


def docx_to_text(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        xml_bytes = zf.read("word/document.xml")
    root = ElementTree.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for para in root.findall(".//w:p", ns):
        parts = [node.text or "" for node in para.findall(".//w:t", ns)]
        joined = "".join(parts).strip()
        if joined:
            paragraphs.append(joined)
    return "\n".join(paragraphs)


def safe_asset_name(index: int, suffix: str) -> str:
    normalized = suffix.lower()
    if not normalized.startswith("."):
        normalized = "." + normalized
    if normalized not in IMAGE_EXTS:
        normalized = ".png"
    return "paper-figure-{0:02d}{1}".format(index, normalized)


def extract_docx_images(path: Path, output_dir: Path):
    extracted = []
    with zipfile.ZipFile(path) as zf:
        media_names = [name for name in zf.namelist() if name.startswith("word/media/")]
        for idx, media_name in enumerate(media_names, start=1):
            suffix = Path(media_name).suffix.lower() or ".png"
            if suffix not in IMAGE_EXTS:
                continue
            target = output_dir / safe_asset_name(idx, suffix)
            with zf.open(media_name) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(
                {
                    "name": target.name,
                    "path": str(target.resolve()),
                    "source": "docx-media",
                }
            )
    return extracted


def copy_workspace_images(image_paths, output_dir: Path, start_index: int):
    copied = []
    seen = set()
    index = start_index
    for raw_path in image_paths or []:
        candidate = Path(str(raw_path))
        if not candidate.exists() or not candidate.is_file():
            continue
        suffix = candidate.suffix.lower()
        if suffix not in IMAGE_EXTS:
            continue
        key = str(candidate.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        target = output_dir / safe_asset_name(index, suffix)
        shutil.copy2(candidate, target)
        copied.append(
            {
                "name": target.name,
                "path": str(target.resolve()),
                "source": "workspace-image",
                "original_path": str(candidate.resolve()),
            }
        )
        index += 1
    return copied


def pdf_to_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        pass

    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        with tempfile.TemporaryDirectory(prefix="paper-pdf-") as temp_dir:
            txt_path = Path(temp_dir) / "paper.txt"
            subprocess.run([pdftotext, str(path), str(txt_path)], check=True)
            return txt_path.read_text(encoding="utf-8", errors="ignore")

    raise RuntimeError("PDF parsing failed. Install pypdf or pdftotext, or upload DOCX/TXT.")


def doc_to_text(path: Path) -> str:
    antiword = shutil.which("antiword")
    if antiword:
        result = subprocess.run([antiword, str(path)], capture_output=True, text=True, check=True)
        return result.stdout

    soffice = shutil.which("soffice")
    if soffice:
        with tempfile.TemporaryDirectory(prefix="paper-doc-") as temp_dir:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "txt:Text", "--outdir", temp_dir, str(path)],
                capture_output=True,
                text=True,
                check=True,
            )
            txt_path = Path(temp_dir) / f"{path.stem}.txt"
            if txt_path.exists():
                return txt_path.read_text(encoding="utf-8", errors="ignore")

    if sys.platform.startswith("win"):
        winword = shutil.which("winword")
        if winword:
            temp_txt = path.with_suffix(".txt")
            open_path = str(path).replace("'", "''")
            txt_path = str(temp_txt).replace("'", "''")
            ps_script = (
                "$word = New-Object -ComObject Word.Application; "
                "$word.Visible = $false; "
                f"$doc = $word.Documents.Open('{open_path}'); "
                f"$txt = '{txt_path}'; "
                "$doc.SaveAs([ref] $txt, [ref] 2); "
                "$doc.Close(); "
                "$word.Quit();"
            )
            subprocess.run(["powershell", "-Command", ps_script], check=True)
            if temp_txt.exists():
                text = temp_txt.read_text(encoding="utf-8", errors="ignore")
                try:
                    temp_txt.unlink()
                except Exception:
                    pass
                return text

    raise RuntimeError("DOC parsing failed. Upload DOCX or PDF for the most reliable results.")


def read_source(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return pdf_to_text(path)
    if suffix == ".docx":
        return docx_to_text(path)
    if suffix == ".doc":
        return doc_to_text(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def build_result(metadata: dict, raw_text: str):
    normalized = normalize_whitespace(raw_text)[:MAX_TEXT_LENGTH]
    paragraphs = split_paragraphs(normalized)
    language = detect_language(normalized)
    title = infer_title(paragraphs, metadata["paper_safe"])
    abstract_text = infer_abstract(paragraphs, language)
    sections = detect_sections(normalized)
    highlights = infer_highlights(paragraphs, abstract_text)

    return {
        "status": "ok",
        "source_path": metadata["paper_original"],
        "normalized_path": metadata["paper_safe"],
        "source_type": metadata["paper_extension"].lstrip("."),
        "language": language,
        "title": title,
        "abstract": abstract_text,
        "highlights": highlights,
        "sections": {key: value[:1200] for key, value in sections.items()},
        "body_excerpt": normalized[:5000],
        "text_length": len(normalized),
    }, normalized


def main():
    parser = argparse.ArgumentParser(description="Parse a normalized academic paper into structured JSON.")
    parser.add_argument("--input", required=True, help="Path to workspace-inputs.json.")
    parser.add_argument("--output-dir", required=True, help="Directory for parsed-paper.json and text outputs.")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = json.loads(input_path.read_text(encoding="utf-8"))
    paper_path = Path(metadata["paper_safe"]).resolve()
    raw_text = read_source(paper_path)
    parsed, normalized_text = build_result(metadata, raw_text)
    assets_dir = output_dir / "extracted-paper-assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    extracted_images = []
    if paper_path.suffix.lower() == ".docx":
        extracted_images.extend(extract_docx_images(paper_path, assets_dir))
    extracted_images.extend(copy_workspace_images(metadata.get("image_candidates", []), assets_dir, len(extracted_images) + 1))

    parsed_path = output_dir / "parsed-paper.json"
    body_path = output_dir / "paper-body.txt"

    body_path.write_text(normalized_text + "\n", encoding="utf-8")
    parsed["body_text_path"] = str(body_path)
    parsed["extracted_images"] = extracted_images
    parsed["extracted_assets_dir"] = str(assets_dir.resolve())
    parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(str(parsed_path))


if __name__ == "__main__":
    main()
