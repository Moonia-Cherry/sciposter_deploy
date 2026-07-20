#!/usr/bin/env python
import argparse
from pathlib import Path


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Academic Poster Preview</title>
  <style>
    body { font-family: Arial, "Microsoft YaHei", sans-serif; margin: 0; background: #f3f6fb; color: #14385f; }
    .wrap { max-width: 1200px; margin: 24px auto; padding: 0 16px 32px; }
    .bar { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; }
    a.btn { background: #1E5AA8; color: white; padding: 10px 14px; border-radius: 8px; text-decoration: none; font-weight: 600; }
    .card { background: white; border-radius: 14px; padding: 14px; box-shadow: 0 10px 30px rgba(20, 56, 95, 0.08); }
    img, object { width: 100%; border-radius: 10px; background: white; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="bar">
      <a class="btn" href="./academic-poster.pptx">Download PPTX</a>
      <a class="btn" href="./academic-poster.svg">Download SVG</a>
      <a class="btn" href="./academic-poster.png">Download PNG</a>
      <a class="btn" href="./poster-spec.json">Download Spec</a>
    </div>
    <div class="card">
      <object data="./academic-poster.svg" type="image/svg+xml">
        <img src="./academic-poster.png" alt="Poster Preview" />
      </object>
    </div>
  </div>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Build a simple preview page.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(HTML, encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()
