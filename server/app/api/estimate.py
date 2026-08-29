from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Asset, User
from ..services.estimate_service import calibrate_scale, estimate_rooms
from .deps import get_current_user

router = APIRouter(prefix="/api/estimate", tags=["estimate"])


class RoomBox(BaseModel):
    label: str = ""
    room_type: str = ""
    bbox: list[float]


class EstimateIn(BaseModel):
    input_asset_id: int
    rooms: list[RoomBox] = Field(min_length=1)
    mm_per_px: float | None = Field(default=None, gt=0, le=100)
    texts: list[str] = []      # 户型图 OCR 文字（用于自动标定比例尺）


@router.post("")
def estimate(body: EstimateIn, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    rooms = [r.model_dump() for r in body.rooms]
    scale = body.mm_per_px
    auto_used = False
    method = "手动填写"
    if scale is None:
        scale, method = calibrate_scale(rooms, body.texts)
        auto_used = scale is not None
        if scale is None:
            from fastapi import HTTPException
            raise HTTPException(400, "无法从图纸标注自动标定比例尺，请手动填写（毫米/像素）")
    result = estimate_rooms(rooms, scale)
    result["scale_auto"] = auto_used
    result["scale_method"] = method
    return result
