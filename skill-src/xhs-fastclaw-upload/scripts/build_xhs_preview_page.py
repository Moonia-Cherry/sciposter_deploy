#!/usr/bin/env python
import argparse
import html
import json
from pathlib import Path


def esc(value: str) -> str:
    return html.escape(str(value or ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Xiaohongshu preview page from the generated package JSON.")
    parser.add_argument("--input", required=True, help="Path to xiaohongshu-package.json.")
    parser.add_argument("--output", required=True, help="Path to xiaohongshu-preview.html.")
    args = parser.parse_args()

    package = json.loads(Path(args.input).read_text(encoding="utf-8"))
    images = package.get("generated_images", []) or []
    hashtags = package.get("hashtags", []) or []

    image_html = []
    for idx, image_name in enumerate(images, start=1):
        image_html.append(
            """
            <section class="image-card">
              <div class="meta">
                <strong>Card {idx}</strong>
                <a class="link" href="./xiaohongshu-images/{name}" target="_blank">{name}</a>
              </div>
              <img src="./xiaohongshu-images/{name}" alt="{name}" />
            </section>
            """.format(idx=idx, name=esc(image_name))
        )

    html_text = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>小红书图文预览</title>
  <style>
    :root {{
      --bg: #f8f3ee;
      --paper: #fffdfa;
      --ink: #1f2937;
      --muted: #6b7280;
      --accent: #da6a46;
      --line: #ecd9cf;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background: linear-gradient(180deg, #fdf8f3 0%, var(--bg) 100%);
    }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
    .hero {{ background: rgba(255,255,255,0.96); border: 1px solid var(--line); border-radius: 28px; padding: 22px; margin-bottom: 18px; }}
    .toolbar {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 14px 0 18px; }}
    .btn {{ background: var(--accent); color: white; padding: 10px 14px; border-radius: 999px; text-decoration: none; font-weight: 700; }}
    h1, p {{ margin: 0; }}
    h1 {{ font-size: 36px; line-height: 1.15; }}
    .subtitle {{ margin-top: 14px; color: var(--muted); line-height: 1.8; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }}
    .chip {{ background: #fde8df; color: var(--accent); border-radius: 999px; padding: 8px 12px; font-weight: 700; }}
    .image-card {{ background: rgba(255,255,255,0.96); border: 1px solid var(--line); border-radius: 28px; padding: 18px; margin-bottom: 18px; }}
    .meta {{ display: flex; justify-content: space-between; align-items: center; color: var(--muted); margin-bottom: 10px; gap: 12px; }}
    .link {{ color: var(--accent); text-decoration: none; font-weight: 700; }}
    img {{ width: 100%; display: block; border-radius: 20px; border: 1px solid #ead8cb; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>{title}</h1>
      <p class="subtitle">{summary}</p>
      <div class="toolbar">
        <a class="btn" href="./xiaohongshu-package.docx">打开 DOCX 总说明</a>
      </div>
      <div class="chips">{chips}</div>
    </section>
    {images_html}
  </div>
</body>
</html>
""".format(
        title=esc(package.get("chosen_title", "小红书图文方案")),
        summary=esc(package.get("summary", "")),
        chips="".join("<span class='chip'>{0}</span>".format(esc(tag)) for tag in hashtags),
        images_html="".join(image_html),
    )

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_text, encoding="utf-8")
    print(str(output))


if __name__ == "__main__":
    main()
