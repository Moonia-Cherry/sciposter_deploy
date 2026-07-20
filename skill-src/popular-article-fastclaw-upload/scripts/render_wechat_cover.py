#!/usr/bin/env python
import argparse
import json
import os
import textwrap
import zipfile
from pathlib import Path
from typing import Optional, Tuple
from xml.sax.saxutils import escape

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as exc:  # pragma: no cover
    raise RuntimeError("Pillow is required to render the WeChat cover image.") from exc


WIDTH = 900
HEIGHT = 383
LEFT_PANEL = 590


def normalize_text(value: object) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def choose_font(size: int, bold: bool = False):
    override = os.environ.get("SCIPOSTER_FONT_DIR")
    font_root = Path(override) if override else Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates = []
    if bold:
        candidates.extend(
            [
                font_root / "msyhbd.ttc",
                font_root / "simhei.ttf",
                font_root / "SourceHanSansCN-Bold.otf",
            ]
        )
    candidates.extend(
        [
            font_root / "msyh.ttc",
            font_root / "simhei.ttf",
            font_root / "simsun.ttc",
        ]
    )
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except Exception:
                continue
    raise RuntimeError(
        "未找到可用的 Windows 中文字体。请安装 Microsoft YaHei（msyh.ttc/msyhbd.ttc）后重新部署。"
    )


