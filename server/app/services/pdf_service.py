"""可交付 PDF 生成：方案书 / 工程量估算表 / 改造对比册。

横版 16:9（960x540pt）演示格式，深色轻奢风格（对齐客户样本《昭通恒业·未来森林室内深化方案》）：
封面 → 目录 → 章节分隔页（大号金色衬线数字）→ 效果图页（左上双语标题 + 准满幅图）。
"""

import uuid
from datetime import date
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

from ..config import settings

# ---- 设计系统（取自样本分析） ----
PAGE_W, PAGE_H = 960.0, 540.0          # 16:9 横版
BG = colors.HexColor("#262626")         # 深炭黑
BG_SOFT = colors.HexColor("#303030")    # 表格行底
GOLD = colors.HexColor("#C9A063")       # 香槟金
GOLD_DIM = colors.HexColor("#8C7A55")   # 暗金（描线）
WHITE = colors.HexColor("#F2EDE4")      # 暖白
MUTED = colors.HexColor("#9A948A")      # 灰褐（次级文字）

SERIF = "Times-Roman"                   # 金色英文/数字衬线（内置）

_FONT_READY = False


def _ensure_font():
    global _FONT_READY
    if _FONT_READY:
        return
    try:
        pdfmetrics.registerFont(TTFont("ZH", "C:/Windows/Fonts/simhei.ttf"))
    except Exception:
        try:
            pdfmetrics.registerFont(TTFont("ZH", "C:/Windows/Fonts/msyh.ttc",
                                           subfontIndex=0))
        except Exception:
            pass
    _FONT_READY = True


def _zh() -> str:
    _ensure_font()
    return "ZH" if "ZH" in pdfmetrics.getRegisteredFontNames() else "Helvetica"


_ZONE_EN = [
    ("客厅", "LIVING ROOM"), ("主卧", "MASTER BEDROOM"), ("卧室", "BEDROOM"),
    ("餐厅", "DINING ROOM"), ("厨房", "KITCHEN"), ("卫生间", "BATHROOM"),
    ("浴室", "BATHROOM"), ("玄关", "ENTRANCE HALL"), ("书房", "STUDY"),
    ("阳台", "BALCONY"), ("儿童", "KIDS ROOM"), ("老人", "ELDER ROOM"),
    ("走廊", "CORRIDOR"), ("过道", "CORRIDOR"), ("衣帽", "CLOAKROOM"),
    ("平面", "FLOOR PLAN"), ("售楼", "SALES CENTER"), ("样板", "SHOW FLAT"),
    ("大堂", "LOBBY"), ("接待", "RECEPTION"), ("办公", "OFFICE"),
    ("会议", "MEETING ROOM"), ("餐厨", "KITCHEN & DINING"),
]
_CN_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def _zone_en(name: str) -> str:
    for key, en in _ZONE_EN:
        if key in name:
            return en
    return "RENDERING"


class _Deck:
    """画布封装：统一深色底、页码、金线装饰。"""

    def __init__(self, path: Path, brand: str = ""):
        self.path = path
        self.brand = brand
        self.c = pdfcanvas.Canvas(str(path), pagesize=(PAGE_W, PAGE_H))
        self.page_no = 0

    def _text(self, x, y, text, font, size, color, char_space=0, alpha=1.0):
        c = self.c
        c.saveState()
        c.setFont(font, size)
        c.setFillColor(color)
        if alpha < 1.0:
            try:
                c.setFillAlpha(alpha)
            except Exception:
                pass
        try:
            c.drawString(x, y, text, charSpace=char_space)
        except TypeError:          # 旧版 reportlab 无 charSpace
            c.drawString(x, y, text)
        c.restoreState()

    def text_width(self, text, font, size, char_space=0.0) -> float:
        try:
            return pdfmetrics.stringWidth(text, font, size) + \
                char_space * max(len(text) - 1, 0)
        except Exception:
            return pdfmetrics.stringWidth(text, font, size)

    def new_page(self, page_number: bool = True):
        if self.page_no > 0:
            self.c.showPage()
        self.page_no += 1
        c = self.c
        c.setFillColor(BG)
        c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        if page_number and self.page_no > 1:
            self._text(PAGE_W - 40, 16, f"{self.page_no:02d}", SERIF, 8, MUTED,
                       char_space=1)
            if self.brand:
                self._text(40, 16, self.brand, SERIF, 7, GOLD_DIM, char_space=3)

    def hairline(self, x1, y1, x2, y2, color=GOLD_DIM, width=0.5, alpha=1.0):
        c = self.c
        c.saveState()
        c.setStrokeColor(color)
        c.setLineWidth(width)
        if alpha < 1.0:
            try:
                c.setStrokeAlpha(alpha)
            except Exception:
                pass
        c.line(x1, y1, x2, y2)
        c.restoreState()

    def image_fit(self, path, x, y, w, h):
        """等比放入指定框并居中。"""
        p = Path(path)
        if not p.is_file():
            return
        with PILImage.open(p) as im:
            iw, ih = im.size
        r = min(w / iw, h / ih)
        dw, dh = iw * r, ih * r
        self.c.drawImage(str(p), x + (w - dw) / 2, y + (h - dh) / 2, dw, dh)

    def close(self) -> Path:
        self.c.save()
        return self.path


