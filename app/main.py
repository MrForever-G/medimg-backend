# 应用入口：创建实例、初始化、注册路由
import os
from fastapi import FastAPI
from app.config import settings
from app.db import init_db
from app.routers import health_router

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

@app.on_event("startup")
def on_startup():
    os.makedirs(settings.STORAGE_ROOT, exist_ok=True)  # 确保存储目录存在
    init_db()  # 初始化数据库

app.include_router(health_router.router)
