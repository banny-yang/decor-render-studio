from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Project, Task, User
from ..schemas import ProjectIn, ProjectOut
from .deps import get_current_user

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _out(db: Session, p: Project) -> ProjectOut:
    o = ProjectOut.model_validate(p)
    o.task_count = db.scalar(select(func.count(Task.id)).where(Task.project_id == p.id)) or 0
    return o


@router.get("")
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Project).order_by(Project.id.desc())).all()
    return [_out(db, p) for p in items]


@router.post("", response_model=ProjectOut)
def create(body: ProjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = Project(name=body.name, customer=body.customer, description=body.description)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _out(db, p)


@router.put("/{project_id}", response_model=ProjectOut)
def update(project_id: int, body: ProjectIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "项目不存在")
    p.name, p.customer, p.description = body.name, body.customer, body.description
    db.commit()
    return _out(db, p)


@router.delete("/{project_id}")
def delete(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "项目不存在")
    db.delete(p)
    db.commit()
    return {"ok": True}
