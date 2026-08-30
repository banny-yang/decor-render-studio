"""任务编排：创建 → 提交 ComfyUI（或 Mock）→ 进度/归档。"""

import asyncio
import io
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select

from ..comfy.client import client as comfy_client
from ..config import settings
from ..db import SessionLocal
from ..event_bus import bus
from ..models import Asset, StyleTemplate, Task, utcnow
from ..schemas import TaskCreateIn
from .workflow_builder import build_workflow

log = logging.getLogger("task_service")

TERMINAL = ("done", "error", "cancelled")


async def _publish(task_id: int, **fields):
    fields.setdefault("task_id", task_id)
    await bus.publish(f"task:{task_id}", fields)


def _merge_template(db, data: TaskCreateIn) -> tuple[str, str, dict]:
    """把风格模板的提示词/参数与用户输入合并。用户显式提供的优先。"""
    positive, negative = data.prompt.strip(), data.negative_prompt.strip()
    tparams: dict = {}
    if data.template_id:
        tpl = db.get(StyleTemplate, data.template_id)
        if tpl:
            tparams = dict(tpl.params or {})
            if tpl.positive_prompt:
                positive = f"{tpl.positive_prompt}, {positive}" if positive else tpl.positive_prompt
            if tpl.negative_prompt:
                negative = f"{tpl.negative_prompt}, {negative}" if negative else tpl.negative_prompt
    return positive, negative, tparams


def _params_dict(data: TaskCreateIn, positive: str, negative: str, tparams: dict) -> dict:
    """模板参数作为底，用户显式传入的字段覆盖。

    线稿→效果图实测调优：denoise 1.0 + ControlNet 0.75 + steps 8 + cfg 2.0
    （denoise 低于 1.0 会残留线稿白色底，出图偏平面）。
    """
    default_denoise = {"t2i": 1.0, "inpaint": 1.0, "floorplan": 0.85,
                       "renovate": 0.85}.get(data.mode, 0.85)
    default_strength = 0.85 if data.mode == "floorplan" else 0.75
    p = {
        "positive": positive,
        "negative": negative,
        "steps": tparams.get("steps", 8 if data.mode != "t2i" else 6),
        "cfg": tparams.get("cfg", 2.0 if data.mode != "t2i" else 1.5),
        "sampler": tparams.get("sampler", "euler"),
        "scheduler": tparams.get("scheduler", "sgm_uniform"),
        "denoise": tparams.get("denoise", default_denoise),
        "seed": data.seed,
        "width": tparams.get("width", 1024),
        "height": tparams.get("height", 768),
        "batch": data.batch,
        "controlnet_model": data.controlnet_model,
        "controlnet_strength": tparams.get("controlnet_strength", default_strength),
    }
    for k in ("steps", "cfg", "sampler", "scheduler", "denoise"):
        v = getattr(data, k)
        if v is not None:
            p[k] = v
    return p


