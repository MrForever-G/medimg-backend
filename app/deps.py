# app/deps.py

from typing import Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User, UserRole
from app.auth import decode_access_token

# 使用 HTTP Bearer
security = HTTPBearer()

def get_current_user(
    cred=Depends(security),
    db: Session = Depends(get_session),
) -> User:
    """
    解析 Bearer Token，返回当前用户。
    """
    token = cred.credentials  # HTTPAuthorizationCredentials
    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
    except Exception:
        username = None

    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def require_role(*roles: UserRole) -> Callable[[User], User]:
    """
    角色检查依赖：只接受 UserRole 枚举，避免字符串拼写错误。
    """
    allowed = set(roles)

    def _checker(current: User = Depends(get_current_user)) -> User:
        if allowed and current.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return current

    return _checker
