# app/main.py

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db


# 路由模块
from app.routers import health_router, auth_router, datasets_router, samples_router, annotations_router, approvals_router

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
)

# CORS 设置：允许前端访问后端 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(samples_router.router)
app.include_router(annotations_router.router)
app.include_router(approvals_router.router)
