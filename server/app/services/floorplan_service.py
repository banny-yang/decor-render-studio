"""户型图房间识别：OCR 抓房间名标注（有标注的图）+ 解析「X房X厅X卫」摘要（原始平面图）。

识别结果是"建议清单"，最终以设计师在页面上确认/编辑后的清单为准。
"""

import io
import re

from PIL import Image, ImageOps

# 房间类型：匹配词（长的在前，避免"主卧"被"卧"抢先）+ 展示名 + 透视/平面提示词
ROOM_TYPES: dict[str, dict] = {
    "master_bedroom": {
        "label": "主卧", "match": ["主卧室", "主卧"],
        "perspective": "master bedroom interior, king size bed with elegant headboard, "
                       "bedside tables, warm bedding, soft natural light, professional interior photography, photorealistic, 8k",
        "plan": "master bedroom with king bed layout",
    },
    "bedroom": {
        "label": "卧室", "match": ["卧室", "次卧室", "次卧", "客房", "老人房", "儿童房"],
        "perspective": "cozy bedroom interior, comfortable bed, wardrobe, wooden floor, "
                       "soft warm lighting, professional interior photography, photorealistic, 8k",
        "plan": "bedroom with bed and wardrobe layout",
    },
    "living_room": {
        "label": "客厅", "match": ["客厅", "起居室"],
        "perspective": "modern living room interior, comfortable sofa, coffee table, "
                       "floor-to-ceiling window, natural sunlight, professional interior photography, photorealistic, 8k",
        "plan": "living room with sofa and TV wall layout",
    },
    "dining_room": {
        "label": "餐厅", "match": ["餐厅", "餐厨"],
        "perspective": "elegant dining room interior, dining table with chairs, pendant light, "
                       "professional interior photography, photorealistic, 8k",
        "plan": "dining room with dining table layout",
    },
    "kitchen": {
        "label": "厨房", "match": ["厨房", "中西厨"],
        "perspective": "modern kitchen interior, kitchen cabinets, countertop, sink, "
                       "clean bright lighting, professional interior photography, photorealistic, 8k",
        "plan": "kitchen with cabinets and counter layout",
    },
    "bathroom": {
        "label": "卫生间", "match": ["卫生间", "主卫", "次卫", "公卫", "盥洗", "卫浴", "厕所"],
        "perspective": "modern bathroom interior, walk-in shower, vanity with mirror, "
                       "clean tiles, bright lighting, professional interior photography, photorealistic, 8k",
        "plan": "bathroom with shower and toilet layout",
    },
    "balcony": {
        "label": "阳台", "match": ["阳台", "露台"],
        "perspective": "balcony with floor-to-ceiling railing view, leisure chair, plants, "
                       "afternoon sunlight, professional interior photography, photorealistic, 8k",
        "plan": "balcony layout",
    },
    "study": {
        "label": "书房", "match": ["书房"],
        "perspective": "study room interior, bookshelf, desk, comfortable chair, "
                       "warm reading light, professional interior photography, photorealistic, 8k",
        "plan": "study room with desk and bookshelf layout",
    },
    "entryway": {
        "label": "玄关", "match": ["玄关"],
        "perspective": "entryway interior, shoe cabinet, mirror, warm welcome lighting, "
                       "professional interior photography, photorealistic, 8k",
        "plan": "entryway layout",
    },
    "walk_in_closet": {
        "label": "衣帽间", "match": ["衣帽间"],
        "perspective": "walk-in closet interior, organized wardrobes, dressing island, "
                       "soft lighting, professional interior photography, photorealistic, 8k",
        "plan": "walk-in closet layout",
    },
}

_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

_NUM_CLASS = "0-9一两二三四五六七八九十"

# 纯风格片段（不含房间类型词）：避免风格模板自带的 "living room" 等覆盖房间类型
STYLE_FRAGMENTS = {
    "现代简约": "modern minimalist style, clean lines, neutral color palette",
    "奶油风": "cream style, warm beige and off-white tones, soft rounded furniture",
    "新中式": "new Chinese style, dark wood furniture, elegant oriental aesthetic",
    "侘寂风": "wabi-sabi style, rustic minimalism, textured lime plaster",
    "法式轻奢": "french light luxury style, elegant moldings, brass accents",
    "轻奢现代": "modern luxury style, marble, gold accents, sophisticated",
    "日式原木": "japanese zen style, natural wood, minimal decoration",
    "工业风": "industrial style, exposed brick, black metal frame",
}
DEFAULT_STYLE = "modern minimalist style"


