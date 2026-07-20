#!/usr/bin/env python
import argparse
import json
import re
from pathlib import Path


def split_sentences(text: str):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def first_nonempty(lines):
    for line in lines:
        line = line.strip()
        if line:
            return line
    return ""


def summarize_points(text: str, limit: int):
    sentences = split_sentences(text)
    if sentences:
        return sentences[:limit]
    chunks = [line.strip("-* \t") for line in text.splitlines() if line.strip()]
    return chunks[:limit]


def build_brief(text: str):
    lines = [line.rstrip() for line in text.splitlines()]
    title = first_nonempty(lines)
    summary_points = summarize_points(text, 8)
    hero = summary_points[:3]

    return {
        "poster_type": "academic",
        "theme": {
            "tone": "clean",
            "accent_color": "",
            "layout": "three-column",
        },
        "paper": {
            "title": title,
            "authors": [],
            "affiliation": "",
            "venue": "",
            "year": "",
            "keywords": [],
        },
        "hero": {
            "headline": title or "Research Poster Draft",
            "subheadline": summary_points[0] if summary_points else "",
            "key_findings": hero,
        },
        "sections": [
            {
                "id": "background",
                "title": "Background",
                "kind": "bullets",
                "content": summary_points[:2],
                "layout_hints": {"priority": "medium", "column_span": 1},
            },
            {
                "id": "method",
                "title": "Method",
                "kind": "bullets",
                "content": summary_points[2:4],
                "layout_hints": {"priority": "medium", "column_span": 1},
            },
            {
                "id": "results",
                "title": "Results",
                "kind": "bullets",
                "content": summary_points[4:7],
                "layout_hints": {"priority": "high", "column_span": 1},
            },
            {
                "id": "conclusion",
                "title": "Conclusion",
                "kind": "bullets",
                "content": summary_points[7:8],
                "layout_hints": {"priority": "high", "column_span": 1},
            },
        ],
        "figures": [
            {
                "id": "fig1",
                "title": "Main figure",
                "purpose": "Show the most important visual evidence.",
                "source_needed": True,
                "caption": "",
                "placement_hint": "center-right",
            }
        ],
        "footer": {
            "references": [],
            "contact": "",
            "acknowledgements": "",
        },
        "missing_information": [
            "authors",
            "affiliation",
            "venue",
            "year",
            "references",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Build a first-pass academic poster brief JSON.")
    parser.add_argument("--input", required=True, help="Path to source text file.")
    parser.add_argument("--output", required=True, help="Path to output JSON file.")
    args = parser.parse_args()

    source = Path(args.input)
    output = Path(args.output)
    text = source.read_text(encoding="utf-8")
    brief = build_brief(text)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(output))


if __name__ == "__main__":
    main()
