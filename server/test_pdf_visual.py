# -*- coding: utf-8 -*-
"""视觉验证：用真实/占位图生成三种交付 PDF，并渲染回 PNG。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from PIL import Image, ImageDraw

from app.config import settings
from app.services import pdf_service

out_dir = Path(__file__).parent / "pdf_preview"
out_dir.mkdir(exist_ok=True)

# 找已有输出图，找不到就用占位渐变
real = sorted((settings.data_dir / "assets").glob("*/output/*.png"))
real += sorted((settings.data_dir / "assets").glob("*output*.png"))
picks: list[Path] = [p for p in real if p.stat().st_size > 50_000][:4]

if len(picks) < 4:
    for i, hue in enumerate([(30, 60), (80, 120), (200, 160), (150, 90)]):
        im = Image.new("RGB", (1024, 768),
                       (40 + hue[0], 40 + hue[0] // 2, 30 + hue[1] // 2))
        dr = ImageDraw.Draw(im)
        for y in range(0, 768, 8):
            dr.line([(0, y), (1024, y)], fill=(40 + hue[0] + y // 24,
                                               40 + hue[0] // 2,
                                               30 + hue[1] // 2))
        dr.rectangle([120, 120, 900, 640], outline=(200, 180, 140), width=3)
        p = out_dir / f"placeholder_{i}.png"
        im.save(p)
        picks.append(p)

imgs = [str(p) for p in picks[:4]]
print("图片:", [Path(p).name for p in imgs])

# 1) 方案书
p1 = pdf_service.build_proposal(
    "未来森林项目深化方案", "昭通恒业",
    [{"heading": "客厅", "image_paths": imgs[:2]},
     {"heading": "主卧", "image_paths": imgs[2:4]},
     {"heading": "厨房", "image_paths": [imgs[0]]}])
print("proposal:", p1.name)

# 2) 估算表
data = {"items": [
    {"label": "客厅", "width_m": 4.2, "depth_m": 5.8, "area_sqm": 24.4,
     "wall_len_m": 20.0},
    {"label": "主卧", "width_m": 3.6, "depth_m": 4.5, "area_sqm": 16.2,
     "wall_len_m": 16.2},
    {"label": "厨房", "width_m": 2.8, "depth_m": 3.2, "area_sqm": 9.0,
     "wall_len_m": 12.0}],
    "total_area_sqm": 49.6, "mm_per_px": 4.94, "scale_auto": True,
    "note": "基于房间外接框估算，实际工程量以现场复核为准。"}
p2 = pdf_service.build_estimate("工程量估算表", "昭通恒业", data)
print("estimate:", p2.name)

# 3) 改造对比册
p3 = pdf_service.build_compare(
    "老房改造对比", "昭通恒业",
    [{"heading": "客厅", "before_path": imgs[3], "after_path": imgs[0]},
     {"heading": "卧室", "before_path": imgs[1], "after_path": imgs[2]}])
print("compare:", p3.name)

# 渲染回 PNG
import fitz
for tag, pdf in [("prop", p1), ("est", p2), ("cmp", p3)]:
    doc = fitz.open(pdf)
    print(tag, pdf.name, "pages:", len(doc))
    for idx in range(min(len(doc), 8)):
        pg = doc[idx]
        pix = pg.get_pixmap(dpi=96)
        pix.save(str(out_dir / f"{tag}_p{idx + 1}.png"))
    doc.close()
print("渲染完成 →", out_dir)
