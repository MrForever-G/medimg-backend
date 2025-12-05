from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User, UserRole
from app.auth import hash_password, verify_password, create_access_token
from app.deps import get_current_user
from app.audit import log_action

router = APIRouter(prefix="/auth", tags=["auth"])


# 输入模型
class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: UserRole = UserRole.researcher  # 课程阶段允许传入；实际部署建议仅管理员可指定


# 输出模型
class RegisterOut(BaseModel):
    id: int
    username: str
    role: UserRole


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: int
    username: str
    role: UserRole


# 注册
@router.post("/register", response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_session), request: Request = None):
    """
    临时开放注册（默认 researcher）。
    用户名唯一；重复返回 409。
    """
    exists = db.query(User).filter(User.username == body.username).first()
    if exists:
        log_action(db, None, "register", request, result="deny", detail="duplicate username")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=body.role,
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        log_action(db, None, "register", request, result="deny", detail="integrity error")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    db.refresh(user)
    log_action(db, user.id, "register", request, result="ok")
    return RegisterOut(id=user.id, username=user.username, role=user.role)


# 登录
@router.post("/login", response_model=TokenOut)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_session),
    request: Request = None
):
    """
    OAuth2 密码流登录（表单入参）：
      - username/password 通过表单提交
      - 成功则签发 JWT（sub=username, role=role.value）
    """
    user = db.query(User).filter(User.username == form.username).first()

    if not user or not verify_password(form.password, user.hashed_password):
        log_action(db, None, "login", request, result="deny", detail="wrong credentials")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    token = create_access_token({"sub": user.username, "role": user.role.value})
    log_action(db, user.id, "login", request, result="ok")
    return TokenOut(access_token=token)


# 用户信息
@router.get("/me", response_model=MeOut)
def me(current: User = Depends(get_current_user)):
    """
    受保护路由：返回当前登录用户。
    """
    return MeOut(id=current.id, username=current.username, role=current.role)
