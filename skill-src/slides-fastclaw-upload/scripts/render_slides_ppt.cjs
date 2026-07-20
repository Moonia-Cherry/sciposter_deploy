#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

function loadPptxGenJS() {
  const root = path.resolve(__dirname, "..", "..", "..", "..");
  const localModule = path.join(root, "backend", "node_modules", "pptxgenjs");
  try {
    return require(localModule);
  } catch (localError) {
    try {
      return require("pptxgenjs");
    } catch (runtimeError) {
      throw new Error(
        "Missing portable Node dependency 'pptxgenjs'. Verify runtime/node/node_modules and rerun deploy.ps1.",
        { cause: runtimeError },
      );
    }
  }
}

function clean(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function addBullets(slide, bullets, options) {
  const runs = [];
  (bullets || []).forEach((bullet) => {
    const text = clean(bullet);
    if (!text) return;
    runs.push({
      text,
      options: { bullet: { indent: 18 } },
    });
  });
  if (!runs.length) {
    runs.push({
      text: "Add the most important takeaway from the paper here.",
      options: { bullet: { indent: 18 } },
    });
  }
  slide.addText(runs, options);
}

function addHeader(slide, title, subtitle, index, total) {
  slide.addShape("rect", { x: 0, y: 0, w: 13.333, h: 0.32, fill: { color: "144B8B" }, line: { color: "144B8B" } });
  slide.addText(clean(title), {
    x: 0.72,
    y: 0.58,
    w: 7.8,
    h: 0.52,
    fontFace: "Microsoft YaHei",
    fontSize: 24,
    bold: true,
    color: "17324D",
    margin: 0,
  });
  if (clean(subtitle)) {
    slide.addText(clean(subtitle), {
      x: 0.74,
      y: 1.08,
      w: 7.4,
      h: 0.3,
      fontFace: "Microsoft YaHei",
      fontSize: 11,
      color: "66778C",
      margin: 0,
    });
  }
  slide.addText(`${index}/${total}`, {
    x: 11.74,
    y: 0.58,
    w: 0.8,
    h: 0.28,
    align: "right",
    fontFace: "Microsoft YaHei",
    fontSize: 10,
    bold: true,
    color: "144B8B",
    margin: 0,
  });
}

function renderTitleSlide(pptx, slideInfo, index, total) {
  const slide = pptx.addSlide();
  slide.background = { color: "EEF3F8" };
  slide.addShape("roundRect", { x: 0.54, y: 0.45, w: 12.2, h: 6.45, rectRadius: 0.14, fill: { color: "FFFFFF" }, line: { color: "D6E1EE", pt: 1.2 } });
  slide.addShape("rect", { x: 0.54, y: 0.45, w: 12.2, h: 0.34, fill: { color: "144B8B" }, line: { color: "144B8B" } });
  slide.addText(clean(slideInfo.title), {
    x: 0.94,
    y: 1.28,
    w: 7.3,
    h: 1.1,
    fontFace: "Microsoft YaHei",
    fontSize: 26,
    bold: true,
    color: "17324D",
    valign: "mid",
    margin: 0,
  });
  slide.addText(clean(slideInfo.subtitle), {
    x: 0.98,
    y: 2.12,
    w: 5.4,
    h: 0.36,
    fontFace: "Microsoft YaHei",
    fontSize: 14,
    color: "144B8B",
    margin: 0,
  });
  addBullets(slide, slideInfo.bullets, {
    x: 1.0,
    y: 2.8,
    w: 5.9,
    h: 2.3,
    fontFace: "Microsoft YaHei",
    fontSize: 18,
    color: "17324D",
    breakLine: true,
    paraSpaceAfterPt: 10,
    margin: 0.02,
  });
  slide.addShape("roundRect", { x: 8.1, y: 2.0, w: 3.7, h: 3.25, rectRadius: 0.12, fill: { color: "E8F0FA" }, line: { color: "D7E4F4", pt: 1 } });
  slide.addText("Key Figure Area", {
    x: 8.5,
    y: 2.48,
    w: 2.5,
    h: 0.34,
    fontFace: "Microsoft YaHei",
    fontSize: 16,
    bold: true,
    color: "144B8B",
    margin: 0,
  });
  slide.addText(clean(slideInfo.figure_hint), {
    x: 8.5,
    y: 3.1,
    w: 2.6,
    h: 1.2,
    fontFace: "Microsoft YaHei",
    fontSize: 12,
    color: "66778C",
    breakLine: true,
    margin: 0,
  });
  slide.addText("SciPoster group-meeting deck", {
    x: 0.92,
    y: 6.3,
    w: 2.3,
    h: 0.22,
    fontFace: "Microsoft YaHei",
    fontSize: 9,
    color: "66778C",
    margin: 0,
  });
  slide.addText(`${index}/${total}`, {
    x: 11.6,
    y: 6.3,
    w: 0.8,
    h: 0.22,
    fontFace: "Microsoft YaHei",
    fontSize: 9,
    bold: true,
    color: "144B8B",
    align: "right",
    margin: 0,
  });
}

function renderAgendaSlide(pptx, slideInfo, index, total) {
  const slide = pptx.addSlide();
  slide.background = { color: "EEF3F8" };
  slide.addShape("roundRect", { x: 0.54, y: 0.45, w: 12.2, h: 6.45, rectRadius: 0.14, fill: { color: "FFFFFF" }, line: { color: "D6E1EE", pt: 1.2 } });
  addHeader(slide, slideInfo.title, slideInfo.subtitle, index, total);
  const bullets = slideInfo.bullets || [];
  bullets.slice(0, 3).forEach((bullet, i) => {
    const x = 0.96 + i * 3.95;
    slide.addShape("roundRect", { x, y: 2.4, w: 3.35, h: 2.0, rectRadius: 0.12, fill: { color: "E8F0FA" }, line: { color: "D7E4F4", pt: 1 } });
    slide.addShape("roundRect", { x: x + 0.22, y: 2.64, w: 0.6, h: 0.42, rectRadius: 0.08, fill: { color: "144B8B" }, line: { color: "144B8B" } });
    slide.addText(String(i + 1), {
      x: x + 0.42,
      y: 2.74,
      w: 0.18,
      h: 0.12,
      fontFace: "Microsoft YaHei",
      fontSize: 11,
      bold: true,
      color: "FFFFFF",
      align: "center",
      margin: 0,
    });
    slide.addText(clean(bullet), {
      x: x + 0.22,
      y: 3.28,
      w: 2.85,
      h: 0.86,
      fontFace: "Microsoft YaHei",
      fontSize: 16,
      color: "17324D",
      breakLine: true,
      margin: 0,
      valign: "mid",
    });
  });
}

function renderContentSlide(pptx, slideInfo, index, total) {
  const slide = pptx.addSlide();
  slide.background = { color: "EEF3F8" };
  slide.addShape("roundRect", { x: 0.54, y: 0.45, w: 12.2, h: 6.45, rectRadius: 0.14, fill: { color: "FFFFFF" }, line: { color: "D6E1EE", pt: 1.2 } });
  addHeader(slide, slideInfo.title, slideInfo.subtitle, index, total);
  slide.addShape("roundRect", { x: 0.82, y: 2.02, w: 6.55, h: 4.35, rectRadius: 0.12, fill: { color: "F9FBFE" }, line: { color: "D6E1EE", pt: 1 } });
  slide.addText("Key Points", {
    x: 1.05,
    y: 2.25,
    w: 1.8,
    h: 0.26,
    fontFace: "Microsoft YaHei",
    fontSize: 15,
    bold: true,
    color: "144B8B",
    margin: 0,
  });
  addBullets(slide, slideInfo.bullets, {
    x: 1.05,
    y: 2.72,
    w: 5.8,
    h: 3.2,
    fontFace: "Microsoft YaHei",
    fontSize: 18,
    color: "17324D",
    breakLine: true,
    paraSpaceAfterPt: 10,
    margin: 0.02,
  });

  slide.addShape("roundRect", { x: 7.72, y: 2.02, w: 4.02, h: 4.35, rectRadius: 0.12, fill: { color: "E8F0FA" }, line: { color: "D7E4F4", pt: 1 } });
  slide.addText("Suggested Figure", {
    x: 7.98,
    y: 2.25,
    w: 2.2,
    h: 0.26,
    fontFace: "Microsoft YaHei",
    fontSize: 15,
    bold: true,
    color: "144B8B",
    margin: 0,
  });
  slide.addText(clean(slideInfo.figure_hint), {
    x: 7.98,
    y: 2.8,
    w: 3.15,
    h: 1.1,
    fontFace: "Microsoft YaHei",
    fontSize: 13,
    color: "66778C",
    breakLine: true,
    margin: 0,
  });
  slide.addShape("roundRect", { x: 8.0, y: 4.35, w: 3.2, h: 1.45, rectRadius: 0.08, fill: { color: "FFFFFF" }, line: { color: "CAD8EA", pt: 1 } });
  slide.addText("Replace with paper figure,\nworkflow, chart, or table.", {
    x: 8.28,
    y: 4.76,
    w: 2.55,
    h: 0.6,
    fontFace: "Microsoft YaHei",
    fontSize: 11,
    color: "17324D",
    breakLine: true,
    margin: 0,
    align: "center",
  });
  slide.addText("Editable PPTX export included", {
    x: 0.96,
    y: 6.3,
    w: 2.3,
    h: 0.22,
    fontFace: "Microsoft YaHei",
    fontSize: 9,
    color: "66778C",
    margin: 0,
  });
}

function renderQASlide(pptx, slideInfo, index, total) {
  const slide = pptx.addSlide();
  slide.background = { color: "EEF3F8" };
  slide.addShape("roundRect", { x: 0.54, y: 0.45, w: 12.2, h: 6.45, rectRadius: 0.14, fill: { color: "FFFFFF" }, line: { color: "D6E1EE", pt: 1.2 } });
  addHeader(slide, slideInfo.title, slideInfo.subtitle, index, total);
  (slideInfo.bullets || []).slice(0, 3).forEach((bullet, i) => {
    const y = 2.15 + i * 1.35;
    slide.addShape("roundRect", { x: 1.02, y, w: 11.0, h: 0.98, rectRadius: 0.12, fill: { color: "E8F0FA" }, line: { color: "D7E4F4", pt: 1 } });
    slide.addText(clean(bullet), {
      x: 1.28,
      y: y + 0.28,
      w: 10.3,
      h: 0.34,
      fontFace: "Microsoft YaHei",
      fontSize: 18,
      color: "17324D",
      margin: 0,
      valign: "mid",
    });
  });
}

function main() {
  const args = process.argv.slice(2);
  const packageIndex = args.indexOf("--input");
  const outputIndex = args.indexOf("--output");
  if (packageIndex === -1 || outputIndex === -1 || !args[packageIndex + 1] || !args[outputIndex + 1]) {
    console.error("Usage: node render_slides_ppt.cjs --input <slides-package.json> --output <slides.pptx>");
    process.exit(1);
  }

  const packagePath = path.resolve(args[packageIndex + 1]);
  const outputPath = path.resolve(args[outputIndex + 1]);
  const PptxGenJS = loadPptxGenJS();
  const packageData = JSON.parse(fs.readFileSync(packagePath, "utf8"));
  const pptx = new PptxGenJS();
  const slides = packageData.slides || [];

  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "SciPoster";
  pptx.company = "SciPoster";
  pptx.subject = clean(packageData.title);
  pptx.title = clean(packageData.title);
  pptx.lang = packageData.language === "zh-CN" ? "zh-CN" : "en-US";
  pptx.theme = {
    headFontFace: "Microsoft YaHei",
    bodyFontFace: "Microsoft YaHei",
    lang: pptx.lang,
  };

  slides.forEach((slideInfo, index) => {
    const position = index + 1;
    if (slideInfo.layout === "title") {
      renderTitleSlide(pptx, slideInfo, position, slides.length);
    } else if (slideInfo.layout === "agenda") {
      renderAgendaSlide(pptx, slideInfo, position, slides.length);
    } else if (slideInfo.layout === "qa") {
      renderQASlide(pptx, slideInfo, position, slides.length);
    } else {
      renderContentSlide(pptx, slideInfo, position, slides.length);
    }
  });

  pptx.writeFile({ fileName: outputPath }).then(() => {
    console.log(outputPath);
  }).catch((error) => {
    console.error(error && error.stack ? error.stack : String(error));
    process.exit(1);
  });
}

main();
