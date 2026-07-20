#!/usr/bin/env python
import argparse
import json
import os
import textwrap
from pathlib import Path


try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
except ImportError as exc:
    raise RuntimeError(
        "缺少 portable Python 依赖 Pillow。请校验 runtime/python 并重新运行 deploy.ps1。"
    ) from exc


WIDTH = 1600
HEIGHT = 900
BG = "#EEF3F8"
CANVAS = "#FFFFFF"
ACCENT = "#144B8B"
ACCENT_LIGHT = "#E8F0FA"
TEXT = "#17324D"
MUTED = "#64748B"
BORDER = "#D6E1EE"


def load_font(size, bold=False):
    override = os.environ.get("SCIPOSTER_FONT_DIR")
    font_root = Path(override) if override else Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates = []
    if bold:
        candidates.extend(
            [
                font_root / "msyhbd.ttc",
                font_root / "simhei.ttf",
            ]
        )
    candidates.extend(
        [
            font_root / "msyh.ttc",
            font_root / "simhei.ttf",
            font_root / "simsun.ttc",
        ]
    )
    for path in candidates:
        try:
            if Path(path).exists():
                return ImageFont.truetype(str(path), size=size)
        except Exception:
            pass
    raise RuntimeError(
        "未找到可用的 Windows 中文字体。请安装 Microsoft YaHei（msyh.ttc/msyhbd.ttc）后重新部署。"
    )


def clean(text):
    return " ".join(str(text or "").replace("\r", " ").replace("\n", " ").split()).strip()


def wrap(text, width, max_lines):
    value = clean(text)
    if not value:
        return []
    lines = textwrap.wrap(value, width=width) or [value[:width]]
    return lines[:max_lines]


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def save_slide(image, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(output_path))


def draw_lines(draw, origin, lines, font, fill, line_gap):
    x, y = origin
    for index, line in enumerate(lines):
        draw.text((x, y + index * line_gap), line, font=font, fill=fill)


def resolve_image_path(value):
    if not value:
        return None
    candidate = Path(str(value))
    if candidate.exists():
        return candidate
    return None


def paste_figure(canvas, figure_path, box):
    resolved = resolve_image_path(figure_path)
    if not resolved:
        return False
    try:
        figure = Image.open(resolved).convert("RGB")
    except Exception:
        return False
    max_w = box[2] - box[0]
    max_h = box[3] - box[1]
    figure.thumbnail((max_w, max_h))
    x = box[0] + (max_w - figure.width) // 2
    y = box[1] + (max_h - figure.height) // 2
    canvas.paste(figure, (x, y))
    return True


def render_title_slide(draw, canvas, slide, idx, total, title_font, subtitle_font, body_font):
    rounded(draw, (64, 54, WIDTH - 64, HEIGHT - 54), 34, CANVAS, outline=BORDER, width=2)
    rounded(draw, (64, 54, WIDTH - 64, 94), 20, ACCENT)
    draw.text((110, 128), clean(slide.get("title", "")), font=title_font, fill=TEXT)
    draw.text((114, 228), clean(slide.get("subtitle", "")), font=subtitle_font, fill=ACCENT)

    y = 320
    for bullet in slide.get("bullets", [])[:3]:
        lines = wrap("- " + bullet, 34, 3)
        draw_lines(draw, (122, y), lines, body_font, TEXT, 42)
        y += 42 * len(lines) + 18

    rounded(draw, (930, 210, 1440, 660), 28, ACCENT_LIGHT, outline="#D7E4F4", width=2)
    draw.text((980, 260), "核心配图区", font=subtitle_font, fill=ACCENT)
    pasted = paste_figure(canvas, slide.get("figure_image"), (970, 320, 1400, 620))
    if not pasted:
        draw_lines(draw, (980, 340), wrap(slide.get("figure_hint", ""), 18, 5), body_font, MUTED, 34)

    draw.text((110, HEIGHT - 102), "SciPoster 组会汇报模板", font=load_font(20), fill=MUTED)
    draw.text((WIDTH - 174, HEIGHT - 102), "{0}/{1}".format(idx, total), font=load_font(20, bold=True), fill=ACCENT)


