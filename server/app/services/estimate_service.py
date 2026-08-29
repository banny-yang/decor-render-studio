"""工程量估算：基于房间框 + 比例尺的确定性面积/墙长估算。

比例尺标定优先级：用户手填 > OCR 尺寸标注自动推断（取最大跨度标注 ÷ 房间区总宽像素）。
估算基于外接矩形，L 型/异形房间会偏高——输出中明确标注。
"""

import re


def extract_dimensions_mm(texts: list[str]) -> list[float]:
    """从 OCR 文字中提取尺寸标注（mm 或 m），返回 mm 列表（中位数滤波去噪）。"""
    dims: list[float] = []
    for t in texts or []:
        for m in re.finditer(r"(?<![\d.])(\d{4,5})(?!\d)", t):
            v = float(m.group(1))
            if 1000 <= v <= 30000:
                dims.append(v)
        for m in re.finditer(r"(?<![\d.])(\d{1,2}\.\d{1,2})\s*m\b", t, re.IGNORECASE):
            dims.append(float(m.group(1)) * 1000)
    if not dims:
        return []
    # OCR 噪声码（如 TL28280）会产生离群值：保留中位数 0.4~3 倍范围内的值
    dims.sort()
    med = dims[len(dims) // 2]
    return [d for d in dims if 0.4 * med <= d <= 3.0 * med]


def extract_area_sqm(texts: list[str]) -> float | None:
    """提取户型图标题中的建筑面积标注（如「122m」「122m²」）。"""
    for t in texts or []:
        for m in re.finditer(r"(?<![\d.])(\d{2,4})\s*m(?:²|\^2)?(?![\d])", t, re.IGNORECASE):
            v = float(m.group(1))
            if 20 <= v <= 1000:
                return v
    return None


def calibrate_scale(rooms: list[dict], texts: list[str]) -> tuple[float | None, str]:
    """自动标定 mm/px。优先建筑面积标注反推，其次最大跨度标注。返回 (scale, 方法)。"""
    boxes = [r["bbox"] for r in rooms if r.get("bbox")]
    if not boxes:
        return None, ""
    union_w = max(b[0] + b[2] for b in boxes) - min(b[0] for b in boxes)
    if union_w < 50:
        return None, ""

    # 方法1：建筑面积标注 → 面积反推比例尺（总面积 mm² / 房间框总像素面积）
    area = extract_area_sqm(texts)
    if area:
        px_area = sum(b[2] * b[3] for b in boxes)
        scale = (area * 1e6 / px_area) ** 0.5
        if 2.0 <= scale <= 80.0:
            return round(scale, 3), f"按标注建筑面积 {area:.0f}㎡ 反推"

    # 方法2：最大跨度标注 ÷ 房间区总宽
    dims = extract_dimensions_mm(texts)
    if dims:
        scale = max(dims) / union_w
        if 2.0 <= scale <= 80.0:
            return round(scale, 3), f"按最大跨度标注 {max(dims):.0f}mm 反推"
    return None, ""


def estimate_rooms(rooms: list[dict], mm_per_px: float) -> dict:
    items = []
    total = 0.0
    for r in rooms:
        if not r.get("bbox"):
            continue
        x, y, w, h = r["bbox"]
        area = w * h * mm_per_px * mm_per_px / 1e6      # ㎡
        wall = 2 * (w + h) * mm_per_px / 1000            # m
        items.append({
            "label": r.get("label", ""),
            "width_m": round(w * mm_per_px / 1000, 2),
            "depth_m": round(h * mm_per_px / 1000, 2),
            "area_sqm": round(area, 1),
            "wall_len_m": round(wall, 1),
        })
        total += area
    return {
        "mm_per_px": mm_per_px,
        "items": items,
        "total_area_sqm": round(total, 1),
        "note": "基于房间外接矩形估算，L 型/异形房间数值偏高，仅供报价参考，不作为施工依据",
    }
