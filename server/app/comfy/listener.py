"""监听 ComfyUI WebSocket 进度事件，驱动任务状态机并经 EventBus 推给 SSE。"""

import asyncio
import json
import logging

import websockets

from ..db import SessionLocal
from ..event_bus import bus
from ..models import Task
from .client import client

log = logging.getLogger("comfy.listener")

TERMINAL = ("done", "error")


async def _publish(task_id: int, **fields):
    await bus.publish(f"task:{task_id}", fields)


async def _handle_event(msg: dict):
    mtype = msg.get("type")
    data = msg.get("data", {})
    pid = data.get("prompt_id")
    if not pid:  # status/心跳类消息
        return

    with SessionLocal() as db:
        task = db.query(Task).where(Task.prompt_id == pid).first()
        if task is None or task.status in TERMINAL:
            return
        task_id = task.id

    # 进度在 ws 线程里更新（KSampler 每步/每张都会推）
    if mtype == "progress":
        value, maxv = data.get("value", 0), data.get("max", 0)
        with SessionLocal() as db:
            task = db.query(Task).where(Task.id == task_id).first()
            task.total_steps = maxv
            task.step = value
            task.progress = round(value / maxv * 100, 1) if maxv else 0.0
            if task.status in ("queued", "pending"):
                task.status = "running"
            db.commit()
        await _publish(task_id, status="running", progress=task.progress,
                       step=value, total_steps=maxv)
        return

    if mtype == "execution_error":
        err = data.get("exception_message") or data.get("exception_type") or "ComfyUI 执行出错"
        with SessionLocal() as db:
            task = db.query(Task).where(Task.id == task_id).first()
            task.status = "error"
            task.error = str(err)[:2000]
            from ..models import utcnow
            task.finished_at = utcnow()
            db.commit()
        await _publish(task_id, status="error", error=str(err)[:2000])
        return

    if mtype == "execution_success":
        from ..services.task_service import finalize_task
        await finalize_task(task_id)


async def run_listener():
    """常驻后台任务：断线自动重连。"""
    if client is None:
        return
    while True:
        try:
            async with websockets.connect(client.ws_url(), max_size=2**26, open_timeout=10) as ws:
                log.info("已连接 ComfyUI WebSocket: %s", client.base_url)
                async for raw in ws:
                    if isinstance(raw, bytes):
                        continue
                    try:
                        await _handle_event(json.loads(raw))
                    except Exception:
                        log.exception("处理 ComfyUI 事件出错")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("ComfyUI WebSocket 断开: %s，5 秒后重连", e)
            await asyncio.sleep(5)


_listener_task = None


def start_listener():
    global _listener_task
    _listener_task = asyncio.create_task(run_listener())
    return _listener_task
