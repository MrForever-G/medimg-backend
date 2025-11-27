# 健康检查路由
from fastapi import APIRouter
from sqlalchemy import text
from app.db import engine

router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    # 返回应用与数据库健康状态
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"ok": True, "db": db_ok}
