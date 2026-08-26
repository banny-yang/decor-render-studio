from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..models import User
from ..services.furnishing_presets import grouped_presets
from ..services.prompt_service import check_domain, translate_prompt
from .deps import get_current_user

router = APIRouter(prefix="/api/prompt", tags=["prompt"])


class TranslateIn(BaseModel):
    text: str


@router.post("/translate")
async def translate(body: TranslateIn, user: User = Depends(get_current_user)):
    return await translate_prompt(body.text)


@router.post("/check")
def check(body: TranslateIn, user: User = Depends(get_current_user)):
    return {"violations": check_domain(body.text)}


@router.get("/presets")
def presets(user: User = Depends(get_current_user)):
    """软装快速替换预设库（按类别分组）。"""
    return grouped_presets()
