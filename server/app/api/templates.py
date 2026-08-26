from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import StyleTemplate, User
from ..schemas import TemplateIn, TemplateOut
from .deps import get_current_user

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
def list_templates(category: str | None = None, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    q = select(StyleTemplate).order_by(StyleTemplate.id)
    if category:
        q = q.where(StyleTemplate.category == category)
    return db.scalars(q).all()


@router.post("", response_model=TemplateOut)
def create(body: TemplateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.scalar(select(StyleTemplate).where(StyleTemplate.name == body.name)):
        raise HTTPException(400, "同名模板已存在")
    t = StyleTemplate(**body.model_dump(), is_builtin=False)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.put("/{template_id}", response_model=TemplateOut)
def update(template_id: int, body: TemplateIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    t = db.get(StyleTemplate, template_id)
    if t is None:
        raise HTTPException(404, "模板不存在")
    for k, v in body.model_dump().items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{template_id}")
def delete(template_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.get(StyleTemplate, template_id)
    if t is None:
        raise HTTPException(404, "模板不存在")
    if t.is_builtin:
        raise HTTPException(400, "内置模板不可删除，可编辑")
    db.delete(t)
    db.commit()
    return {"ok": True}
