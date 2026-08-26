"""DXF 施工图转换：图层规范化 + 黑白工程出图（PDF/PNG）。

确定性管线（非 AI 生成）：墙体粗实线、门窗中线、家具细线、标注/轴网辅助线，
加图框与标题栏。所有几何与尺寸数据均来自原 DXF 文件。
"""

from datetime import date
from pathlib import Path

import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

from ..config import settings

# 图层名模糊归类 -> 标准类别
LAYER_RULES = [
    ("wall", ["墙", "wall", "wq"]),
    ("door", ["门", "door"]),
    ("window", ["窗", "window"]),
    ("furniture", ["家具", "洁具", "软装", "furn", "sanitary"]),
    ("dimension", ["标注", "尺寸", "dim"]),
    ("axis", ["轴", "axis"]),
    ("text", ["文字", "说明", "text"]),
]

# 类别 -> DXF lineweight（单位 0.01mm）
CATEGORY_LW = {"wall": 70, "door": 35, "window": 35, "furniture": 18,
               "dimension": 13, "axis": 9, "text": 13, "default": 25}

SHEETS = {"A3": (420, 297), "A4": (297, 210)}


def classify_layer(name: str) -> str:
    low = (name or "").lower()
    for cat, keys in LAYER_RULES:
        if any(k in low for k in keys):
            return cat
    return "default"


def _extents(msp):
    """模型空间包围盒 (min_x, min_y, max_x, max_y)；空图返回 None。"""
    xs, ys = [], []
    for e in msp:
        try:
            t = e.dxftype()
            if t == "LINE":
                for p in (e.dxf.start, e.dxf.end):
                    xs.append(p[0]); ys.append(p[1])
            elif t == "LWPOLYLINE":
                for x, y in e.get_points("xy"):
                    xs.append(x); ys.append(y)
            elif t == "POLYLINE":
                for v in e.vertices:
                    xs.append(v.dxf.location.x); ys.append(v.dxf.location.y)
            elif t in ("CIRCLE", "ARC"):
                c, r = e.dxf.center, e.dxf.radius
                xs += [c.x - r, c.x + r]; ys += [c.y - r, c.y + r]
            elif t in ("TEXT", "MTEXT", "INSERT"):
                p = e.dxf.insert
                xs.append(p[0]); ys.append(p[1])
        except Exception:
            continue
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def convert_dxf(data: bytes, project: str, title: str, scale: str,
                sheet: str = "A3") -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        f.write(data)
        dxf_path = Path(f.name)
    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as e:
        raise ValueError(f"DXF 文件解析失败：{e}") from e
    finally:
        dxf_path.unlink(missing_ok=True)

    msp = doc.modelspace()
    extents = _extents(msp)
    if extents is None:
        raise ValueError("DXF 模型空间没有可渲染的实体")

    # 1) 图层规范化：全黑白 + 按类别线宽（必须在渲染前设置）
    layer_stats: dict[str, int] = {}
    for layer in doc.layers:
        cat = classify_layer(layer.dxf.name)
        layer_stats[cat] = layer_stats.get(cat, 0) + 1
        layer.color = 7
        layer.dxf.lineweight = CATEGORY_LW[cat]

    # 2) 渲染 DXF 内容
    sheet_w, sheet_h = SHEETS.get(sheet.upper(), SHEETS["A3"])
    fig = plt.figure(figsize=(sheet_w / 25.4, sheet_h / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("white")
    ax.axis("off")
    ctx = RenderContext(doc)
    ctx.set_current_layout(msp)
    Frontend(ctx, MatplotlibBackend(ax)).draw_layout(msp, finalize=True)

    # 内容缩放到图框内区域（左边距15，右侧留70给标题栏）
    inner_x0, inner_y0 = 15, 15
    inner_w, inner_h = sheet_w - 15 - 70, sheet_h - 30
    ax.set_position([inner_x0 / sheet_w, inner_y0 / sheet_h,
                     inner_w / sheet_w, inner_h / sheet_h])
    ax.set_aspect("equal")
    pad_x = (extents[2] - extents[0]) * 0.02 + 1
    pad_y = (extents[3] - extents[1]) * 0.02 + 1
    ax.set_xlim(extents[0] - pad_x, extents[2] + pad_x)
    ax.set_ylim(extents[1] - pad_y, extents[3] + pad_y)

    # 3) 图框 + 标题栏
    ax2 = fig.add_axes([0, 0, 1, 1])
    ax2.set_xlim(0, sheet_w)
    ax2.set_ylim(0, sheet_h)
    ax2.set_aspect("equal")
    ax2.axis("off")
    ax2.add_patch(mpatches.Rectangle((10, 10), sheet_w - 20, sheet_h - 20,
                                     linewidth=1.2, edgecolor="black", facecolor="none"))
    tb_x = sheet_w - 10 - 60
    ax2.add_patch(mpatches.Rectangle((tb_x, 10), 60, sheet_h - 20,
                                     linewidth=0.8, edgecolor="black", facecolor="none"))
    rows = [
        ("工程名称", project or "—"),
        ("图纸名称", title or "平面施工图"),
        ("比例", scale or "1:100"),
        ("日期", date.today().strftime("%Y-%m-%d")),
        ("图纸编号", "SD-01"),
    ]
    row_h = (sheet_h - 24) / len(rows)
    y = sheet_h - 12 - row_h
    for label, value in rows:
        ax2.plot([tb_x, tb_x + 60], [y, y], color="black", linewidth=0.5)
        ax2.text(tb_x + 4, y + row_h * 0.32, label, fontsize=7, color="black", va="center")
        ax2.text(tb_x + 56, y + row_h * 0.32, value, fontsize=7.5, color="black",
                 ha="right", va="center", clip_on=True)
        y -= row_h

    # 4) 输出 PDF + PNG
    out_dir = settings.data_dir / "cad"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"cad_{date.today().strftime('%Y%m%d')}_{len(data) % 100000}"
    pdf_path = out_dir / f"{stem}.pdf"
    png_path = out_dir / f"{stem}.png"
    fig.savefig(str(pdf_path), format="pdf")
    fig.savefig(str(png_path), format="png", dpi=150)
    plt.close(fig)

    return {
        "pdf": {"path": str(pdf_path.relative_to(settings.data_dir)), "filename": pdf_path.name},
        "png": {"path": str(png_path.relative_to(settings.data_dir)), "filename": png_path.name},
        "layers": layer_stats,
        "entities": len(msp),
    }
