# app/main.py

import os
from fastapi import FastAPI

from app.config import settings
from app.db import init_db
from app.routers import datasets_router


# 路由模块
from app.routers import health_router, auth_router


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
)


@app.on_event("startup")
def startup() -> None:
    # 初始化存储路径与数据库
    os.makedirs(settings.STORAGE_ROOT, exist_ok=True)
    init_db()


# 路由注册
app.include_router(health_router.router)
app.include_router(auth_router.router)
app.include_router(datasets_router.router)