#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

// createRequire honors NODE_PATH, which deploy.ps1 points at the package's
// portable runtime/node/node_modules directory. This keeps the skill portable
// after FastClaw copies it into an agent-private home directory.
const require = createRequire(import.meta.url);
function requireRuntimePackage(name) {
  try {
    return require(name);
  } catch (error) {
    throw new Error(
      `Missing portable Node dependency '${name}'. Verify runtime/node/node_modules and rerun deploy.ps1.`,
      { cause: error },
    );
  }
}
const PptxGenJS = requireRuntimePackage("pptxgenjs");
const sharp = requireRuntimePackage("sharp");

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key.startsWith("--")) throw new Error(`Unexpected argument: ${key}`);
    if (!value || value.startsWith("--")) {
      args[key.slice(2)] = true;
    } else {
      args[key.slice(2)] = value;
      index += 1;
    }
  }
  return args;
}

function must(args, name) {
  if (!args[name]) throw new Error(`Missing --${name}`);
  return args[name];
}

function color(value, fallback) {
  return String(value || fallback).replace(/^#/, "").toUpperCase();
}

function list(value) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function bulletText(items) {
  return list(items).map((item) => `• ${item}`).join("\n");
}

function addPanel(slide, pptx, theme, x, y, w, h, title, items, titleSize = 18, bodySize = 12) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h,
    rectRadius: 0.04,
    fill: { color: color(theme.panel_bg, "FFFFFF") },
    line: { color: color(theme.accent_color, "1E5AA8"), transparency: 72, width: 1 },
  });
  slide.addText(title, {
    x: x + 0.15, y: y + 0.10, w: w - 0.30, h: 0.28,
    fontFace: theme.body_font || "Microsoft YaHei", fontSize: titleSize,
    bold: true, color: color(theme.accent_color, "1E5AA8"),
    margin: 0, breakLine: false,
  });
  slide.addText(bulletText(items), {
    x: x + 0.16, y: y + 0.43, w: w - 0.32, h: h - 0.55,
    fontFace: theme.body_font || "Microsoft YaHei", fontSize: bodySize,
    color: color(theme.headline_color, "163A63"),
    margin: 0.02, breakLine: false, valign: "top", fit: "shrink",
  });
}

