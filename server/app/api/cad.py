from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Asset, Project, User
from .assets import asset_to_out
from .deps import get_current_user

router = APIRouter(prefix="/api/cad", tags=["cad"])


@router.post("/convert")
async def convert(
    file: UploadFile = File(...),
    project_name: str = Form(default=""),
    title: str = Form(default=""),
    scale: str = Form(default="1:100"),
    sheet: str = Form(default="A3"),
    project_id: int | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """DXF 上传 -> 规范化施工图 PDF/PNG。同步转换（通常数秒内）。"""
    if not (file.filename or "").lower().endswith(".dxf"):
        raise HTTPException(400, "仅支持 DXF 格式；DWG 请先在 CAD 软件中另存为 DXF")
    data = await file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(400, "DXF 文件不能超过 50MB")
    if not data:
        raise HTTPException(400, "文件为空")

    if project_id and db.get(Project, project_id) is None:
        raise HTTPException(404, "关联项目不存在")

    from ..services.cad_service import convert_dxf
    try:
        result = await run_in_threadpool(convert_dxf, data, project_name, title, scale, sheet)
    except ValueError as e:
        raise HTTPException(400, str(e))

    assets = []
    for kind_key in ("png", "pdf"):
        info = result[kind_key]
        a = Asset(project_id=project_id, kind="cad",
                  file_path=info["path"], filename=info["filename"])
        db.add(a)
        db.flush()
        assets.append(asset_to_out(a))
    db.commit()

    return {"assets": assets, "layers": result["layers"], "entities": result["entities"]}