def _parse_num(s: str) -> int | None:
    s = s.strip()
    if s.isdigit():
        return int(s)
    return _CN_NUM.get(s)


def _summary_rooms(texts: list[str]) -> list[dict]:
    """从「X房X厅X卫」类摘要推断默认房间清单。"""
    joined = " ".join(texts)
    m = re.search(rf"([{_NUM_CLASS}])\s*房", joined)
    n_bed = _parse_num(m.group(1)) if m else None
    m2 = re.search(rf"([{_NUM_CLASS}])\s*厅", joined)
    n_hall = _parse_num(m2.group(1)) if m2 else None
    m3 = re.search(rf"([{_NUM_CLASS}])\s*卫", joined)
    m_bath = _parse_num(m3.group(1)) if m3 else None
    if n_bed is None and n_hall is None and m_bath is None:
        return []

    rooms = []
    if n_bed:
        rooms.append({"room_type": "master_bedroom", "label": "主卧", "bbox": None, "source": "count"})
        for i in range(2, n_bed + 1):
            rooms.append({"room_type": "bedroom", "label": f"卧室{i - 1}", "bbox": None, "source": "count"})
    if n_hall and n_hall >= 1:
        rooms.append({"room_type": "living_room", "label": "客厅", "bbox": None, "source": "count"})
    if n_hall and n_hall >= 2:
        rooms.append({"room_type": "dining_room", "label": "餐厅", "bbox": None, "source": "count"})
    rooms.append({"room_type": "kitchen", "label": "厨房", "bbox": None, "source": "count"})
    for i in range(1, (m_bath or 1) + 1):
        rooms.append({"room_type": "bathroom",
                      "label": "卫生间" + (str(i) if (m_bath or 1) > 1 else ""),
                      "bbox": None, "source": "count"})
    return rooms


def _labeled_rooms(ocr_items: list[tuple[list, str]], scale: float) -> list[dict]:
    """从 OCR 文字中提取房间名标注（含位置）。"""
    rooms: list[dict] = []
    seen_pos: list[tuple[int, int]] = []
    for box, text in ocr_items:
        t = text.strip()
        if not t or len(t) > 6:  # 段落文字不算标注
            continue
        for rt, cfg in ROOM_TYPES.items():
            if any(w in t for w in cfg["match"]):
                x = int(box[0][0] / scale)
                y = int(box[0][1] / scale)
                # 同一位置的重复标注去重
                if any(abs(x - px) < 40 and abs(y - py) < 40 for px, py in seen_pos):
                    break
                seen_pos.append((x, y))
                w = int((box[1][0] - box[0][0]) / scale)
                h = int((box[3][1] - box[0][1]) / scale)
                rooms.append({"room_type": rt, "label": cfg["label"], "bbox": [x, y, w, h],
                              "source": "label"})
                break
    return rooms


def analyze_floorplan(data: bytes) -> dict:
    """OCR（放大增强）→ 房间清单。返回 {rooms, size, texts}。"""
    from rapidocr_onnxruntime import RapidOCR

    img = Image.open(io.BytesIO(data))
    w, h = img.size
    gray = img.convert("L")
    # 小字放大 2 倍 + 对比度增强
    up = gray.resize((w * 2, h * 2), Image.LANCZOS)
    up = ImageOps.autocontrast(up)
    buf = io.BytesIO()
    up.save(buf, format="PNG")

    ocr = RapidOCR()
    result, _ = ocr(buf.getvalue())
    items = [(it[0], it[1]) for it in (result or [])]

    texts = [t for _, t in items]
    rooms = _labeled_rooms(items, scale=2.0)
    if not rooms:
        rooms = _summary_rooms(texts)
    regions = detect_room_regions(data)
    _assign_regions(rooms, regions)

    return {"rooms": rooms, "size": [w, h], "texts": texts[:40]}


