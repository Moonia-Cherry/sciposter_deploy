#!/usr/bin/env python
"""Verify that missing runtime prerequisites fail with actionable messages."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def require_failure(command: list[str], expected: str, env: dict[str, str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    output = result.stdout + result.stderr
    if result.returncode == 0:
        raise AssertionError(f"Command unexpectedly succeeded: {command}")
    if expected not in output:
        raise AssertionError(f"Expected {expected!r} in failure output:\n{output}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    slides = root / "skill-src" / "slides-fastclaw-upload" / "scripts"
    popular = root / "skill-src" / "popular-article-fastclaw-upload" / "scripts"

    with tempfile.TemporaryDirectory(prefix="sciposter-missing-node-") as temporary:
        env = os.environ.copy()
        env["PATH"] = ""
        require_failure(
            [
                sys.executable,
                str(slides / "run_academic_slides_pipeline.py"),
                "--workspace",
                temporary,
                "--output-dir",
                str(Path(temporary) / "output"),
            ],
            "未找到 Node.js",
            env,
        )

    with tempfile.TemporaryDirectory(prefix="sciposter-empty-fonts-") as font_dir:
        env = os.environ.copy()
        env["SCIPOSTER_FONT_DIR"] = font_dir
        code = (
            "import runpy; "
            f"module=runpy.run_path({str(slides / 'render_slides_preview_png.py')!r}); "
            "module['load_font'](20)"
        )
        require_failure([sys.executable, "-c", code], "未找到可用的 Windows 中文字体", env)

    require_failure(
        [sys.executable, "-S", str(popular / "render_article_exports.py"), "--help"],
        "缺少 portable Python 依赖",
        os.environ.copy(),
    )
    print("PASS actionable runtime prerequisite errors")


if __name__ == "__main__":
    main()
