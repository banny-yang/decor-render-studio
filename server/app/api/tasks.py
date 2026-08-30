import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, get_db
from ..event_bus import bus
from ..models import Asset, Task, User, utcnow
from ..schemas import TaskCreateIn, TaskOut
from ..services import queue_service
from ..services.task_service import create_task
from .assets import asset_to_out
from .deps import get_current_user

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

TERMINAL = ("done", "error", "cancelled")


def task_to_out(db: Session, t: Task) -> TaskOut:
    outputs = db.scalars(select(Asset).where(Asset.task_id == t.id, Asset.kind == "output")
                         .order_by(Asset.id)).all()
    input_a = db.scalar(select(Asset).where(Asset.task_id == t.id, Asset.kind == "input"))
    out = TaskOut.model_validate(t)
    out.outputs = [asset_to_out(a) for a in outputs]
    out.input_asset = asset_to_out(input_a) if input_a else None
    out.queue_position, out.queue_waiting, out.est_wait_sec = \
        queue_service.task_queue_info(db, t).values()
    return out


def _snapshot(db: Session, task_id: int) -> dict:
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    return task_to_out(db, t).model_dump(mode="json")


@router.post("", response_model=TaskOut)
async def create(body: TaskCreateIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    if body.mode in ("img2img", "inpaint", "floorplan", "renovate") and not body.input_asset_id:
        raise HTTPException(400, "图生图/局部重绘/平面图渲染/老房改造必须上传输入图片")
    if body.mode == "refstyle" and not body.ref_asset_id:
        raise HTTPException(400, "参考图风格匹配必须上传参考图片")
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
               scope: str = "mine",   # mine=自己的（默认）| all=全部（仅管理员）
               limit: int = Query(default=50, le=200), offset: int = 0,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Task).order_by(Task.id.desc())
    if project_id:
        q = q.where(Task.project_id == project_id)
    if status:
        q = q.where(Task.status == status)
    # 多用户隔离：普通用户只能看自己的任务；管理员可 ?scope=all 看全部
    if not (user.is_admin and scope == "all"):
        q = q.where(Task.user_id == user.id)
    items = db.scalars(q.limit(limit).offset(offset)).all()
    return [task_to_out(db, t) for t in items]


@router.get("/meta/queue")
def queue_overview(user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """全局队列概览 + 我方排队中的任务（位次为全局 FIFO 位次）。"""
    snap = queue_service.queue_snapshot(db)
    all_pending = db.scalars(select(Task).where(Task.status == "pending")
                             .order_by(Task.id)).all()
    pos_map = {t.id: i for i, t in enumerate(all_pending, start=1)}
    avg = queue_service.avg_duration_sec()
    snap["my_pending"] = [
        {"id": t.id, "queue_position": pos_map[t.id],
         "est_wait_sec": int((pos_map[t.id] + snap["running"]) * avg),
         "prompt": (t.prompt or "")[:30], "mode": t.mode}
        for t in all_pending if t.user_id == user.id]
    return snap


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    if not user.is_admin and t.user_id != user.id:
        raise HTTPException(404, "任务不存在")
    return task_to_out(db, t)


@router.post("/{task_id}/cancel", response_model=TaskOut)
async def cancel_task(task_id: int, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """取消排队/执行中的任务：pending 直接取消；queued/running 通知 ComfyUI。"""
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    if not user.is_admin and t.user_id != user.id:
        raise HTTPException(404, "任务不存在")
    if t.status in TERMINAL:
        raise HTTPException(400, f"任务已结束（{t.status}），无法取消")
    orig_status = t.status
    t.status, t.finished_at = "cancelled", utcnow()
    t.error = "用户取消"
    db.commit()
    await bus.publish(f"task:{task_id}",
                      {"task_id": task_id, "status": "cancelled", "error": "用户取消"})
    if not settings.mock_comfyui and t.prompt_id:
        from ..comfy.client import client
        try:
            if orig_status == "queued":           # 还在 ComfyUI 队列：仅移除，不影响正在跑的任务
                await client.queue_delete(t.prompt_id)
            elif orig_status == "running":
                await client.queue_delete(t.prompt_id)
                await client.interrupt()
        except Exception:
            pass           # ComfyUI 侧清理尽力而为
    if orig_status == "pending":
        await queue_service._after_pick(task_id)   # 通知后面任务位置前移
    db.refresh(t)
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
