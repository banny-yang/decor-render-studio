"""首次启动初始化：建表 + 内置账号 + 8 套装修风格模板（按 Lightning 参数预设）。"""

from sqlalchemy import select

from .db import Base, SessionLocal, engine
from .models import StyleTemplate, User
from .security import hash_password

NEGATIVE_BASE = (
    "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, "
    "fewer digits, cropped, worst quality, low quality, jpeg artifacts, watermark, "
    "signature, blurry, deformed, disfigured, cartoon, painting, illustration"
)

# Lightning 版公共参数（按线稿→效果图实测调优：denoise 1.0 + 强度 0.75 + steps 8 + cfg 2.0）
LIGHTNING_DEFAULTS = {
    "steps": 8,
    "cfg": 2.0,
    "sampler": "euler",
    "scheduler": "sgm_uniform",
    "denoise": 1.0,
    "controlnet_strength": 0.75,
}

TEMPLATES = [
    (
        "现代简约",
        "客厅",
        "modern minimalist living room, clean lines, neutral color palette, white wall, "
        "wood floor, large window with natural light, comfortable fabric sofa, "
        "indoor plant, professional interior photography, photorealistic, 8k, high detail",
        NEGATIVE_BASE,
        {"width": 1024, "height": 768},
    ),
    (
        "奶油风",
        "客厅",
        "cream style living room, warm beige and off-white tones, soft rounded furniture, "
        "boucle sofa, curved lines, milk coffee color palette, cozy atmosphere, "
        "diffused warm lighting, gauzy curtains, professional interior photography, photorealistic, 8k",
        NEGATIVE_BASE,
        {"width": 1024, "height": 768},
    ),
    (
        "新中式",
        "客厅",
        "new chinese style living room, modern oriental design, dark wood furniture, "
        "ink painting artwork, lattice screen, celadon vase, tea table, warm ambient light, "
        "elegant zen atmosphere, professional interior photography, photorealistic, 8k",
        NEGATIVE_BASE,
        {"width": 1024, "height": 768},
    ),
    (
        "侘寂风",
        "客厅",
        "wabi-sabi style living room, rustic minimalism, textured lime plaster wall, "
        "natural wood, linen fabric, dried branch in ceramic vase, imperfection aesthetic, "
        "soft natural light, muted earth tones, professional interior photography, photorealistic, 8k",
        NEGATIVE_BASE,
        {"width": 1024, "height": 768},
    ),
    (
        "法式轻奢",
        "客厅",
        "french light luxury living room, elegant moldings on wall, brass accents, "
        "velvet sofa, marble coffee table, crystal chandelier, arched doorways, "
        "soft warm color palette, professional interior photography, photorealistic, 8k",
        NEGATIVE_BASE,
        {"width": 1024, "height": 768},
    ),
    (
        "轻奢现代",
        "客厅",
        "modern luxury living room, dark green and gold accents, marble wall, "
        "designer sofa, metal light fixture, high-end materials, sophisticated ambiance, "
        "professional interior photography, photorealistic, 8k, high detail",
        NEGATIVE_BASE,
        {"width": 1024, "height": 768},
    ),
    (
        "日式原木",
        "客厅",
        "japanese zen style living room, natural wood furniture, tatami, shoji screen, "
        "low platform sofa, paper floor lamp, bonsai, warm wood tones, minimal decoration, "
        "soft natural light, professional interior photography, photorealistic, 8k",
        NEGATIVE_BASE,
        {"width": 1024, "height": 768},
    ),
        (
        "工业风",
        "客厅",
        "industrial style living room, exposed brick wall, concrete ceiling, "
        "black metal frame, leather sofa, edison bulb pendant lights, open floor plan, "
        "loft apartment, professional interior photography, photorealistic, 8k",
        NEGATIVE_BASE,
        {"width": 1024, "height": 768},
    ),
]

# 平面图渲染模板：俯视彩色平面布置图（负面词禁透视/照片感）
FLOORPLAN_BASE = (
    "top-down view, 2D interior design floor plan rendering, colored walls, "
    "furniture layout, professional plan illustration, clean edges, high detail"
)
FLOORPLAN_NEGATIVE = NEGATIVE_BASE + ", perspective, 3d view, photorealistic interior, isometric"

FLOORPLAN_TEMPLATES = [
    (
        "平面图·现代简约",
        "modern minimalist style, light gray walls, oak wooden floor texture, "
        "gray fabric sofa, simple furniture layout",
    ),
    (
        "平面图·北欧原木",
        "Scandinavian style, white walls, light oak wood floor texture, "
        "beige furniture, green plants, cozy layout",
    ),
    (
        "平面图·新中式",
        "new Chinese style, warm beige walls, dark walnut wood floor texture, "
        "traditional Chinese furniture layout, elegant tones",
    ),
    (
        "平面图·轻奢",
        "light luxury style, cream walls with marble accents, dark wood floor texture, "
        "designer furniture layout, gold accents",
    ),
]


def init_db():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == "admin")) is None:
            db.add(User(username="admin", password_hash=hash_password("admin123"),
                        display_name="管理员", is_admin=True))
        for name, category, pos, neg, extra in TEMPLATES:
            if db.scalar(select(StyleTemplate).where(StyleTemplate.name == name)) is None:
                params = {**LIGHTNING_DEFAULTS, **extra}
                db.add(StyleTemplate(name=name, category=category, positive_prompt=pos,
                                     negative_prompt=neg, params=params, is_builtin=True))
        for name, style_prompt in FLOORPLAN_TEMPLATES:
            if db.scalar(select(StyleTemplate).where(StyleTemplate.name == name)) is None:
                params = {**LIGHTNING_DEFAULTS, "denoise": 0.85, "controlnet_strength": 0.85,
                          "width": 1024, "height": 768}
                db.add(StyleTemplate(name=name, category="平面图",
                                     positive_prompt=f"{FLOORPLAN_BASE}, {style_prompt}",
                                     negative_prompt=FLOORPLAN_NEGATIVE, params=params,
                                     is_builtin=True))
        db.commit()
