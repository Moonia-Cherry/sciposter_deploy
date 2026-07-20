#!/usr/bin/env python
import argparse
import base64
import html
import json
import mimetypes
from pathlib import Path


def esc(text: str) -> str:
    return html.escape(text or "")


def file_data_uri(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def text_block(lines, x, y, font_size, color, weight="400", line_gap=1.28):
    spans = []
    dy = 0
    for line in lines:
        spans.append(f'<tspan x="{x}" y="{y + dy}">{esc(line)}</tspan>')
        dy += int(font_size * line_gap)
    return f'<text x="{x}" y="{y}" font-size="{font_size}" fill="{color}" font-weight="{weight}" font-family="Arial, Microsoft YaHei, sans-serif">{"".join(spans)}</text>'


def wrap_text(text: str, max_chars: int):
    text = (text or "").strip()
    if not text:
        return [""]
    words = text.split()
    if len(words) <= 1:
        return [text[:max_chars], text[max_chars: max_chars * 2].strip()] if len(text) > max_chars else [text]
    lines = []
    current = []
    for word in words:
        trial = " ".join(current + [word]).strip()
        if current and len(trial) > max_chars:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return [line for line in lines[:2] if line]


def wrap_lines(text: str, max_chars: int, max_lines: int = 2):
    lines = wrap_text(text, max_chars)
    if not lines:
        return [""]
    return lines[:max_lines]


def panel(title, items, x, y, w, h, accent, body, title_size=22, body_size=15):
    lines = [f"- {item}" for item in (items or [])[:3]]
    return "".join(
        [
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" ry="6" fill="#FFFFFF" stroke="{accent}" stroke-opacity="0.22" stroke-width="2"/>',
            text_block([title], x + 18, y + 34, title_size, accent, "700"),
            text_block(lines, x + 20, y + 68, body_size, body),
        ]
    )


def render(spec: dict, output: Path):
    theme = spec.get("theme", {})
    paper = spec.get("paper", {})
    hero = spec.get("hero", {})
    sections = spec.get("sections", [])
    figures = spec.get("figures", [])
    footer = spec.get("footer", {})

    bg = theme.get("background", "#F7FAFC")
    accent = theme.get("accent_color", "#1E5AA8")
    headline = theme.get("headline_color", "#163A63")
    muted = theme.get("muted_color", "#5B6B7F")

    sec0 = sections[0] if len(sections) > 0 else {"title": "Background", "content": []}
    sec1 = sections[1] if len(sections) > 1 else {"title": "Method", "content": []}
    sec2 = sections[2] if len(sections) > 2 else {"title": "Results", "content": []}
    sec3 = sections[3] if len(sections) > 3 else {"title": "Conclusion", "content": []}
    title_lines = wrap_text(paper.get("title") or hero.get("headline") or "Academic Poster", 54)
    author_lines = wrap_lines("; ".join(paper.get("authors") or ["Authors TBD"]), 96, 2)
    affiliation_lines = wrap_lines(paper.get("affiliation") or "Affiliation TBD", 94, 2)
    hero_top = 286 if len(affiliation_lines) > 1 else 270

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">',
        f'<rect width="1920" height="1080" fill="{bg}"/>',
        f'<rect x="0" y="0" width="1920" height="78" fill="{accent}"/>',
        text_block(title_lines, 70, 126, 34 if len(" ".join(title_lines)) > 96 else 38, headline, "700", 1.16),
        text_block(author_lines, 72, 196, 17, muted),
        text_block(affiliation_lines, 72, 232, 15, muted),
        f'<rect x="70" y="{hero_top}" width="1180" height="88" rx="6" ry="6" fill="{accent}" fill-opacity="0.08"/>',
        f'<rect x="1290" y="{hero_top}" width="560" height="88" rx="6" ry="6" fill="{accent}" fill-opacity="0.08"/>',
        text_block(wrap_text(hero.get("subheadline") or "Poster summary", 88), 96, hero_top + 34, 20, headline, "700", 1.16),
        text_block(["Key Highlights"] + [f"- {item}" for item in (hero.get("key_findings") or [])[:2]], 1318, hero_top + 27, 16, headline, "700", 1.14),
        panel(sec0.get("title", "Background"), sec0.get("content", []), 70, hero_top + 122, 560, 150, accent, headline, 22, 15),
        panel(sec1.get("title", "Method"), sec1.get("content", []), 70, hero_top + 292, 560, 150, accent, headline, 22, 15),
        panel(sec2.get("title", "Results"), sec2.get("content", []), 700, hero_top + 122, 700, 150, accent, headline, 22, 15),
        panel(sec3.get("title", "Conclusion"), sec3.get("content", []), 1450, hero_top + 122, 400, 180, accent, headline, 21, 14),
        panel("References", (footer.get("references") or [])[:3], 1450, 745, 400, 145, accent, headline, 18, 12),
    ]

    frames = [
        {"x": 700, "y": hero_top + 292, "w": 330, "h": 175},
        {"x": 1055, "y": hero_top + 292, "w": 330, "h": 175},
        {"x": 700, "y": hero_top + 492, "w": 685, "h": 130},
    ]
    for idx, frame in enumerate(frames):
        fig = figures[idx] if idx < len(figures) else {}
        out.append(f'<rect x="{frame["x"]}" y="{frame["y"]}" width="{frame["w"]}" height="{frame["h"]}" rx="4" ry="4" fill="#FFFFFF" stroke="{accent}" stroke-opacity="0.18" stroke-width="1"/>')
        fig_path = fig.get("path", "")
        if fig_path and Path(fig_path).exists():
            out.append(f'<image href="{file_data_uri(Path(fig_path))}" x="{frame["x"]+6}" y="{frame["y"]+6}" width="{frame["w"]-12}" height="{frame["h"]-12}" preserveAspectRatio="xMidYMid meet"/>')
        else:
            out.append(text_block(["Figure placeholder"], frame["x"] + 46, frame["y"] + 88, 18, muted))
        out.append(text_block([fig.get("caption") or fig.get("title") or f"Figure {idx+1}"], frame["x"], frame["y"] + frame["h"] + 20, 12, muted))

    out.extend(
        [
            text_block([f'Style: {theme.get("style_id", "classic-blue")} | Template: {theme.get("template_id", "conference-classic")}'], 1468, 920, 12, muted),
            f'<rect x="70" y="1000" width="1780" height="26" fill="{accent}" fill-opacity="0.92"/>',
            text_block(["Generated by academic-poster skill. SVG preview remains scalable."], 85, 1018, 12, "#FFFFFF"),
            "</svg>",
        ]
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(out), encoding="utf-8")
    print(str(output))


def main():
    parser = argparse.ArgumentParser(description="Render a scalable SVG poster preview.")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    render(spec, Path(args.output))


if __name__ == "__main__":
    main()
