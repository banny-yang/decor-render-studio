from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import parse_token


async def get_current_user(
    x_auth_token: str | None = Header(default=None),
    token: str | None = Query(default=None),  # 供 EventSource / <img> 使用
    db: Session = Depends(get_db),
) -> User:
    tok = x_auth_token or token
    if not tok:
        raise HTTPException(401, "未登录")
    uid = parse_token(tok)
    if uid is None:
        raise HTTPException(401, "登录已过期，请重新登录")
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(401, "用户不存在")
    return user