function addFigure(slide, pptx, theme, figure, frame, index) {
  slide.addShape(pptx.ShapeType.rect, {
    ...frame,
    fill: { color: "FFFFFF" },
    line: { color: color(theme.accent_color, "1E5AA8"), transparency: 76, width: 1 },
  });
  if (figure?.path) {
    slide.addImage({ path: path.resolve(figure.path), x: frame.x + 0.04, y: frame.y + 0.04, w: frame.w - 0.08, h: frame.h - 0.08 });
  } else {
    slide.addText("Figure placeholder", {
      x: frame.x + 0.15, y: frame.y + frame.h / 2 - 0.16, w: frame.w - 0.30, h: 0.32,
      fontFace: theme.body_font || "Microsoft YaHei", fontSize: 12,
      align: "center", color: color(theme.muted_color, "5B6B7F"), margin: 0,
    });
  }
  slide.addText(figure?.caption || figure?.title || `Figure ${index + 1}`, {
    x: frame.x, y: frame.y + frame.h + 0.04, w: frame.w, h: 0.19,
    fontFace: theme.body_font || "Microsoft YaHei", fontSize: 9,
    align: "center", color: color(theme.muted_color, "5B6B7F"), margin: 0,
    fit: "shrink",
  });
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const specPath = path.resolve(must(args, "spec"));
  const outputPath = path.resolve(must(args, "output"));
  const previewPath = args.preview ? path.resolve(args.preview) : undefined;
  const spec = JSON.parse(await fs.readFile(specPath, "utf8"));
  const theme = spec.theme || {};
  const paper = spec.paper || {};
  const hero = spec.hero || {};
  const sections = list(spec.sections);
  const figures = list(spec.figures);
  const footer = spec.footer || {};
  const missing = list(spec.missing_information);

  const pptx = new PptxGenJS();
  pptx.defineLayout({ name: "SCIPOSTER_WIDE", width: 16, height: 9 });
  pptx.layout = "SCIPOSTER_WIDE";
  pptx.author = "SciPoster";
  pptx.subject = "Editable academic poster";
  pptx.title = paper.title || hero.headline || "Academic Poster";
  pptx.company = paper.affiliation || "";
  pptx.lang = "zh-CN";
  pptx.theme = {
    headFontFace: theme.title_font || "Microsoft YaHei",
    bodyFontFace: theme.body_font || "Microsoft YaHei",
    lang: "zh-CN",
  };

  const slide = pptx.addSlide();
  slide.background = { color: color(theme.background, "F7FAFC") };
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 16, h: 0.65, fill: { color: color(theme.accent_color, "1E5AA8") }, line: { transparency: 100 } });
  slide.addText(paper.title || hero.headline || "Academic Poster", {
    x: 0.58, y: 0.78, w: 10.0, h: 0.78,
    fontFace: theme.title_font || "Microsoft YaHei", fontSize: 26,
    bold: true, color: color(theme.headline_color, "163A63"), margin: 0, fit: "shrink",
  });
  slide.addText(list(paper.authors).join(", ") || "Authors TBD", {
    x: 0.60, y: 1.55, w: 7.8, h: 0.25, fontSize: 13,
    fontFace: theme.body_font || "Microsoft YaHei", color: color(theme.muted_color, "5B6B7F"), margin: 0,
  });
  slide.addText(paper.affiliation || "Affiliation TBD", {
    x: 0.60, y: 1.82, w: 7.8, h: 0.23, fontSize: 11,
    fontFace: theme.body_font || "Microsoft YaHei", color: color(theme.muted_color, "5B6B7F"), margin: 0,
  });
  slide.addShape(pptx.ShapeType.roundRect, {
    x: 0.58, y: 2.20, w: 14.84, h: 0.75,
    fill: { color: color(theme.accent_color, "1E5AA8"), transparency: 91 },
    line: { transparency: 100 },
  });
  slide.addText(hero.subheadline || "Poster summary", {
    x: 0.82, y: 2.38, w: 7.2, h: 0.30, fontSize: 14, bold: true,
    fontFace: theme.body_font || "Microsoft YaHei", color: color(theme.headline_color, "163A63"), margin: 0, fit: "shrink",
  });
  slide.addText(bulletText(list(hero.key_findings).slice(0, 3)), {
    x: 8.35, y: 2.31, w: 6.4, h: 0.48, fontSize: 10,
    fontFace: theme.body_font || "Microsoft YaHei", color: color(theme.headline_color, "163A63"), margin: 0, fit: "shrink",
  });

  addPanel(slide, pptx, theme, 0.58, 3.20, 4.66, 1.42, sections[0]?.title || "Background", sections[0]?.content || []);
  addPanel(slide, pptx, theme, 0.58, 4.80, 4.66, 1.42, sections[1]?.title || "Method", sections[1]?.content || []);
  addPanel(slide, pptx, theme, 5.82, 3.20, 5.84, 1.42, sections[2]?.title || "Results", sections[2]?.content || [], 19, 12);
  addPanel(slide, pptx, theme, 12.08, 3.20, 3.34, 1.84, sections[3]?.title || "Conclusion", sections[3]?.content || []);
  addPanel(slide, pptx, theme, 12.08, 5.28, 3.34, 1.16, "Key Highlights", list(hero.key_findings).slice(0, 3), 15, 10);
  addPanel(slide, pptx, theme, 12.08, 6.65, 3.34, 1.30, "References", list(footer.references).slice(0, 4), 14, 9);

  const frames = [
    { x: 5.82, y: 4.86, w: 2.72, h: 1.72 },
    { x: 8.74, y: 4.86, w: 2.72, h: 1.72 },
    { x: 5.82, y: 6.88, w: 5.64, h: 1.02 },
  ];
  frames.forEach((frame, index) => addFigure(slide, pptx, theme, figures[index], frame, index));

  slide.addText(missing.length ? `Missing: ${missing.join(", ")}` : "Missing: none", {
    x: 12.22, y: 8.08, w: 3.0, h: 0.20, fontSize: 8,
    fontFace: theme.body_font || "Microsoft YaHei", color: color(theme.muted_color, "5B6B7F"), margin: 0, fit: "shrink",
  });
  slide.addShape(pptx.ShapeType.rect, { x: 0.58, y: 8.38, w: 14.84, h: 0.22, fill: { color: color(theme.accent_color, "1E5AA8") }, line: { transparency: 100 } });
  slide.addText("Generated by the portable SciPoster academic-poster skill. Editable in PowerPoint.", {
    x: 0.72, y: 8.41, w: 10.2, h: 0.13, fontSize: 7, color: "FFFFFF", margin: 0,
  });

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await pptx.writeFile({ fileName: outputPath });

  if (previewPath) {
    const svgPath = path.join(path.dirname(outputPath), "academic-poster.svg");
    await sharp(svgPath).png().toFile(previewPath);
  }
  const specMirror = path.join(path.dirname(outputPath), "poster-spec.json");
  await fs.writeFile(specMirror, `${JSON.stringify(spec, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ output: outputPath, preview: previewPath, posterSpec: specMirror }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