# ---- 页面模板 ----

def _cover(d: _Deck, title: str, customer: str, en_title: str):
    d.new_page(page_number=False)
    zh = _zh()
    d._text(_center(d, en_title, SERIF, 12, 6), 330, en_title, SERIF, 12,
            GOLD, char_space=6)
    # 主标题
    d._text(_center(d, title, zh, 32), 256, title, zh, 32, WHITE)
    # 金色发光分割线（主线 + 上下羽化线）
    cx, half = PAGE_W / 2, 130
    d.hairline(cx - half, 230, cx + half, 230, GOLD, 1.1)
    d.hairline(cx - half + 18, 234, cx + half - 18, 234, GOLD, 0.4, alpha=0.35)
    d.hairline(cx - half + 18, 226, cx + half - 18, 226, GOLD, 0.4, alpha=0.35)
    # 底部信息
    info = f"客户：{customer or '—'}"
    d._text(_center(d, info, zh, 11), 100, info, zh, 11, MUTED)
    dat = date.today().strftime("%Y.%m.%d")
    d._text(_center(d, dat, SERIF, 10, 3), 76, dat, SERIF, 10, MUTED,
            char_space=3)


def _center(d: _Deck, text, font, size, char_space=0) -> float:
    return (PAGE_W - d.text_width(text, font, size, char_space)) / 2


def _catalog(d: _Deck, entries: list[tuple[str, str]]):
    """目录页：左侧 CATALOGUE 目 录，右侧条目（中文大 + 英文小）。"""
    d.new_page()
    zh = _zh()
    d._text(64, 312, "CATALOGUE", SERIF, 26, GOLD, char_space=8)
    d._text(66, 274, "目  录", zh, 20, WHITE)
    d.hairline(66, 262, 210, 262, GOLD_DIM, 0.5)
    gap = min(64, 360 / max(len(entries) - 1, 1))
    top = 300 + (len(entries) - 1) * gap / 2   # 条目组围绕版心垂直居中
    for i, (cn, en) in enumerate(entries):
        y = top - i * gap
        d._text(400, y, f"{i + 1:02d}", SERIF, 15, GOLD, char_space=1)
        d._text(445, y + 1, cn, zh, 15, WHITE)
        d._text(446, y - 17, en, SERIF, 7.5, MUTED, char_space=2)
        if i < len(entries) - 1:
            d.hairline(400, y - 30, 890, y - 30, GOLD_DIM, 0.3, alpha=0.4)


def _divider(d: _Deck, num: str, cn_title: str, en_title: str):
    """章节分隔页：左侧大号金色衬线数字 + 中英文标题，右侧留白。"""
    d.new_page()
    zh = _zh()
    d._text(150, 218, num, SERIF, 96, GOLD, char_space=2, alpha=0.92)
    d.hairline(158, 196, 300, 196, GOLD_DIM, 0.6)
    d._text(158, 162, cn_title, zh, 22, WHITE)
    d._text(159, 138, en_title, SERIF, 10, GOLD, char_space=4)


def _zone_header(d: _Deck, cn_label: str, en_name: str, sub_cn: str):
    """内容页左上角双语标题：大号金色英文 + 白色中文小字。"""
    d.new_page()
    zh = _zh()
    d._text(24, 508, en_name, SERIF, 24, GOLD, char_space=5)
    w = d.text_width(en_name, SERIF, 24, 5)
    d._text(30 + w, 510, sub_cn, zh, 11, WHITE)
    d._text(30 + w, 510 - 13, cn_label, zh, 9, MUTED)


# ---- 三个交付物 ----