def fit_lines(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> str:
    text = normalize_text(text)
    if not text:
        return "论文解读"

    best = text
    for wrap in range(8, 25):
        lines = textwrap.wrap(text, width=wrap, break_long_words=False, break_on_hyphens=False)
        if not lines:
            continue
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip("，。；;,. ") + "..."
        trial = "\n".join(lines)
        bbox = draw.multiline_textbbox((0, 0), trial, font=font, spacing=6)
        if bbox[2] - bbox[0] <= max_width:
            return trial
        best = trial
    return best


def crop_cover_image(image_path: Path, target_size: Tuple[int, int]) -> Optional[Image.Image]:
    if not image_path.exists():
        return None
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception:
        return None

    target_w, target_h = target_size
    src_w, src_h = image.size
    if not src_w or not src_h:
        return None
    src_ratio = src_w / src_h
    target_ratio = target_w / target_h

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = max((src_w - new_w) // 2, 0)
        image = image.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = max((src_h - new_h) // 2, 0)
        image = image.crop((0, top, src_w, top + new_h))
    return image.resize((target_w, target_h))


def build_cover_image(package: dict, output_dir: Path) -> Path:
    canvas = Image.new("RGB", (WIDTH, HEIGHT), "#F7F1E8")
    draw = ImageDraw.Draw(canvas)

    draw.rectangle((0, 0, LEFT_PANEL, HEIGHT), fill="#FFF9F0")
    draw.rectangle((LEFT_PANEL, 0, WIDTH, HEIGHT), fill="#102D45")
    draw.rectangle((0, 0, WIDTH, 24), fill="#D93D2B")
    draw.rounded_rectangle((28, 56, 192, 92), radius=18, fill="#FFD44D")
    draw.rounded_rectangle((28, 308, 210, 350), radius=18, fill="#112E46")
    draw.rounded_rectangle((232, 308, 450, 350), radius=18, fill="#D93D2B")
    draw.rectangle((LEFT_PANEL - 24, 32, LEFT_PANEL - 8, HEIGHT - 32), fill="#E4A82F")
    draw.ellipse((496, 34, 556, 94), fill="#D93D2B")
    draw.ellipse((528, 98, 566, 136), fill="#FFD44D")
    draw.ellipse((468, 286, 524, 342), fill="#1A6C7A")

    tag_font = choose_font(18, bold=True)
    title_font = choose_font(44, bold=True)
    subtitle_font = choose_font(18)
    badge_font = choose_font(20, bold=True)
    footer_font = choose_font(16, bold=True)

    title = fit_lines(draw, package.get("title", "论文解读"), title_font, 490, 3)
    summary = normalize_text(package.get("summary", ""))
    if len(summary) > 56:
        summary = summary[:56].rstrip() + "..."

    draw.text((44, 60), "SCI POSTER · 公众号头图", fill="#173046", font=tag_font)
    draw.multiline_text((44, 126), title, fill="#17212B", font=title_font, spacing=8)

    if summary:
        draw.rounded_rectangle((44, 258, 520, 298), radius=14, fill="#F1E8D5")
        draw.text((58, 267), summary, fill="#5F4A2D", font=subtitle_font)

    draw.text((48, 319), "论文要点提炼", fill="#FFFFFF", font=badge_font)
    draw.text((250, 319), "可直接用于推送封面", fill="#FFFFFF", font=badge_font)
    draw.text((44, 6), "900 × 383", fill="#FFFFFF", font=footer_font)

    assets_dir = output_dir / "extracted-paper-assets"
    asset_images = package.get("asset_images", []) or []
    hero_image = None
    for image_name in asset_images:
        hero_image = crop_cover_image(assets_dir / image_name, (248, 248))
        if hero_image is not None:
            break

    if hero_image is not None:
        card = Image.new("RGB", (264, 264), "#FFFFFF")
        card.paste(hero_image, (8, 8))
        canvas.paste(card, (622, 58))
    else:
        draw.rounded_rectangle((624, 58, 870, 248), radius=28, fill="#F8C13A")
        draw.rounded_rectangle((650, 84, 844, 222), radius=22, fill="#FFF4D3")
        draw.line((678, 114, 816, 114), fill="#D93D2B", width=8)
        draw.line((678, 148, 792, 148), fill="#1A6C7A", width=8)
        draw.line((678, 182, 828, 182), fill="#173046", width=8)
        draw.ellipse((778, 248, 854, 324), fill="#D93D2B")
        draw.ellipse((722, 266, 774, 318), fill="#FFD44D")

    draw.text((638, 284), "研究问题", fill="#FFFFFF", font=badge_font)
    draw.text((638, 314), "方法亮点", fill="#FFFFFF", font=badge_font)
    draw.text((752, 314), "结果意义", fill="#FFFFFF", font=badge_font)

    output_path = output_dir / "wechat-cover.png"
    canvas.save(output_path)
    return output_path


def build_pptx_from_png(image_path: Path, output_path: Path) -> Path:
    slide_cx = 12192000
    slide_cy = 5181600

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""

    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""

    app_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Office PowerPoint</Application>
  <Slides>1</Slides>
  <Notes>0</Notes>
  <HiddenSlides>0</HiddenSlides>
  <MMClips>0</MMClips>
  <ScaleCrop>false</ScaleCrop>
  <HeadingPairs>
    <vt:vector size="2" baseType="variant">
      <vt:variant><vt:lpstr>Slides</vt:lpstr></vt:variant>
      <vt:variant><vt:i4>1</vt:i4></vt:variant>
    </vt:vector>
  </HeadingPairs>
  <TitlesOfParts>
    <vt:vector size="1" baseType="lpstr">
      <vt:lpstr>WeChat Cover</vt:lpstr>
    </vt:vector>
  </TitlesOfParts>
  <Company>SciPoster</Company>
  <AppVersion>16.0000</AppVersion>
</Properties>
"""

    core_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>WeChat Cover</dc:title>
  <dc:creator>SciPoster</dc:creator>
  <cp:lastModifiedBy>SciPoster</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-07-17T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-07-17T00:00:00Z</dcterms:modified>
</cp:coreProperties>
"""

    presentation_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" saveSubsetFonts="1" autoCompressPictures="0">
  <p:sldMasterIdLst>
    <p:sldMasterId id="2147483648" r:id="rId1"/>
  </p:sldMasterIdLst>
  <p:sldIdLst>
    <p:sldId id="256" r:id="rId2"/>
  </p:sldIdLst>
  <p:sldSz cx="{slide_cx}" cy="{slide_cy}"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>
"""

    presentation_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
</Relationships>
"""

    slide_master_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld name="Office Theme">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst>
</p:sldMaster>
"""

    slide_master_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>
"""

    slide_layout_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" preserve="1" showMasterSp="1" type="blank">
  <p:cSld name="Blank">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>
"""

    slide_layout_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""

    theme_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="SciPoster Theme">
  <a:themeElements>
    <a:clrScheme name="SciPoster">
      <a:dk1><a:srgbClr val="1F2937"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="102D45"/></a:dk2>
      <a:lt2><a:srgbClr val="F6F1E8"/></a:lt2>
      <a:accent1><a:srgbClr val="D93D2B"/></a:accent1>
      <a:accent2><a:srgbClr val="FFD44D"/></a:accent2>
      <a:accent3><a:srgbClr val="1A6C7A"/></a:accent3>
      <a:accent4><a:srgbClr val="173046"/></a:accent4>
      <a:accent5><a:srgbClr val="F1E8D5"/></a:accent5>
      <a:accent6><a:srgbClr val="E4A82F"/></a:accent6>
      <a:hlink><a:srgbClr val="0563C1"/></a:hlink>
      <a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="SciPoster Fonts">
      <a:majorFont><a:latin typeface="Aptos"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Aptos"/></a:majorFont>
      <a:minorFont><a:latin typeface="Aptos"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Aptos"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="SciPoster Formats">
      <a:fillStyleLst><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:fillStyleLst>
      <a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="accent4"/></a:solidFill></a:ln></a:lnStyleLst>
      <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
      <a:bgFillStyleLst><a:solidFill><a:schemeClr val="lt2"/></a:solidFill></a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
  <a:objectDefaults/>
  <a:extraClrSchemeLst/>
</a:theme>
"""

    slide_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      <p:pic>
        <p:nvPicPr><p:cNvPr id="2" name="WeChat Cover"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
        <p:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
        <p:spPr>
          <a:xfrm><a:off x="0" y="0"/><a:ext cx="{slide_cx}" cy="{slide_cy}"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
        </p:spPr>
      </p:pic>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="3" name="Cover Label"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="640080" y="4114800"/><a:ext cx="3657600" cy="472440"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:noFill/>
          <a:ln><a:noFill/></a:ln>
        </p:spPr>
        <p:txBody>
          <a:bodyPr anchor="ctr" rIns="0" lIns="0" tIns="0" bIns="0"/>
          <a:lstStyle/>
          <a:p>
            <a:r>
              <a:rPr lang="zh-CN" sz="1400" b="1">
                <a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>
                <a:latin typeface="Aptos"/>
                <a:ea typeface="Microsoft YaHei"/>
              </a:rPr>
              <a:t>{escape("公众号头图（900x383）")}</a:t>
            </a:r>
            <a:endParaRPr lang="zh-CN" sz="1400"/>
          </a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>
"""

    slide_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/cover.png"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>
"""

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("docProps/app.xml", app_xml)
        archive.writestr("docProps/core.xml", core_xml)
        archive.writestr("ppt/presentation.xml", presentation_xml)
        archive.writestr("ppt/_rels/presentation.xml.rels", presentation_rels)
        archive.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml)
        archive.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels)
        archive.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml)
        archive.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels)
        archive.writestr("ppt/theme/theme1.xml", theme_xml)
        archive.writestr("ppt/slides/slide1.xml", slide_xml)
        archive.writestr("ppt/slides/_rels/slide1.xml.rels", slide_rels)
        archive.write(image_path, "ppt/media/cover.png")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render WeChat cover artifacts.")
    parser.add_argument("--input", required=True, help="Path to popular-article-package.json")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    args = parser.parse_args()

    package = json.loads(Path(args.input).read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    png_path = build_cover_image(package, output_dir)
    pptx_path = build_pptx_from_png(png_path, output_dir / "wechat-cover.pptx")

    print(json.dumps({"png": str(png_path), "pptx": str(pptx_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
