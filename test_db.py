# test_db.py
from sqlmodel import create_engine
from dotenv import load_dotenv
import os

# 1. 载入 .env 文件
load_dotenv()

# 2. 读取数据库连接字符串
db_url = os.getenv("DB_URL")

print(f"[INFO] 正在连接数据库: {db_url}")

# 3. 创建 SQLModel 数据库引擎
try:
    engine = create_engine(db_url, echo=True)
    with engine.connect() as conn:
        result = conn.exec_driver_sql("SELECT 1")
        print("✅ 数据库连接成功！返回结果:", result.scalar_one())
except Exception as e:
    print("❌ 数据库连接失败！错误信息如下：")
    print(e)
