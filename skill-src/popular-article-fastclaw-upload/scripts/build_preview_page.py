#!/usr/bin/env python
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to popular-article-package.json.")
    parser.add_argument("--output", required=True, help="Path to popular-article-preview.html.")
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    package = json.loads(Path(args.input).read_text(encoding="utf-8"))
    asset_images = package.get("asset_images", [])
    has_cover = (output_path.parent / "wechat-cover.png").exists()

    image_cards = []
    for image_name in asset_images:
        image_cards.append(
            f"""
            <figure class="paper-asset">
              <img src="./extracted-paper-assets/{image_name}" alt="{image_name}" />
              <figcaption>从论文中提取的可用配图：{image_name}</figcaption>
            </figure>
            """
        )

    section_html = []
    fallback = [
        "建议在这里插入论文中的方法框架图，帮助读者快速理解研究路径。",
        "建议在这里插入论文中的实验结果图，把结论讲得更直观。",
        "建议在这里插入示意图、概念图或论文截图，提升阅读节奏。",
    ]
    for index, section in enumerate(package.get("sections", [])):
        paragraphs = "".join(f"<p>{paragraph}</p>" for paragraph in section.get("paragraphs", []))
        if index < len(asset_images):
            visual_block = f"""
            <figure class="inline-visual">
              <img src="./extracted-paper-assets/{asset_images[index]}" alt="{asset_images[index]}" />
              <figcaption>建议插在这一段之后的论文原图素材</figcaption>
            </figure>
            """
        else:
            visual_block = f"""
            <div class="inline-placeholder">
              <strong>建议配图位置</strong>
              <p>{fallback[min(index, len(fallback) - 1)]}</p>
            </div>
            """
        section_html.append(
            f"""
            <section class="article-section">
              <h2>{section.get('heading', '')}</h2>
              {paragraphs}
              {visual_block}
            </section>
            """
        )

    cover_block = "<div class='cover-preview'><img src='./wechat-cover.png' alt='wechat cover preview' /></div>" if has_cover else ""

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{package.get("title", "公众号文章预览")}</title>
  <style>
    :root {{
      --bg: #f6f1ea;
      --paper: #fffdfa;
      --ink: #1f2937;
      --muted: #6b7280;
      --accent: #135d66;
      --accent-2: #d97841;
      --line: #eadfce;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(19, 93, 102, 0.10), transparent 24%),
        radial-gradient(circle at bottom left, rgba(217, 120, 65, 0.10), transparent 26%),
        var(--bg);
      font-family: "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
    }}
    .wrap {{ max-width: 1280px; margin: 0 auto; padding: 28px 20px 44px; }}
    .toolbar {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 14px;
      border-radius: 999px;
      text-decoration: none;
      background: var(--accent-2);
      color: white;
      font-weight: 700;
    }}
    .hero {{ display: grid; grid-template-columns: 1.3fr 0.85fr; gap: 18px; margin-bottom: 18px; }}
    .panel {{
      background: rgba(255,255,255,0.93);
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: 24px;
      box-shadow: 0 18px 40px rgba(31, 41, 55, 0.06);
    }}
    .cover {{
      min-height: 320px;
      background:
        linear-gradient(135deg, rgba(19, 93, 102, 0.10), rgba(217, 120, 65, 0.08)),
        var(--paper);
    }}
    .cover-preview {{
      margin-top: 18px;
      border-radius: 22px;
      overflow: hidden;
      border: 1px solid var(--line);
      background: white;
    }}
    .cover-preview img {{ display: block; width: 100%; }}
    .eyebrow {{
      display: inline-block;
      margin-bottom: 14px;
      color: var(--accent);
      letter-spacing: 0.08em;
      font-weight: 800;
      text-transform: uppercase;
    }}
    h1, h2, h3, p {{ margin: 0; }}
    h1 {{ font-size: 40px; line-height: 1.16; max-width: 14ch; }}
    .summary {{ margin-top: 16px; color: var(--muted); line-height: 1.9; max-width: 58ch; }}
    .source-note {{
      margin-top: 18px;
      padding: 14px 16px;
      border-radius: 18px;
      background: #edf7f7;
      color: #11454b;
      line-height: 1.75;
    }}
    .layout {{ display: grid; grid-template-columns: 1.18fr 0.82fr; gap: 18px; align-items: start; }}
    .article-body {{ display: grid; gap: 16px; }}
    .article-section {{ border: 1px solid var(--line); background: var(--paper); border-radius: 24px; padding: 22px; }}
    .article-section h2 {{ font-size: 26px; margin-bottom: 14px; }}
    .article-section p {{ line-height: 1.95; margin-top: 10px; color: #374151; }}
    .inline-visual, .inline-placeholder {{
      margin-top: 18px;
      border-radius: 20px;
      overflow: hidden;
      background: #f8f5f1;
      border: 1px dashed var(--line);
      padding: 16px;
    }}
    .inline-visual img, .paper-asset img {{ width: 100%; display: block; border-radius: 14px; background: #fff; }}
    .inline-visual figcaption, .paper-asset figcaption {{ margin-top: 10px; color: var(--muted); font-size: 14px; }}
    .sidebar {{ display: grid; gap: 18px; }}
    .paper-gallery {{ display: grid; gap: 14px; }}
    .paper-asset {{ margin: 0; padding: 14px; border: 1px solid var(--line); border-radius: 22px; background: #fff; }}
    .empty-state {{ color: var(--muted); line-height: 1.8; margin: 0; }}
    ul {{ padding-left: 20px; margin: 12px 0 0; display: grid; gap: 10px; }}
    @media (max-width: 1024px) {{
      .hero, .layout {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="toolbar">
      <a class="btn" href="./popular-article.docx">下载 DOCX</a>
      <a class="btn" href="./popular-article.pdf">下载 PDF</a>
      <a class="btn" href="./popular-article.md">下载 Markdown</a>
      <a class="btn" href="./popular-article-package.json">下载 JSON</a>
      <a class="btn" href="./wechat-cover.png">下载头图 PNG</a>
      <a class="btn" href="./wechat-cover.pptx">下载头图 PPT</a>
    </div>
    <section class="hero">
      <div class="panel cover">
        <div class="eyebrow">WeChat Article Preview</div>
        <h1>{package.get("title", "")}</h1>
        <p class="summary">{package.get("summary", "")}</p>
        <div class="source-note">{package.get("asset_note", "")}</div>
        {cover_block}
      </div>
      <div class="panel">
        <div class="eyebrow">发布建议</div>
        <h3>当前已经生成标准成稿、导出文件和公众号头图</h3>
        <ul>{"".join(f"<li>{item}</li>" for item in package.get("next_steps", []))}</ul>
      </div>
    </section>
    <section class="layout">
      <article class="panel article-body">
        {''.join(section_html)}
      </article>
      <aside class="sidebar">
        <section class="panel">
          <div class="eyebrow">论文配图</div>
          <h3>从论文中提取的素材</h3>
          <div class="paper-gallery">{''.join(image_cards) or '<p class="empty-state">当前没有自动提取到论文内嵌图片，但正文中已经预留配图位置。</p>'}</div>
        </section>
      </aside>
    </section>
  </div>
</body>
</html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(str(output_path))


if __name__ == "__main__":
    main()
