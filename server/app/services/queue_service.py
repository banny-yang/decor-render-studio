"""全局任务队列：DB 持久化 FIFO 调度（GPU 单卡串行），多用户公平排队。

- create_task 只入库（status=pending）并 notify；本模块的后台 worker 逐个取出提交
- 队列位置 = pending 按提交顺序排序的名次；预计等待 = 位次 × 近期平均耗时
- 每次取任务后向剩余 pending 任务推送位移后的队列位置（SSE）
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import func, select

from ..config import settings
from ..db import SessionLocal
from ..event_bus import bus
from ..models import Task, utcnow

log = logging.getLogger("queue_service")

TERMINAL = ("done", "error", "cancelled")

_worker: asyncio.Task | None = None
_wake = asyncio.Event()
# 近期完成任务耗时（秒），用于预计等待
_recent_durations: list[float] = []
_started_at: dict[int, float] = {}      # task_id -> worker 开始处理的时刻


def notify_new_task():
    """新任务入库后唤醒 worker（跨线程安全：Event.set 在无运行 loop 时忽略）。"""
    try:
        _wake.set()
    except RuntimeError:
        pass


def start_dispatcher():
    global _worker
    if _worker is None or _worker.done():
        _wake.clear()
        _worker = asyncio.create_task(_worker_loop())
        log.info("任务调度器已启动（并发=1，FIFO）")


async def _worker_loop():
    """逐个取 pending 任务处理，直到终态再取下一个。"""
    while True:
        try:
            task_id = _pick_next()
            if task_id is None:
                _wake.clear()
                try:
                    await asyncio.wait_for(_wake.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
                continue
            await _process(task_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("调度循环异常")
            await asyncio.sleep(1)


def _pick_next() -> int | None:
    with SessionLocal() as db:
        t = db.scalar(select(Task).where(Task.status == "pending")
                      .order_by(Task.id).limit(1))
        return t.id if t else None


async def _process(task_id: int):
    from . import task_service

    _started_at[task_id] = time.monotonic()
    try:
        if settings.mock_comfyui:
            await task_service._run_mock(task_id)   # mock 内部自带 step 推进
        else:
            await task_service._submit_to_comfyui(task_id)
    except Exception as e:
        log.exception("任务 %s 提交失败", task_id)
        with SessionLocal() as db:
            task = db.get(Task, task_id)
            if task and task.status not in TERMINAL:
                task.status, task.error, task.finished_at = "error", f"{e}"[:2000], utcnow()
                db.commit()
        await bus.publish(f"task:{task_id}",
                          {"task_id": task_id, "status": "error", "error": str(e)[:2000]})
        await _after_pick(task_id)
        return

    # 等待终态（listener 驱动 running→done/error）；mock 路径 _run_mock 返回时已是终态
    deadline = time.monotonic() + settings.queue_task_timeout
    while time.monotonic() < deadline:
        with SessionLocal() as db:
            t = db.get(Task, task_id)
            if t is None or t.status in TERMINAL:
                break
        await asyncio.sleep(0.5)
    else:
        log.error("任务 %s 等待超时（%ss），标记失败", task_id, settings.queue_task_timeout)
        with SessionLocal() as db:
            t = db.get(Task, task_id)
            if t and t.status not in TERMINAL:
                t.status, t.error, t.finished_at = "error", "执行超时", utcnow()
                db.commit()
        await bus.publish(f"task:{task_id}",
                          {"task_id": task_id, "status": "error", "error": "执行超时"})

    # 记录耗时（真实执行区间：开始处理 → 终态）
    start = _started_at.pop(task_id, None)
    if start is not None:
        _recent_durations.append(time.monotonic() - start)
        del _recent_durations[:-10]      # 保留最近 10 个
    await _after_pick(task_id)


async def _after_pick(finished_task_id: int):
    """一个任务离开队列后，向剩余 pending 任务推送新的队列位置。"""
    with SessionLocal() as db:
        pending = db.scalars(select(Task).where(Task.status == "pending")
                             .order_by(Task.id)).all()
        avg = avg_duration_sec()
        for pos, t in enumerate(pending, start=1):
            await bus.publish(f"task:{t.id}", {
                "task_id": t.id, "status": "pending", "queue_position": pos,
                "queue_waiting": len(pending), "est_wait_sec": int(pos * avg),
            })


def avg_duration_sec() -> float:
    if not _recent_durations:
        return 25.0        # Lightning 默认档一图约 20~30s
    return sum(_recent_durations) / len(_recent_durations)


def queue_snapshot(db) -> dict:
    """全局队列概览：运行中 / 排队数 / 平均耗时。"""
    running = db.scalar(select(func.count(Task.id)).where(Task.status.in_(("queued", "running"))))
    waiting = db.scalar(select(func.count(Task.id)).where(Task.status == "pending"))
    return {"running": running or 0, "waiting": waiting or 0,
            "avg_duration_sec": int(avg_duration_sec()),
            "concurrency": settings.max_concurrency}


def task_queue_info(db, task: Task) -> dict:
    """单个任务的排队信息（挂到 TaskOut）。"""
    if task.status != "pending":
        return {"queue_position": 0, "queue_waiting": 0, "est_wait_sec": 0}
    ahead = db.scalar(select(func.count(Task.id)).where(
        Task.status == "pending", Task.id < task.id))
    waiting = db.scalar(select(func.count(Task.id)).where(Task.status == "pending"))
    pos = (ahead or 0) + 1
    return {"queue_position": pos, "queue_waiting": waiting or 0,
            "est_wait_sec": int(pos * avg_duration_sec())}
