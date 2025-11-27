# 读取 .env 配置，集中管理运行参数
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()  # 启动时加载 .env

@dataclass(frozen=True)
class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "MedImg Label & Access Control")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    DB_URL: str = os.getenv("DB_URL", "")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret")
    STORAGE_ROOT: str = os.getenv("STORAGE_ROOT", "./storage")
    JWT_ALG: str = os.getenv("JWT_ALG", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

settings = Settings()