async def create_task(db, user_id: int | None, data: TaskCreateIn) -> Task:
    positive, negative, tparams = _merge_template(db, data)

    # 中文提示词自动翻译（在线优先，词典兜底；原词存档于 params）
    from ..services.prompt_service import CJK, translate_prompt
    if CJK.search(positive):
        try:
            result = await translate_prompt(positive)
            positive = result["english"] or positive
        except Exception:
            log.warning("提示词翻译失败，按原样提交", exc_info=True)
    if CJK.search(negative):
        try:
            negative = (await translate_prompt(negative))["english"] or negative
        except Exception:
            pass

    p = _params_dict(data, positive, negative, tparams)
    # 输入资产引用持久化，供队列 worker 重启后仍能提交
    p["_in"] = {"input_asset_id": data.input_asset_id,
                "mask_asset_id": data.mask_asset_id,
                "ref_asset_id": data.ref_asset_id}

    task = Task(
        mode=data.mode, status="pending", project_id=data.project_id, user_id=user_id,
        template_id=data.template_id, prompt=data.prompt, negative_prompt=data.negative_prompt,
        params=p,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 有输入图的模式：回链输入资产
    if data.mode in ("img2img", "inpaint", "floorplan", "renovate") and data.input_asset_id:
        a = db.get(Asset, data.input_asset_id)
        if a:
            a.task_id = task.id
            a.kind = "input"
            db.commit()

    # 入全局队列，由 queue_service 的 worker 按 FIFO 提交（多用户排队）
    from . import queue_service
    with SessionLocal() as qdb:
        info = queue_service.task_queue_info(qdb, task)
    await _publish(task.id, status="pending", **info)
    queue_service.notify_new_task()
    return task


async def _submit_to_comfyui(task_id: int):
    """从 DB 读取任务（含 params._in 资产引用），构建工作流并提交 ComfyUI。"""
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is None or task.status != "pending":   # 已被取消则跳过
            return
        p = dict(task.params)
        mode = task.mode
        inputs = p.get("_in") or {}
        input_asset_id = inputs.get("input_asset_id")
        mask_asset_id = inputs.get("mask_asset_id")
        ref_asset_id = inputs.get("ref_asset_id")

        # 输入图上传到 ComfyUI
        input_name = mask_name = ref_name = None

        # refstyle：上传参考风格图（无结构线稿时按参考图宽高比定尺寸）
        if mode == "refstyle":
            if not ref_asset_id:
                raise ValueError("参考图风格匹配必须提供参考图片")
            from PIL import Image as _Img
            ref = db.get(Asset, ref_asset_id)
            rfile = settings.data_dir / ref.file_path
            if not input_asset_id:
                with _Img.open(rfile) as ri:
                    ratio = ri.width / ri.height
                p["width"], p["height"] = (1024, 768) if ratio >= 1.2 else \
                    (768, 1024) if ratio <= 0.83 else (896, 896)
            ref_name = await comfy_client.upload_image(rfile.read_bytes(),
                                                       f"task{task_id}_ref.png")

        if mode in ("img2img", "inpaint", "floorplan", "renovate"):
            asset = db.get(Asset, input_asset_id) if input_asset_id else None
            if asset is None:
                raise ValueError("图生图/局部重绘必须提供输入图片")
            file = settings.data_dir / asset.file_path
            input_name = await comfy_client.upload_image(file.read_bytes(), f"task{task_id}_input.png")
            if mode == "inpaint":
                if not mask_asset_id:
                    raise ValueError("局部重绘必须提供掩码图片")
                m = db.get(Asset, mask_asset_id)
                mfile = settings.data_dir / m.file_path
                mask_name = await comfy_client.upload_image(mfile.read_bytes(), f"task{task_id}_mask.png")

        wf = build_workflow(mode, p, input_name=input_name, mask_name=mask_name,
                            prefix=f"rvx/task{task_id}", ref_name=ref_name)
        pid = await comfy_client.submit(wf)
        task.prompt_id = pid
        task.status = "queued"
        db.commit()
    await _publish(task_id, status="queued")


async def finalize_task(task_id: int):
    """执行成功后：从 history 拉取产物并归档。"""
    from ..comfy.client import ComfyUIError

    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is None or task.status in TERMINAL:
            return
        pid = task.prompt_id

    hist: dict = {}
    for attempt in range(6):  # history 写入可能略滞后于 ws 事件
        hist = await comfy_client.history(pid)
        if hist.get("outputs"):
            break
        await asyncio.sleep(0.5)

    status_str = (hist.get("status") or {}).get("status_str")
    if status_str == "error":
        messages = (hist.get("status") or {}).get("messages") or []
        err = "ComfyUI 执行出错"
        for m in messages:
            if isinstance(m, list) and m and m[0] == "execution_error":
                err = m[1].get("exception_message", err) if len(m) > 1 else err
        with SessionLocal() as db:
            task = db.get(Task, task_id)
            task.status, task.error, task.finished_at = "error", str(err)[:2000], utcnow()
            db.commit()
        await _publish(task_id, status="error", error=str(err)[:2000])
        return

    outputs = hist.get("outputs") or {}
    saved: list[dict] = []
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        out_dir = settings.assets_dir / f"task{task_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        for node_out in outputs.values():
            for img in node_out.get("images", []):
                try:
                    blob = await comfy_client.view_image(
                        img["filename"], img.get("subfolder", ""), img.get("type", "output"))
                except Exception:
                    log.exception("下载产物失败 task=%s %s", task_id, img.get("filename"))
                    continue
                safe = re.sub(r"[^\w.-]", "_", img["filename"])
                (out_dir / safe).write_bytes(blob)
                asset = Asset(task_id=task_id, project_id=task.project_id, kind="output",
                              file_path=str((out_dir / safe).relative_to(settings.data_dir)),
                              filename=safe)
                db.add(asset)
                db.flush()
                saved.append({"asset_id": asset.id, "filename": safe})
        task.status, task.progress, task.finished_at = "done", 100.0, utcnow()
        db.commit()
    await _publish(task_id, status="done", progress=100.0, outputs=saved)


# ---------------- Mock 模式（无 GPU 时联调用） ----------------

async def _run_mock(task_id: int):
    from PIL import Image, ImageDraw, ImageFont

    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is None or task.status != "pending":   # 已被取消则跳过
            return
        p = dict(task.params)
        task.status = "queued"
        db.commit()
    await _publish(task_id, status="queued")

    await asyncio.sleep(0.5)
    steps = p.get("steps", 6)
    for s in range(1, steps + 1):
        await asyncio.sleep(0.45)
        with SessionLocal() as db:
            task = db.get(Task, task_id)
            if task.status in TERMINAL:                # 中途取消
                return
            pct = round(s / steps * 95, 1)
            task.status, task.progress = "running", pct
            task.step, task.total_steps = s, steps
            db.commit()
        await _publish(task_id, status="running", progress=pct, step=s, total_steps=steps)

    w, h = p.get("width", 1024), p.get("height", 768)
    batch = p.get("batch", 4)
    out_dir = settings.assets_dir / f"task{task_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[dict] = []
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        for i in range(batch):
            img = Image.new("RGB", (w, h))
            dr = ImageDraw.Draw(img)
            for y in range(h):  # 简单渐变
                hue = int(200 * y / h + i * 30) % 256
                dr.line([(0, y), (w, y)], fill=(30, hue, 200 - hue // 2))
            try:
                font = ImageFont.load_default(28)
                small = ImageFont.load_default(18)
            except TypeError:
                font = small = ImageFont.load_default()
            dr.text((24, 24), f"MOCK  task #{task_id}  [{task.mode}]  {i + 1}/{batch}", fill="white", font=font)
            dr.text((24, 70), (p.get("positive", "")[:60] or "-"), fill="white", font=small)
            name = f"mock_{task_id}_{i + 1}.png"
            img.save(out_dir / name, format="PNG")
            asset = Asset(task_id=task_id, project_id=task.project_id, kind="output",
                          file_path=str((out_dir / name).relative_to(settings.data_dir)),
                          filename=name, width=w, height=h)
            db.add(asset)
            db.flush()
            saved.append({"asset_id": asset.id, "filename": name})
        task.status, task.progress, task.finished_at = "done", 100.0, utcnow()
        db.commit()
    await _publish(task_id, status="done", progress=100.0, outputs=saved)
