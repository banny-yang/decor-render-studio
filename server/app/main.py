import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import assets, auth, cad, estimate, floorplan, pdf, projects, prompt, renovate, tasks, templates
from .comfy.client import init_client
from .comfy.listener import start_listener
from .config import settings
from .seed import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.assets_dir.mkdir(parents=True, exist_ok=True)
    if settings.mock_comfyui:
        logging.getLogger("main").warning("MOCK_COMFYUI=true：使用模拟推理模式（仅供联调）")
    else:
        init_client(settings.comfyui_url)
        start_listener()
    # 重启恢复：上次中断的任务（queued/running）重新排队，由调度器再次执行
    from sqlalchemy import select
    from .db import SessionLocal
    from .models import Task
    from .services.queue_service import start_dispatcher
    with SessionLocal() as db:
        stuck = db.scalars(select(Task).where(Task.status.in_(("queued", "running")))).all()
        for t in stuck:
            t.status, t.progress = "pending", 0.0
        if stuck:
            db.commit()
            logging.getLogger("main").info("重启恢复：%s 个未完成任务重新排队", len(stuck))
    # 全局任务队列（多用户 FIFO 排队，串行执行）
    start_dispatcher()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(assets.router)
app.include_router(tasks.router)
app.include_router(projects.router)
app.include_router(templates.router)
app.include_router(prompt.router)
app.include_router(cad.router)
app.include_router(floorplan.router)
app.include_router(renovate.router)
app.include_router(estimate.router)
app.include_router(pdf.router)


@app.get("/api/health")
def health():
    return {"ok": True, "mock": settings.mock_comfyui}


# 生产模式：托管前端构建产物（web/dist）
_dist = settings.server_dir.parent / "web" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="web")