def detect_room_regions(data: bytes) -> list[list]:
    """CV 尽力检测房间封闭区域，返回 [x, y, w, h] 列表（原始坐标）。

    原始平面图（门洞无门扇弧线）检测能力有限，检测不全时由前端手动框选补齐。
    """
    import cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []
    H, W = img.shape
    img_area = W * H

    _, wall = cv2.threshold(img, 180, 255, cv2.THRESH_BINARY_INV)
    wall = cv2.dilate(wall, np.ones((3, 3), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(wall, 8)
    keep = np.zeros_like(wall)
    for i in range(1, n):
        if stats[i][4] > max(img_area // 3000, 60):  # 去家具/文字小暗块
            keep[labels == i] = 255

    k = 31  # 封闭门洞（对常见截图比例的经验值）
    closed = cv2.morphologyEx(keep, cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    mask = np.zeros((H + 2, W + 2), np.uint8)
    ff = closed.copy()
    for seed in [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1),
                 (W // 2, 0), (W // 2, H - 1), (0, H // 2), (W - 1, H // 2)]:
        cv2.floodFill(ff, mask, seed, 200)
    enclosed = ((closed == 0) & (ff != 200)).astype(np.uint8) * 255

    n2, _, stats2, _ = cv2.connectedComponentsWithStats(enclosed, 8)
    regions = []
    for i in range(1, n2):
        x, y, w, h, a = stats2[i]
        if a < img_area * 0.008 or w / max(h, 1) > 7 or h / max(w, 1) > 7:
            continue
        regions.append([int(x), int(y), int(w), int(h), int(a)])
    regions.sort(key=lambda r: -r[4])
    return regions


def _assign_regions(rooms: list[dict], regions: list[list]) -> None:
    """把检测到的区域分配给房间：OCR 标注房间按中心点落区匹配；
    摘要房间按启发式（客厅/主卧/卧室取大区，厨卫取小区）。"""
    if not regions:
        return
    used: set[int] = set()

    def take(big: bool):
        order = range(len(regions)) if big else range(len(regions) - 1, -1, -1)
        for i in order:
            if i not in used:
                used.add(i)
                return regions[i][:4]
        return None

    # 1) OCR 标注房间：中心点落在哪个区域就给哪个
    for room in rooms:
        if room["source"] != "label" or not room.get("bbox"):
            continue
        cx = room["bbox"][0] + room["bbox"][2] / 2
        cy = room["bbox"][1] + room["bbox"][3] / 2
        for i, (x, y, w, h, _a) in enumerate(regions):
            if i in used:
                continue
            if x <= cx <= x + w and y <= cy <= y + h:
                room["bbox"] = [x, y, w, h]
                used.add(i)
                break

    # 2) 摘要房间：按类型启发式分配剩余区域
    for room in rooms:
        if room["bbox"] is not None:
            continue
        room["bbox"] = take(big=room["room_type"] in
                            ("living_room", "master_bedroom", "bedroom", "dining_room"))


def size_by_bbox(bbox: list | None) -> tuple[int, int]:
    """按房间框宽高比选生成尺寸。"""
    """按房间框宽高比选生成尺寸。"""
    if not bbox or not bbox[2] or not bbox[3]:
        return 1024, 768
    ratio = bbox[2] / max(bbox[3], 1)
    if ratio >= 1.2:
        return 1024, 768
    if ratio <= 0.83:
        return 768, 1024
    return 896, 896


def crop_room(data: bytes, bbox: list, margin: float = 0.35) -> bytes:
    """按房间框裁剪（外扩 margin 比例）。

    关键：图生图输出分辨率=输入分辨率，小裁剪必须升采样到长边 >=1024，
    否则产物只有两三百像素，放大后抽象不可辨。
    """
    img = Image.open(io.BytesIO(data))
    w, h = img.size
    x, y, bw, bh = bbox
    dx, dy = int(bw * margin), int(bh * margin)
    box = (max(0, x - dx), max(0, y - dy), min(w, x + bw + dx), min(h, y + bh + dy))
    out = img.crop(box)
    long_side = max(out.size)
    if long_side > 1280:
        r = 1280 / long_side
        out = out.resize((int(out.width * r), int(out.height * r)), Image.LANCZOS)
    elif long_side < 1024:
        r = 1024 / long_side
        out = out.resize((int(out.width * r), int(out.height * r)), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()
