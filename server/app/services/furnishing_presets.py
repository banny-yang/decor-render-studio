"""软装快速替换预设库：类别 -> 预设（中文名 + 英文提示词）。

mask_hint 字段为后续接入 SAM 自动分割预留（如 "sofa"），当前不参与逻辑。
公司可按需扩充本列表。
"""

PRESETS: list[dict] = [
    {"category": "沙发", "name": "奶油风布艺沙发", "prompt_en": "cream boucle fabric sofa, soft rounded silhouette, cozy",
     "mask_hint": "sofa"},
    {"category": "沙发", "name": "米色亚麻沙发", "prompt_en": "beige linen sofa, natural texture, minimalist",
     "mask_hint": "sofa"},
    {"category": "沙发", "name": "深绿丝绒沙发", "prompt_en": "dark green velvet sofa, elegant, light luxury style",
     "mask_hint": "sofa"},
    {"category": "沙发", "name": "焦糖色真皮沙发", "prompt_en": "caramel leather sofa, vintage, premium texture",
     "mask_hint": "sofa"},
    {"category": "沙发", "name": "灰色模块沙发", "prompt_en": "gray modular sectional sofa, modern minimalist",
     "mask_hint": "sofa"},
    {"category": "单人椅", "name": "休闲扶手椅", "prompt_en": "lounge armchair with wooden frame, fabric cushion",
     "mask_hint": "armchair"},
    {"category": "单人椅", "name": "藤编椅", "prompt_en": "rattan armchair, natural boho style",
     "mask_hint": "armchair"},
    {"category": "床品", "name": "白色酒店风床品", "prompt_en": "crisp white hotel bedding, neat pillows, elegant",
     "mask_hint": "bed"},
    {"category": "床品", "name": "亚麻色床品", "prompt_en": "natural linen bedding in oatmeal tones, relaxed",
     "mask_hint": "bed"},
    {"category": "窗帘", "name": "白纱窗帘", "prompt_en": "white sheer curtains, light and airy",
     "mask_hint": "curtain"},
    {"category": "窗帘", "name": "奶油遮光帘", "prompt_en": "cream blackout curtains, soft folds, warm",
     "mask_hint": "curtain"},
    {"category": "窗帘", "name": "亚麻窗帘", "prompt_en": "natural linen curtains, textured weave",
     "mask_hint": "curtain"},
    {"category": "地毯", "name": "米色长绒地毯", "prompt_en": "beige plush high-pile rug, soft texture",
     "mask_hint": "rug"},
    {"category": "地毯", "name": "几何编织地毯", "prompt_en": "geometric woven rug, modern pattern",
     "mask_hint": "rug"},
    {"category": "地毯", "name": "圆形地毯", "prompt_en": "round rug, neutral tones, layered under furniture",
     "mask_hint": "rug"},
    {"category": "灯具", "name": "落地灯", "prompt_en": "modern floor lamp with warm light, black metal stand",
     "mask_hint": "lamp"},
    {"category": "灯具", "name": "水晶吊灯", "prompt_en": "crystal chandelier, luxurious, sparkling light",
     "mask_hint": "chandelier"},
    {"category": "灯具", "name": "纸艺吊灯", "prompt_en": "japanese paper pendant lamp, soft warm glow",
     "mask_hint": "pendant light"},
    {"category": "装饰画", "name": "抽象挂画", "prompt_en": "abstract art painting in frame on wall, modern gallery style",
     "mask_hint": "painting"},
    {"category": "装饰画", "name": "山水挂画", "prompt_en": "chinese ink landscape painting in wooden frame, elegant",
     "mask_hint": "painting"},
    {"category": "绿植", "name": "大型绿植", "prompt_en": "large potted green plant, fiddle leaf fig, fresh",
     "mask_hint": "plant"},
    {"category": "绿植", "name": "干枝瓶插", "prompt_en": "dried branches in ceramic vase, wabi-sabi style",
     "mask_hint": "vase"},
    {"category": "墙面", "name": "微水泥墙面", "prompt_en": "microcement wall finish, subtle texture, warm gray",
     "mask_hint": "wall"},
    {"category": "墙面", "name": "乳胶漆·燕麦色", "prompt_en": "oatmeal color painted wall, matte finish",
     "mask_hint": "wall"},
    {"category": "墙面", "name": "护墙板", "prompt_en": "wall paneling with crown molding, classic elegant",
     "mask_hint": "wall"},
    {"category": "地板", "name": "橡木地板", "prompt_en": "oak wooden floor, natural grain, warm tone",
     "mask_hint": "floor"},
    {"category": "地板", "name": "灰色瓷砖", "prompt_en": "large gray ceramic floor tiles, matte, modern",
     "mask_hint": "floor"},
    {"category": "地板", "name": "鱼骨拼地板", "prompt_en": "herringbone parquet wood floor, premium",
     "mask_hint": "floor"},
]


def grouped_presets() -> list[dict]:
    """按类别分组返回。"""
    out: dict[str, list] = {}
    for p in PRESETS:
        out.setdefault(p["category"], []).append(
            {"name": p["name"], "prompt_en": p["prompt_en"], "mask_hint": p["mask_hint"]})
    return [{"category": c, "items": items} for c, items in out.items()]
