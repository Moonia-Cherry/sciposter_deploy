#!/usr/bin/env python
import argparse
import json
from pathlib import Path


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8" />
<title>{title}</title>
<style>
body{{font-family:"Segoe UI","Microsoft YaHei",sans-serif;background:#eef3f8;color:#17324d;margin:0;padding:28px;}}
.shell{{max-width:1180px;margin:0 auto;}}
.hero{{background:#fff;border:1px solid #d7e2ee;border-radius:24px;padding:28px 32px;box-shadow:0 18px 48px rgba(20,75,139,.08);margin-bottom:24px;}}
.hero h1{{margin:0 0 10px;font-size:34px;}}
.hero p{{margin:6px 0 0;line-height:1.7;color:#52657b;}}
.actions{{margin-top:18px;display:flex;gap:12px;flex-wrap:wrap;}}
.btn{{display:inline-block;padding:12px 18px;border-radius:14px;background:#144b8b;color:#fff;text-decoration:none;font-weight:600;}}
.btn.secondary{{background:#e8f0fa;color:#144b8b;}}
.slide{{background:#fff;border:1px solid #d7e2ee;border-radius:24px;padding:22px;margin-bottom:20px;box-shadow:0 12px 36px rgba(20,75,139,.06);}}
.slide h2{{margin:0 0 12px;font-size:22px;}}
.slide img{{width:100%;display:block;border-radius:18px;border:1px solid #d7e2ee;background:#fff;}}
.meta{{font-size:14px;color:#6b7c90;margin-top:8px;}}
</style>
<div class="shell">
  <div class="hero">
    <h1>{title}</h1>
    <p>{summary}</p>
    <div class="actions">
      <a class="btn" href="./slides.pptx">下载可编辑 PPTX</a>
      <a class="btn secondary" href="./slides-outline.md">查看大纲</a>
      <a class="btn secondary" href="./speaker-notes.md">查看讲稿备注</a>
    </div>
  </div>
  {slides_html}
</div>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to slides-package.json")
    parser.add_argument("--output", required=True, help="Path to slides-preview.html")
    args = parser.parse_args()

    package = json.loads(Path(args.input).read_text(encoding="utf-8"))
    output = Path(args.output).resolve()
    slides_html = []

    for idx, slide in enumerate(package.get("slides", []), start=1):
        rel = "./slides-pages/slide-{0:02d}.png".format(idx)
        slides_html.append(
            """<section class="slide">
  <h2>第 {index} 页：{title}</h2>
  <img src="{src}" alt="Slide {index}" />
  <div class="meta">{subtitle}</div>
</section>""".format(
                index=idx,
                title=slide.get("title", "Slide"),
                src=rel,
                subtitle=slide.get("subtitle", ""),
            )
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        HTML_TEMPLATE.format(
            title=package.get("title", "Slides Preview").replace("{", "{{").replace("}", "}}"),
            summary=package.get("summary", "").replace("{", "{{").replace("}", "}}"),
            slides_html="\n".join(slides_html),
        ),
        encoding="utf-8",
    )
    print(str(output))


if __name__ == "__main__":
    main()
