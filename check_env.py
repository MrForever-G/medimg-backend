from dotenv import load_dotenv
import os

load_dotenv()

print("JWT_SECRET:", os.getenv("JWT_SECRET"))
print("DB_URL:", os.getenv("DB_URL"))
print("STORAGE_ROOT:", os.getenv("STORAGE_ROOT"))
