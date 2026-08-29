import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Asset, Task, User
from .assets import asset_to_out
from .deps import get_current_user

router = APIRouter(prefix="/api/renovate", tags=["renovate"])


class CompareIn(BaseModel):
    task_id: int
    output_index: int = 0   # 多张产物时选第几张


@router.post("/compare")
def compare(body: CompareIn, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    """把改造任务的输入图与产物合成为左右分屏对比图。"""
    from PIL import Image, ImageDraw, ImageFont

    task = db.get(Task, body.task_id)
    if task is None or task.mode != "renovate":
        raise HTTPException(404, "改造任务不存在")
    if task.status != "done":
        raise HTTPException(400, "任务尚未完成")

    src = db.scalar(select(Asset).where(Asset.task_id == task.id, Asset.kind == "input"))
    outputs = db.scalars(select(Asset).where(Asset.task_id == task.id, Asset.kind == "output")
                         .order_by(Asset.id)).all()
    if src is None or not outputs or body.output_index >= len(outputs):
        raise HTTPException(400, "缺少输入图或产物")

    before = Image.open(settings.data_dir / src.file_path).convert("RGB")
    after = Image.open(settings.data_dir / outputs[body.output_index].file_path).convert("RGB")

    # 统一高度（以 after 为准，before 按比例缩放后居中裁剪到同宽）
    target_h = after.height
    before_scaled = before.resize(
        (int(before.width * target_h / before.height), target_h), Image.LANCZOS)
    target_w = after.width
    if before_scaled.width > target_w:
        x0 = (before_scaled.width - target_w) // 2
        before_scaled = before_scaled.crop((x0, 0, x0 + target_w, target_h))
    else:
        # before 更窄：把 after 视角对齐（简单居中放大）
        r = target_w / before_scaled.width
        before_scaled = before_scaled.resize((target_w, int(target_h * r)), Image.LANCZOS)
        before_scaled = before_scaled.crop((0, 0, target_w, target_h))

    # 拼接 + 分割线 + 标签
    gap = 8
    canvas = Image.new("RGB", (target_w * 2 + gap, target_h + 64), "#f5f6f8")
    canvas.paste(before_scaled, (0, 64))
    canvas.paste(after, (target_w + gap, 64))
    d = ImageDraw.Draw(canvas)
    d.rectangle([target_w, 64, target_w + gap, 64 + target_h], fill="#2f6e5d")
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 30)
    except OSError:
        font = ImageFont.load_default(30)
    d.text((24, 14), "改造前", fill="#555", font=font)
    tw = d.textlength("改造后", font=font)
    d.text((target_w * 2 + gap - 24 - tw, 14), "改造后", fill="#2f6e5d", font=font)

    out_dir = settings.data_dir / "renovate"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"compare_{task.id}_{body.output_index}_{uuid.uuid4().hex[:6]}.jpg"
    canvas.save(out_dir / name, quality=92)
    a = Asset(task_id=task.id, project_id=task.project_id, kind="renovate_compare",
              file_path=f"renovate/{name}", filename=name,
              width=canvas.width, height=canvas.height)
    db.add(a)
    db.commit()
    db.refresh(a)
    return asset_to_out(a)