def build_proposal(title: str, customer: str, sections: list[dict]) -> Path:
    """方案书：sections = [{heading, image_paths: [..], note}]"""
    d = _new_deck("proposal")
    _cover(d, title, customer, "INTERIOR DESIGN PROPOSAL")
    _catalog(d, [(s.get("heading", "效果图"), _zone_en(s.get("heading", "")))
                 for s in sections])
    for i, sec in enumerate(sections):
        heading = sec.get("heading", "效果图")
        en = _zone_en(heading)
        _divider(d, f"{i + 1:02d}", heading, en)
        imgs = [p for p in sec.get("image_paths", []) if Path(p).is_file()]
        for j, img in enumerate(imgs):
            sub = f"方案{_CN_NUM[j]} | 效果图" if len(imgs) > 1 else "效果图"
            _zone_header(d, heading, en, sub)
            d.image_fit(img, 20, 24, PAGE_W - 40, 450)
    return d.close()


def build_estimate(title: str, customer: str, data: dict) -> Path:
    """工程量估算表 PDF。data 为 estimate_rooms 输出。"""
    d = _new_deck("estimate")
    _cover(d, title, customer, "QUANTITY ESTIMATION")
    zh = _zh()
    rows = [["房间", "宽 (m)", "进深 (m)", "面积 (㎡)", "墙长估算 (m)"]] + [
        [it["label"], f"{it['width_m']}", f"{it['depth_m']}",
         f"{it['area_sqm']}", f"{it['wall_len_m']}"]
        for it in data["items"]
    ] + [["合计", "", "", f"{data['total_area_sqm']}", ""]]

    _zone_header(d, "工程量估算", "QUANTITY ESTIMATION", "估算表")
    x0, y = 60, 400
    widths = [220, 150, 150, 160, 160]
    rh = 26
    c = d.c
    for r, row in enumerate(rows):
        if y - rh < 90:                      # 分页
            d.new_page()
            _zone_header(d, "工程量估算", "QUANTITY ESTIMATION", "估算表（续）")
            y = 400
        y -= rh
        c.setFillColor(GOLD if r == 0 else (BG_SOFT if r % 2 else colors.HexColor("#2B2B2B")))
        c.rect(x0, y, sum(widths), rh, stroke=0, fill=1)
        cx = x0
        for cell, wd in zip(row, widths):
            font = zh
            if r > 0 and cell and not any("\u4e00" <= ch <= "\u9fff" for ch in cell):
                font = SERIF           # 纯数字/字母用衬线
            color = colors.HexColor("#262626") if r == 0 else WHITE
            d._text(cx + 14, y + 8, str(cell), font, 10, color,
                    char_space=1 if r == 0 else 0)
            cx += wd
        c.setStrokeColor(colors.HexColor("#3D3D3D"))
        c.setLineWidth(0.4)
        c.line(x0, y, x0 + sum(widths), y)
    # 说明区
    y -= 46
    d._text(x0, y, "比例尺标定", zh, 11, GOLD)
    d._text(x0, y - 20, f"{data['mm_per_px']} 毫米/像素"
            f"（{'图纸标注自动标定' if data.get('scale_auto') else '手动标定'}）",
            zh, 9.5, MUTED)
    d._text(x0, y - 44, "说明", zh, 11, GOLD)
    d._text(x0, y - 64, data.get("note", "外接框估算，仅供参考。"), zh, 9.5, MUTED)
    return d.close()


def build_compare(title: str, customer: str, pairs: list[dict]) -> Path:
    """改造对比册：pairs = [{heading, before_path, after_path}]"""
    d = _new_deck("compare")
    _cover(d, title, customer, "RENOVATION COMPARISON")
    zh = _zh()
    for p in pairs:
        heading = p.get("heading", "改造对比")
        _zone_header(d, "老房改造", _zone_en(heading), "改造前 | 改造后")
        half = (PAGE_W - 40 - 16) / 2
        for k, (label, en) in enumerate((("改造前", "BEFORE"),
                                         ("改造后", "AFTER"))):
            x = 20 + k * (half + 16)
            d._text(x + 4, 466, label, zh, 12, WHITE)
            d._text(x + d.text_width(label, zh, 12) + 10, 467, en, SERIF, 8,
                    GOLD, char_space=3)
            path = p.get("before_path" if k == 0 else "after_path", "")
            if path and Path(path).is_file():
                d.image_fit(path, x, 30, half, 424)
        d.hairline(20 + half + 8, 30, 20 + half + 8, 470, GOLD_DIM, 0.6,
                   alpha=0.7)
    return d.close()


def _new_deck(prefix: str) -> _Deck:
    out_dir = settings.data_dir / "pdf"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{prefix}_{date.today().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}.pdf"
    return _Deck(path, brand="DECOR RENDER STUDIO")
