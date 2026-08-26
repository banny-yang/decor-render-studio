import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import assets, auth, cad, floorplan, projects, prompt, tasks, templates
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


@app.get("/api/health")
def health():
    return {"ok": True, "mock": settings.mock_comfyui}


# 生产模式：托管前端构建产物（web/dist）
_dist = settings.server_dir.parent / "web" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="web")