def render_agenda_slide(draw, slide, idx, total, title_font, subtitle_font, body_font):
    rounded(draw, (64, 54, WIDTH - 64, HEIGHT - 54), 34, CANVAS, outline=BORDER, width=2)
    draw.text((96, 96), clean(slide.get("title", "")), font=title_font, fill=TEXT)
    draw.text((98, 164), clean(slide.get("subtitle", "")), font=subtitle_font, fill=MUTED)

    card_y = 280
    for card_idx, bullet in enumerate(slide.get("bullets", [])[:3], start=1):
        x1 = 112 + (card_idx - 1) * 454
        x2 = x1 + 390
        rounded(draw, (x1, card_y, x2, card_y + 270), 28, ACCENT_LIGHT, outline="#D7E4F4", width=2)
        rounded(draw, (x1 + 28, card_y + 26, x1 + 110, card_y + 86), 18, ACCENT)
        draw.text((x1 + 56, card_y + 44), str(card_idx), font=load_font(22, bold=True), fill="#FFFFFF")
        draw_lines(draw, (x1 + 30, card_y + 124), wrap(bullet, 14, 5), body_font, TEXT, 40)

    draw.text((WIDTH - 174, HEIGHT - 102), "{0}/{1}".format(idx, total), font=load_font(20, bold=True), fill=ACCENT)


def render_content_slide(draw, canvas, slide, idx, total, title_font, subtitle_font, body_font, small_font):
    rounded(draw, (64, 54, WIDTH - 64, HEIGHT - 54), 34, CANVAS, outline=BORDER, width=2)
    rounded(draw, (64, 54, WIDTH - 64, 88), 18, ACCENT)
    draw.text((96, 108), clean(slide.get("title", "")), font=title_font, fill=TEXT)
    draw.text((98, 174), clean(slide.get("subtitle", "")), font=subtitle_font, fill=MUTED)

    rounded(draw, (96, 232, 910, 770), 26, "#F9FBFE", outline=BORDER, width=2)
    draw.text((126, 264), "关键要点", font=load_font(24, bold=True), fill=ACCENT)

    y = 322
    for bullet in slide.get("bullets", [])[:4]:
        lines = wrap("- " + bullet, 31, 4)
        draw_lines(draw, (132, y), lines, body_font, TEXT, 34)
        y += 34 * len(lines) + 18
        if y > 700:
            break

    rounded(draw, (944, 232, 1440, 770), 26, ACCENT_LIGHT, outline="#D7E4F4", width=2)
    draw.text((978, 264), "建议配图", font=load_font(24, bold=True), fill=ACCENT)
    pasted = paste_figure(canvas, slide.get("figure_image"), (978, 318, 1396, 688))
    if not pasted:
        draw_lines(draw, (978, 334), wrap(slide.get("figure_hint", ""), 17, 6), body_font, MUTED, 34)
        rounded(draw, (978, 520, 1398, 720), 20, "#FFFFFF", outline="#CAD8EA", width=2)
        draw.text((1018, 560), "这里建议替换为", font=small_font, fill=TEXT)
        draw.text((1018, 594), "论文中的图表、流程图", font=small_font, fill=TEXT)
        draw.text((1018, 628), "或关键结果表格。", font=small_font, fill=TEXT)
        draw.text((1018, 668), "正式展示时视觉效果会更完整。", font=small_font, fill=MUTED)

    draw.text((96, HEIGHT - 102), "已包含可编辑 PPTX 导出", font=small_font, fill=MUTED)
    draw.text((WIDTH - 174, HEIGHT - 102), "{0}/{1}".format(idx, total), font=load_font(20, bold=True), fill=ACCENT)


