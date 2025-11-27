from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

# 密码哈希（bcrypt）
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(payload: Dict[str, Any], expires_minutes: Optional[int] = None) -> str:
    """
    生成 JWT：
      - sub: 建议放 username
      - role: 可选，给前端展示；服务端权限仍以数据库为准
      - iat/exp: 签发/过期
    """
    now = datetime.utcnow()
    expire = now + timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {**payload, "iat": now, "exp": expire}
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    校验并解析 JWT；异常交给上层转换成 401。
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
