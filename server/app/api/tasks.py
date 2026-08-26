import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, get_db
from ..event_bus import bus
from ..models import Asset, Task, User
from ..schemas import TaskCreateIn, TaskOut
from ..services.task_service import create_task
from .assets import asset_to_out
from .deps import get_current_user

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

TERMINAL = ("done", "error")


def task_to_out(db: Session, t: Task) -> TaskOut:
    outputs = db.scalars(select(Asset).where(Asset.task_id == t.id, Asset.kind == "output")
                         .order_by(Asset.id)).all()
    input_a = db.scalar(select(Asset).where(Asset.task_id == t.id, Asset.kind == "input"))
    out = TaskOut.model_validate(t)
    out.outputs = [asset_to_out(a) for a in outputs]
    out.input_asset = asset_to_out(input_a) if input_a else None
    return out


def _snapshot(db: Session, task_id: int) -> dict:
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    return task_to_out(db, t).model_dump(mode="json")


@router.post("", response_model=TaskOut)
async def create(body: TaskCreateIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    if body.mode in ("img2img", "inpaint", "floorplan") and not body.input_asset_id:
        raise HTTPException(400, "图生图/局部重绘/平面图渲染必须上传输入图片")
    if body.mode == "inpaint" and not body.mask_asset_id:
        raise HTTPException(400, "局部重绘必须绘制掩码区域")
    # 领域限定：本系统仅生成建筑/装修设计图
    from ..services.prompt_service import check_domain
    violations = check_domain(body.prompt) + check_domain(body.negative_prompt)
    if violations:
        raise HTTPException(400, f"系统仅限建筑装修设计图生成，提示词包含其他领域内容：{violations}")
    task = await create_task(db, user.id, body)
    return task_to_out(db, task)


@router.get("")
def list_tasks(project_id: int | None = None, status: str | None = None,
               limit: int = Query(default=50, le=200), offset: int = 0,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Task).order_by(Task.id.desc())
    if project_id:
        q = q.where(Task.project_id == project_id)
    if status:
        q = q.where(Task.status == status)
    items = db.scalars(q.limit(limit).offset(offset)).all()
    return [task_to_out(db, t) for t in items]


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    return task_to_out(db, t)


@router.get("/{task_id}/events")
def task_events(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """SSE 进度流：先推一次完整快照，之后推送增量事件直到终态。"""
    if db.get(Task, task_id) is None:
        raise HTTPException(404, "任务不存在")

    async def gen():
        key = f"task:{task_id}"
        q = bus.subscribe(key)
        try:
            with SessionLocal() as sdb:
                snap = _snapshot(sdb, task_id)
            yield f"data: {json.dumps(snap, ensure_ascii=False)}\n\n"
            if snap["status"] in TERMINAL:
                return
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                # 增量事件后补一次落库快照，保证前端拿到最新产物列表
                with SessionLocal() as sdb:
                    snap = _snapshot(sdb, task_id)
                yield f"data: {json.dumps(snap, ensure_ascii=False)}\n\n"
                if snap["status"] in TERMINAL:
                    return
        finally:
            bus.unsubscribe(key, q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/meta/health")
async def comfy_health(user: User = Depends(get_current_user)):
    if settings.mock_comfyui:
        return {"mode": "mock", "healthy": True}
    from ..comfy.client import client
    return {"mode": "comfyui", "healthy": await client.healthy()}
