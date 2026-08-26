import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Asset, Task
from ..schemas import AssetOut
from .deps import get_current_user

router = APIRouter(prefix="/api/assets", tags=["assets"])

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def asset_to_out(a: Asset) -> AssetOut:
    return AssetOut(
        id=a.id, kind=a.kind, filename=a.filename, url=f"/api/assets/{a.id}/raw",
        width=a.width, height=a.height, created_at=a.created_at,
    )


@router.post("/upload", response_model=AssetOut)
async def upload(file: UploadFile = File(...), user=Depends(get_current_user),
                 db: Session = Depends(get_db)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"不支持的图片格式: {ext}")
    data = await file.read()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 30MB")

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex[:12]}{ext}"
    (settings.uploads_dir / name).write_bytes(data)

    a = Asset(kind="upload", file_path=f"uploads/{name}", filename=file.filename or name)
    db.add(a)
    db.commit()
    db.refresh(a)
    return asset_to_out(a)


@router.get("/{asset_id}/raw")
def raw(asset_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(404, "图片不存在")
    path = settings.data_dir / a.file_path
    if not path.is_file():
        raise HTTPException(404, "图片文件缺失")
    return FileResponse(path)


@router.get("")
def list_assets(task_id: int | None = None, kind: str | None = None, limit: int = 200,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Asset).order_by(Asset.id.desc()).limit(min(limit, 500))
    if task_id:
        q = q.where(Asset.task_id == task_id)
    if kind:
        q = q.where(Asset.kind == kind)
    return [asset_to_out(a) for a in db.scalars(q)]


@router.get("/{asset_id}/task")
def asset_task(asset_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """通过产物反查任务（前端“以此图重绘”需要拿到输入参数）。"""
    a = db.get(Asset, asset_id)
    if a is None or a.task_id is None:
        raise HTTPException(404, "无关联任务")
    t = db.get(Task, a.task_id)
    from .tasks import task_to_out
    return task_to_out(db, t)
