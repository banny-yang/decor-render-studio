"""提示词服务：中文→英文翻译（在线 + 领域词典兜底）、领域限定检查。

系统仅用于建筑/装修设计图生成，检查提示词中是否包含其他领域内容（人物、
动物、车辆、食物等），命中即拒绝生成。
"""

import re

import httpx

# ---------------- 离线装修领域词典（最长匹配分词） ----------------
DICT: dict[str, str] = {
    # 空间
    "客厅": "living room", "卧室": "bedroom", "主卧": "master bedroom", "次卧": "secondary bedroom",
    "儿童房": "kids room", "厨房": "kitchen", "餐厅": "dining room", "卫生间": "bathroom",
    "浴室": "bathroom", "玄关": "entryway", "走廊": "hallway", "过道": "hallway", "阳台": "balcony",
    "书房": "study room", "办公室": "office", "办公空间": "office space", "会议室": "meeting room",
    "大堂": "lobby", "门店": "storefront", "展厅": "showroom", "酒店": "hotel", "客房": "guest room",
    "民宿": "homestay", "别墅": "villa", "复式": "duplex apartment", "公寓": "apartment",
    "建筑": "building", "建筑外观": "building facade", "户型": "floor plan", "楼梯": "staircase",
    "阁楼": "attic", "地下室": "basement", "车库": "garage", "庭院": "courtyard",
    "屋顶花园": "rooftop garden", "花园": "garden", "游泳池": "swimming pool", "水景": "water feature",
    "室内": "interior", "室外": "outdoor", "空间": "space", "房间": "room",
    # 风格
    "现代简约": "modern minimalist", "现代风格": "modern style", "极简": "minimalist",
    "北欧": "Scandinavian", "奶油风": "cream style", "新中式": "new Chinese style",
    "中式": "Chinese style", "侘寂": "wabi-sabi", "日式": "Japanese style", "原木": "natural wood",
    "法式": "French style", "轻奢": "light luxury", "美式": "American style",
    "欧式": "European style", "工业风": "industrial style", "复古": "vintage",
    "中古": "mid-century", "地中海": "Mediterranean", "波西米亚": "bohemian",
    "艺术装饰": "art deco", "混搭": "eclectic", "极简主义": "minimalism",
    # 家具/软装
    "沙发": "sofa", "布艺沙发": "fabric sofa", "真皮沙发": "leather sofa", "单人沙发": "armchair",
    "茶几": "coffee table", "边几": "side table", "电视柜": "TV cabinet", "电视": "television",
    "柜子": "cabinet", "书柜": "bookshelf", "衣柜": "wardrobe", "床": "bed",
    "双人床": "double bed", "床头柜": "nightstand", "餐桌": "dining table", "餐椅": "dining chair",
    "吧台": "bar counter", "吧椅": "bar stool", "橱柜": "kitchen cabinet", "岛台": "kitchen island",
    "水槽": "sink", "灶台": "stove", "抽油烟机": "range hood", "冰箱": "refrigerator",
    "洗衣机": "washing machine", "马桶": "toilet", "淋浴房": "shower room", "浴缸": "bathtub",
    "浴室柜": "bathroom vanity", "镜子": "mirror", "梳妆台": "dressing table", "书桌": "desk",
    "办公桌": "office desk", "椅子": "chair", "凳子": "stool", "搁板": "shelf",
    "屏风": "folding screen", "地毯": "rug", "窗帘": "curtains", "纱帘": "sheer curtains",
    "抱枕": "throw pillow", "装饰画": "decorative painting", "挂画": "wall art",
    "挂钟": "wall clock", "花瓶": "vase", "绿植": "potted green plant", "盆栽": "potted plant",
    "干枝": "dried branches", "摆件": "ornament", "蜡烛": "candle", "家具": "furniture",
    "软装": "soft furnishing",
    # 材质/硬装
    "木地板": "wooden floor", "地板": "floor", "瓷砖": "ceramic tile", "大理石": "marble",
    "岩板": "sintered stone", "微水泥": "microcement", "水泥": "concrete", "墙面": "wall",
    "白墙": "white wall", "背景墙": "feature wall", "电视背景墙": "TV feature wall",
    "护墙板": "wall panel", "石膏线": "crown molding", "吊顶": "ceiling", "灯带": "light strip",
    "筒灯": "downlight", "射灯": "spotlight", "吊灯": "pendant light", "落地灯": "floor lamp",
    "台灯": "table lamp", "壁灯": "wall lamp", "吸顶灯": "ceiling lamp", "水晶灯": "crystal chandelier",
    "无主灯": "no-main-light lighting", "金属": "metal", "黄铜": "brass", "不锈钢": "stainless steel",
    "玻璃": "glass", "长虹玻璃": "fluted glass", "藤编": "rattan", "皮革": "leather",
    "亚麻": "linen", "丝绒": "velvet", "布艺": "fabric", "木质": "wooden", "胡桃木": "walnut",
    "橡木": "oak", "门": "door", "窗户": "window", "落地窗": "floor-to-ceiling window",
    "飘窗": "bay window", "门框": "door frame", "窗框": "window frame",
    # 颜色
    "白色": "white", "黑色": "black", "灰色": "gray", "米色": "beige", "燕麦色": "oatmeal",
    "焦糖色": "caramel", "墨绿色": "dark green", "绿色": "green", "蓝色": "blue",
    "奶咖色": "milk coffee color", "粉色": "pink", "金色": "gold", "银色": "silver",
    "木色": "wood tone", "暖色": "warm tones", "冷色": "cool tones", "莫兰迪色": "morandi palette",
    "奶油色": "cream color",
    # 描述词
    "效果图": "rendering", "照片级": "photorealistic", "写实": "photorealistic",
    "阳光充足": "abundant sunlight", "自然光": "natural light", "日落": "sunset",
    "阳光": "sunlight", "明亮": "bright", "温馨": "cozy", "高级感": "sophisticated",
    "豪华": "luxurious", "简洁": "clean", "宽敞": "spacious", "通透": "airy",
    "全景": "panorama", "细节": "details", "高清": "high definition", "线稿": "line art sketch",
    "平面图": "floor plan", "下午的阳光": "afternoon sunlight", "落地": "floor-to-ceiling",
    "大": "large", "小": "small", "新": "new", "旧": "old",
}

