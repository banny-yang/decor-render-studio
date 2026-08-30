from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Task, User
from ..schemas import (LoginIn, TokenOut, UserCreateIn, UserOut, UserUpdateIn)
from ..security import hash_password, verify_password
from .deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    return user


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    from ..security import create_token
    return {"token": create_token(user.id), "user": UserOut.model_validate(user)}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# ---------- 用户管理（仅管理员，多用户系统） ----------
@router.get("/users", response_model=list[UserOut])
def list_users(admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post("/users", response_model=UserOut)
def create_user(body: UserCreateIn, admin: User = Depends(_require_admin),
                db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(400, f"用户名已存在：{body.username}")
    u = User(username=body.username, password_hash=hash_password(body.password),
             display_name=body.display_name or body.username, is_admin=body.is_admin)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdateIn,
                admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "用户不存在")
    if body.password:
        u.password_hash = hash_password(body.password)
    if body.display_name is not None:
        u.display_name = body.display_name
    if body.is_admin is not None:
        if body.is_admin is False and u.id == admin.id:
            raise HTTPException(400, "不能取消自己的管理员权限")
        u.is_admin = body.is_admin
    db.commit()
    db.refresh(u)
    return u


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(_require_admin),
                db: Session = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(400, "不能删除自己")
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "用户不存在")
    running = db.scalar(select(Task.id).where(Task.user_id == user_id,
                                              Task.status.in_(("pending", "queued", "running"))))
    if running:
        raise HTTPException(400, "该用户有排队/执行中的任务，请先处理后再删除")
    u.is_admin = False
    db.query(Task).filter(Task.user_id == user_id).update({"user_id": None},
                                                          synchronize_session=False)
    db.delete(u)
    db.commit()
    return {"ok": True}
