import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Asset, StyleTemplate, User
from ..schemas import TaskCreateIn, TaskOut
from ..services.floorplan_service import (DEFAULT_STYLE, ROOM_TYPES, STYLE_FRAGMENTS,
                                          analyze_floorplan, crop_room, size_by_bbox)
from ..services.task_service import create_task
from .assets import asset_to_out
from .deps import get_current_user
from .tasks import task_to_out

router = APIRouter(prefix="/api/floorplan", tags=["floorplan"])

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class RoomIn(BaseModel):
    label: str = Field(max_length=32)
    room_type: str
    bbox: list[float] | None = None


class RenderIn(BaseModel):
    input_asset_id: int
    rooms: list[RoomIn] = Field(min_length=1, max_length=20)
    template_id: int | None = None
    view: str = Field(pattern="^(perspective|plan)$")
    batch_per_room: int = Field(default=1, ge=1, le=2)
    project_id: int | None = None


@router.post("/analyze")
async def analyze(file: UploadFile = File(...), user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """上传户型图 → OCR 识别房间清单（建议值，前端可编辑）。"""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"不支持的图片格式: {ext}")
    data = await file.read()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 30MB")

    try:
        result = await run_in_threadpool(analyze_floorplan, data)
    except Exception as e:
        raise HTTPException(500, f"户型图识别失败: {e}")

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex[:12]}{ext}"
    (settings.uploads_dir / name).write_bytes(data)
    a = Asset(kind="upload", file_path=f"uploads/{name}", filename=file.filename or name)
    db.add(a)
    db.commit()
    db.refresh(a)

    return {"asset": asset_to_out(a), "rooms": result["rooms"],
            "size": result["size"], "texts": result["texts"],
            "room_types": {k: v["label"] for k, v in ROOM_TYPES.items()}}


class MatrixIn(BaseModel):
    rooms: list[RoomIn] = Field(min_length=1, max_length=4)
    template_ids: list[int] = Field(min_length=1, max_length=4)
    project_id: int | None = None


@router.post("/matrix")
async def matrix(body: MatrixIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """方案矩阵：房间 × 风格 批量生成透视效果图（每格 1 张）。"""
    from ..models import StyleTemplate as _T
    tpls = []
    for tid in body.template_ids:
        t = db.get(_T, tid)
        if t is None:
            raise HTTPException(404, f"模板 {tid} 不存在")
        tpls.append(t)

    tasks = []
    for room in body.rooms:
        cfg = ROOM_TYPES.get(room.room_type)
        if cfg is None:
            raise HTTPException(400, f"未知房间类型: {room.room_type}")
        for tpl in tpls:
            style = DEFAULT_STYLE
            for prefix, frag in STYLE_FRAGMENTS.items():
                if tpl.name.startswith(prefix):
                    style = frag
                    break
            width, height = size_by_bbox(room.bbox)
            req = TaskCreateIn(
                mode="t2i", project_id=body.project_id,
                prompt=f"{cfg['perspective']}, {style}",
                width=width, height=height,
                steps=tpl.params.get("steps"), cfg=tpl.params.get("cfg"),
                batch=1, seed=-1,
            )
            task = await create_task(db, user.id, req)
            out = task_to_out(db, task)
            out.params["room_label"] = room.label
            out.params["style_label"] = tpl.name
            tasks.append(out)
    return {"tasks": tasks}


@router.post("/render")
async def render(body: RenderIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """按确认后的房间清单批量建任务。view: perspective=透视效果图, plan=分房彩色平面图。"""
    src = db.get(Asset, body.input_asset_id)
    if src is None:
        raise HTTPException(404, "户型图不存在")
    src_bytes = (settings.data_dir / src.file_path).read_bytes()

    # 风格：取模板风格片段（不用模板整句提示词，避免模板里的房间类型词覆盖当前房间）
    tpl = db.get(StyleTemplate, body.template_id) if body.template_id else None
    style = DEFAULT_STYLE
    for prefix, frag in STYLE_FRAGMENTS.items():
        if tpl and tpl.name.startswith(prefix):
            style = frag
            break

    tasks = []
    for room in body.rooms:
        cfg = ROOM_TYPES.get(room.room_type)
        if cfg is None:
            raise HTTPException(400, f"未知房间类型: {room.room_type}")
        if body.view == "perspective":
            width, height = size_by_bbox(room.bbox)
            req = TaskCreateIn(
                mode="t2i", project_id=body.project_id,
                prompt=f"{cfg['perspective']}, {style}",
                width=width, height=height,
                steps=tpl.params.get("steps") if tpl else None,
                cfg=tpl.params.get("cfg") if tpl else None,
                batch=body.batch_per_room, seed=-1,
            )
        else:
            if not room.bbox:
                continue  # 平面视图需要房间框（手动添加的房间无框，跳过）
            crop_bytes = crop_room(src_bytes, room.bbox)
            cname = f"{uuid.uuid4().hex[:12]}_crop.png"
            (settings.uploads_dir / cname).write_bytes(crop_bytes)
            ca = Asset(kind="upload", file_path=f"uploads/{cname}",
                       filename=f"{room.label}_crop.png")
            db.add(ca)
            db.commit()
            db.refresh(ca)
            req = TaskCreateIn(
                mode="floorplan", project_id=body.project_id, template_id=body.template_id,
                prompt=f"{cfg['plan']}", input_asset_id=ca.id,
                batch=body.batch_per_room, seed=-1,
            )
        task = await create_task(db, user.id, req)
        task_out = task_to_out(db, task)
        task_out.params["room_label"] = room.label  # 前端分组显示用（仅本次响应）
        tasks.append(task_out)

    if not tasks:
        raise HTTPException(400, "没有可生成的房间（分房平面图需要识别出房间位置框）")
    return {"tasks": tasks}