# ---------------- 领域限定：违禁关键词 ----------------
CN_BLOCKED = [
    "人像", "人物", "肖像", "美女", "帅哥", "男人", "女人", "男孩", "女孩", "宝宝", "老人",
    "模特", "明星", "动物", "猫", "狗", "宠物", "老虎", "狮子", "鸟", "鱼", "马",
    "汽车", "轿车", "跑车", "摩托车", "自行车", "飞机", "火车", "坦克", "机器人",
    "美食", "食物", "蛋糕", "水果", "奖牌", "奖杯", "冠军",
    "武器", "刀", "枪", "血", "裸", "内衣", "泳装",
    "二次元", "动漫", "卡通", "漫画", "游戏",
]

EN_BLOCKED = re.compile(
    r"\b(person|people|man|woman|men|women|boy|girl|child|children|baby|portrait|face|model|"
    r"animal|cat|dog|pet|tiger|lion|bird|fish|horse|"
    r"car|vehicle|motorcycle|bicycle|airplane|train|tank|robot|"
    r"food|dish|cake|fruit|medal|trophy|champion|"
    r"weapon|gun|knife|sword|blood|nude|naked|nsfw|underwear|bikini|"
    r"anime|cartoon|manga)\b",
    re.IGNORECASE,
)

CJK = re.compile(r"[\u4e00-\u9fff]")


def dict_translate(text: str) -> tuple[str, list[str]]:
    """离线词典最长匹配翻译，返回 (英文, 未识别中文片段列表)。"""
    keys = sorted(DICT, key=len, reverse=True)
    out: list[str] = []
    unknown: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if not CJK.match(ch):
            if ch.strip():
                out.append(ch)
            i += 1
            continue
        for k in keys:
            if text.startswith(k, i):
                out.append(DICT[k])
                i += len(k)
                break
        else:
            j = i
            while j < len(text) and CJK.match(text[j]):
                j += 1
            unknown.append(text[i:j])
            i = j
    english = re.sub(r"\s+", " ", "".join(out)).replace(" ,", ",").strip()
    return english, unknown


async def online_translate(text: str) -> str | None:
    """MyMemory 免费接口；失败返回 None。"""
    try:
        async with httpx.AsyncClient(timeout=8) as hc:
            resp = await hc.get("https://api.mymemory.translated.net/get",
                                params={"q": text[:450], "langpair": "zh|en"})
            if resp.status_code == 200:
                data = resp.json()
                t = (data.get("responseData") or {}).get("translatedText") or ""
                if t and "MYMEMORY WARNING" not in t:
                    return t.strip()
    except Exception:
        pass
    return None


async def translate_prompt(text: str) -> dict:
    """中文→英文：在线优先，词典兜底。附未识别词与领域违规。"""
    if not text or not CJK.search(text):
        return {"english": text, "source": "passthrough", "unknown": [],
                "violations": check_domain(text)}
    online = await online_translate(text)
    if online:
        return {"english": online, "source": "online", "unknown": [],
                "violations": check_domain(online) + check_domain(text)}
    english, unknown = dict_translate(text)
    return {"english": english, "source": "dict", "unknown": unknown,
            "violations": check_domain(english) + check_domain(text)}


def check_domain(text: str) -> list[str]:
    """返回命中的违禁领域关键词。"""
    if not text:
        return []
    hits = [w for w in CN_BLOCKED if w in text]
    hits += [m.group(0).lower() for m in EN_BLOCKED.finditer(text)]
    return hits