def render_qa_slide(draw, slide, idx, total, title_font, subtitle_font, body_font):
    rounded(draw, (64, 54, WIDTH - 64, HEIGHT - 54), 34, CANVAS, outline=BORDER, width=2)
    draw.text((96, 108), clean(slide.get("title", "")), font=title_font, fill=TEXT)
    draw.text((98, 174), clean(slide.get("subtitle", "")), font=subtitle_font, fill=MUTED)

    y = 280
    for question in slide.get("bullets", [])[:3]:
        rounded(draw, (118, y, WIDTH - 118, y + 132), 24, ACCENT_LIGHT, outline="#D7E4F4", width=2)
        draw_lines(draw, (154, y + 34), wrap(question, 42, 3), body_font, TEXT, 34)
        y += 156

    draw.text((WIDTH - 174, HEIGHT - 102), "{0}/{1}".format(idx, total), font=load_font(20, bold=True), fill=ACCENT)


def render_slide(slide, idx, total):
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    title_font = load_font(42, bold=True)
    subtitle_font = load_font(24)
    body_font = load_font(24)
    small_font = load_font(20)
    layout = slide.get("layout", "content")
    if layout == "title":
        render_title_slide(draw, image, slide, idx, total, title_font, subtitle_font, body_font)
    elif layout == "agenda":
        render_agenda_slide(draw, slide, idx, total, title_font, subtitle_font, body_font)
    elif layout == "qa":
        render_qa_slide(draw, slide, idx, total, title_font, subtitle_font, body_font)
    else:
        render_content_slide(draw, image, slide, idx, total, title_font, subtitle_font, body_font, small_font)
    return image


def save_collage(images, output_path):
    cols = 2
    thumb_w = 720
    thumb_h = int(thumb_w * HEIGHT / WIDTH)
    padding = 40
    header_h = 120
    rows = (len(images) + cols - 1) // cols
    canvas_w = padding + cols * thumb_w + (cols - 1) * padding + padding
    canvas_h = header_h + rows * thumb_h + max(0, rows - 1) * padding + padding
    canvas = Image.new("RGB", (canvas_w, canvas_h), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((padding, 30), "组会 PPT 总览预览", font=load_font(42, bold=True), fill=TEXT)
    draw.text((padding, 78), "右侧显示为整套缩略图，逐页查看请打开 slides-preview.html。", font=load_font(22), fill=MUTED)
    for idx, image in enumerate(images):
        row = idx // cols
        col = idx % cols
        x = padding + col * (thumb_w + padding)
        y = header_h + row * (thumb_h + padding)
        thumb = image.copy()
        thumb.thumbnail((thumb_w, thumb_h))
        canvas.paste(thumb, (x, y))
        draw.rounded_rectangle((x, y, x + thumb.width, y + thumb.height), radius=18, outline=BORDER, width=2)
        draw.rounded_rectangle((x + 16, y + 16, x + 120, y + 56), radius=14, fill=ACCENT)
        draw.text((x + 38, y + 26), "第 {0} 页".format(idx + 1), font=load_font(18, bold=True), fill="#FFFFFF")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(output_path))


def main():
    parser = argparse.ArgumentParser(description="Render slide preview images for the generated deck.")
    parser.add_argument("--input", required=True, help="Path to slides-package.json")
    parser.add_argument("--output", required=True, help="Path to slides-preview.png")
    args = parser.parse_args()

    package = json.loads(Path(args.input).read_text(encoding="utf-8"))
    output_path = Path(args.output).resolve()
    slides_dir = output_path.parent / "slides-pages"
    slides = package.get("slides", [])

    rendered_images = []
    for idx, slide in enumerate(slides, start=1):
        image = render_slide(slide, idx, len(slides))
        rendered_images.append(image)
        slide_path = slides_dir / ("slide-{0:02d}.png".format(idx))
        save_slide(image, slide_path)

    if rendered_images:
        save_collage(rendered_images, output_path)

    print(str(output_path))


if __name__ == "__main__":
    main()
