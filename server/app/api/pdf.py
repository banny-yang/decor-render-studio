from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Asset, Project, Task, User
from ..schemas import TaskOut
from ..services import pdf_service
from ..services.estimate_service import calibrate_scale, estimate_rooms
from .assets import asset_to_out
from .deps import get_current_user

router = APIRouter(prefix="/api/pdf", tags=["pdf"])


def _to_asset(db: Session, path, kind: str, project_id: int | None) -> Asset:
    a = Asset(project_id=project_id, kind=kind,
              file_path=str(path.relative_to(settings.data_dir)),
              filename=path.name)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


class ProposalIn(BaseModel):
    title: str = "室内设计方案书"
    customer: str = ""
    project_id: int | None = None
    task_ids: list[int] = Field(min_length=1, max_length=60)


@router.post("/proposal")
def proposal(body: ProposalIn, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    """按任务产物生成方案书 PDF（按房间标签分组）。"""
    tasks = []
    for tid in body.task_ids:
        t = db.get(Task, tid)
        if t and t.status == "done":
            tasks.append(t)
    if not tasks:
        raise HTTPException(400, "没有已完成的任务可导出")

    sections: dict[str, list[str]] = {}
    order: list[str] = []
    for t in tasks:
        outs = db.scalars(select(Asset).where(Asset.task_id == t.id, Asset.kind == "output")
                          .order_by(Asset.id)).all()
        key = (t.params or {}).get("room_label") or f"任务 #{t.id}"
        if key not in sections:
            sections[key] = []
            order.append(key)
        sections[key].extend(str(settings.data_dir / o.file_path) for o in outs)
    path = pdf_service.build_proposal(
        body.title, body.customer,
        [{"heading": k, "image_paths": sections[k]} for k in order])
    return asset_to_out(_to_asset(db, path, "pdf", body.project_id))


class EstimatePdfIn(BaseModel):
    title: str = "工程量估算表"
    customer: str = ""
    project_id: int | None = None
    rooms: list[dict] = Field(min_length=1)   # {label, bbox}
    mm_per_px: float | None = None
    texts: list[str] = []


@router.post("/estimate")
def estimate_pdf(body: EstimatePdfIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    scale = body.mm_per_px
    if scale is None:
        scale, _method = calibrate_scale(body.rooms, body.texts)
        if scale is None:
            raise HTTPException(400, "无法自动标定比例尺，请手动填写 mm_per_px")
    data = estimate_rooms(body.rooms, scale)
    path = pdf_service.build_estimate(body.title, body.customer, data)
    return asset_to_out(_to_asset(db, path, "pdf", body.project_id))


class ComparePdfIn(BaseModel):
    title: str = "老房改造对比"
    customer: str = ""
    project_id: int | None = None
    task_ids: list[int] = Field(min_length=1, max_length=20)


@router.post("/compare")
def compare_pdf(body: ComparePdfIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    pairs = []
    for tid in body.task_ids:
        t = db.get(Task, tid)
        if not t or t.status != "done":
            continue
        src = db.scalar(select(Asset).where(Asset.task_id == t.id, Asset.kind == "input"))
        outs = db.scalars(select(Asset).where(Asset.task_id == t.id, Asset.kind == "output")
                          .order_by(Asset.id)).all()
        if src and outs:
            pairs.append({
                "heading": (t.params or {}).get("room_label") or f"任务 #{t.id}",
                "before_path": str(settings.data_dir / src.file_path),
                "after_path": str(settings.data_dir / outs[0].file_path),
            })
    if not pairs:
        raise HTTPException(400, "没有可导出的改造任务")
    path = pdf_service.build_compare(body.title, body.customer, pairs)
    return asset_to_out(_to_asset(db, path, "pdf", body.project_id))
