"""可交付 PDF 生成：方案书 / 工程量估算表 / 改造对比册（reportlab + 黑体中文）。"""

import uuid
from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from ..config import settings

_FONT_READY = False


def _ensure_font():
    global _FONT_READY
    if _FONT_READY:
        return
    for name, path, kwargs in [
        ("ZH", "C:/Windows/Fonts/simhei.ttf", {}),
        ("ZH", "C:/Windows/Fonts/msyh.ttc", {"subfontIndex": 0}),
    ]:
        try:
            pdfmetrics.registerFont(TTFont(name, path, **kwargs))
            _FONT_READY = True
            return
        except Exception:
            continue
    _FONT_READY = True  # 找不到就退化为内置字体（中文会乱码，但流程不崩）


def _styles():
    _ensure_font()
    base = "ZH" if "ZH" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
    return base, {
        "title": ParagraphStyle("t", fontName=base, fontSize=26, alignment=1, spaceAfter=6*mm),
        "sub": ParagraphStyle("s", fontName=base, fontSize=13, alignment=1,
                              textColor=colors.HexColor("#666666"), spaceAfter=4*mm),
        "h2": ParagraphStyle("h", fontName=base, fontSize=15, spaceBefore=4*mm, spaceAfter=3*mm),
        "body": ParagraphStyle("b", fontName=base, fontSize=10.5, leading=16),
        "note": ParagraphStyle("n", fontName=base, fontSize=9,
                               textColor=colors.HexColor("#999999")),
    }


def _footer(canvas, doc):
    base = "ZH" if "ZH" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
    canvas.setFont(base, 8)
    canvas.setFillColor(colors.HexColor("#999999"))
    canvas.drawCentredString(A4[0] / 2, 12 * mm, f"— {canvas.getPageNumber()} —")


def _cover(story, base, title: str, customer: str, subtitle: str = ""):
    for _ in range(6):
        story.append(Spacer(1, 14 * mm))
    story.append(Paragraph(title, _styles()[1]["title"]))
    if subtitle:
        story.append(Paragraph(subtitle, _styles()[1]["sub"]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(f"客户：{customer or '—'}", _styles()[1]["sub"]))
    story.append(Paragraph(f"日期：{date.today().strftime('%Y 年 %m 月 %d 日')}",
                           _styles()[1]["sub"]))
    story.append(PageBreak())


def _save(story: list, prefix: str) -> Path:
    out_dir = settings.data_dir / "pdf"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{prefix}_{date.today().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            topMargin=16 * mm, bottomMargin=18 * mm,
                            leftMargin=14 * mm, rightMargin=14 * mm)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return path


def build_proposal(title: str, customer: str,
                   sections: list[dict]) -> Path:
    """方案书：sections = [{heading, image_paths: [..], note}]"""
    base, st = _styles()
    story: list = []
    _cover(story, base, title, customer, "室内设计方案书")
    for sec in sections:
        story.append(Paragraph(sec.get("heading", ""), st["h2"]))
        if sec.get("note"):
            story.append(Paragraph(sec["note"], st["note"]))
            story.append(Spacer(1, 2 * mm))
        for img_path in sec.get("image_paths", []):
            p = Path(img_path)
            if not p.is_file():
                continue
            from PIL import Image as PILImage
            with PILImage.open(p) as im:
                iw, ih = im.size
            max_w, max_h = 175 * mm, 200 * mm
            r = min(max_w / iw, max_h / ih)
            story.append(Image(str(p), width=iw * r, height=ih * r))
            story.append(PageBreak())
        # 去掉最后一页多余的空段落
        while story and isinstance(story[-1], PageBreak):
            story.pop()
        story.append(PageBreak())
    while story and isinstance(story[-1], PageBreak):
        story.pop()
    return _save(story, "proposal")


def build_estimate(title: str, customer: str, data: dict) -> Path:
    """工程量估算表 PDF。data 为 estimate_rooms 输出。"""
    base, st = _styles()
    story: list = []
    _cover(story, base, title, customer, "工程量估算表（辅助报价）")
    story.append(Paragraph("工程量估算", st["h2"]))
    header = ["房间", "宽 (m)", "进深 (m)", "面积 (㎡)", "墙长估算 (m)"]
    rows = [header] + [
        [it["label"], f"{it['width_m']}", f"{it['depth_m']}",
         f"{it['area_sqm']}", f"{it['wall_len_m']}"]
        for it in data["items"]
    ] + [["合计", "", "", f"{data['total_area_sqm']}", ""]]
    table = Table(rows, colWidths=[52 * mm, 30 * mm, 30 * mm, 34 * mm, 34 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), base),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f6e5d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6f5")]),
    ]))
    story.append(table)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"比例尺：{data['mm_per_px']} 毫米/像素"
                           f"（{'图纸标注自动标定' if data.get('scale_auto') else '手动标定'}）",
                           st["body"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("说明：" + data.get("note", ""), st["note"]))
    return _save(story, "estimate")


def build_compare(title: str, customer: str,
                  pairs: list[dict]) -> Path:
    """改造对比册：pairs = [{heading, before_path, after_path}]"""
    base, st = _styles()
    story: list = []
    _cover(story, base, title, customer, "老房改造前后对比")
    from PIL import Image as PILImage
    for p in pairs:
        story.append(Paragraph(p.get("heading", ""), st["h2"]))
        imgs = []
        for key, label in (("before_path", "改造前"), ("after_path", "改造后")):
            path = Path(p[key])
            if not path.is_file():
                continue
            with PILImage.open(path) as im:
                iw, ih = im.size
            r = min(85 * mm / iw, 150 * mm / ih)
            imgs.append((str(path), iw * r, ih * r, label))
        if len(imgs) == 2:
            cells = [[Paragraph(l, st["sub"]) for _, _, _, l in imgs],
                     [Image(ip, width=w, height=h) for ip, w, h, _ in imgs]]
            t = Table(cells, colWidths=[88 * mm, 88 * mm])
            t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
            story.append(t)
        story.append(PageBreak())
    while story and isinstance(story[-1], PageBreak):
        story.pop()
    return _save(story, "compare")
