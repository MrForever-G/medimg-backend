# 数据库连接与会话管理
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings

if not settings.DB_URL:
    raise RuntimeError("Missing DB_URL in .env")

# 创建全局 Engine
engine = create_engine(settings.DB_URL, pool_pre_ping=True, echo=settings.DEBUG)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db() -> None:
    # 启动时验证连接并尝试自动建表
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    try:
        from app.models import Base
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass  # 无模型时跳过

def get_session():
    # FastAPI 依赖：单次请求独立 Session
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
