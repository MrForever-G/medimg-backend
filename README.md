本项目为 软件工程课程设计 医学图像管理系统 后端设计
前端设计可访问： https://github.com/MrForever-G/medimg-frontend
版权归本人所有

````md
# MedImg Backend

MedImg 医学图像管理系统后端服务（FastAPI + MySQL）。

本 README 说明：数据库部署、本地运行、常见问题。

---

## 环境要求

- Python 3.10+（建议 3.11）
- MySQL 8.0+
- Windows / macOS / Linux 均可

---

## 1. 获取代码

```bash
git clone https://github.com/MrForever-G/medimg-backend.git
cd medimg-backend
````

---

## 2. 创建并激活虚拟环境

### Windows（PowerShell）

```bash
python -m venv venv
venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. 安装依赖

如果仓库内存在 `requirements.txt`：

```bash
pip install -U pip
pip install -r requirements.txt
```

如果你使用 Poetry（存在 `pyproject.toml`）：

```bash
poetry install
```

---

## 4. 数据库部署（MySQL）

### 4.1 创建数据库与用户

在 MySQL 控制台执行：

```sql
CREATE DATABASE medimg CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'medimg_user'@'localhost' IDENTIFIED BY 'StrongPass!123';
GRANT ALL PRIVILEGES ON medimg.* TO 'medimg_user'@'localhost';
FLUSH PRIVILEGES;
```

说明：

* 若后端不从 `localhost` 连接 MySQL（Docker / WSL / 远程部署），把 `'localhost'` 改为 `'%'` 或指定来源 IP。

---

## 5. 配置运行参数（.env）

本项目启动会加载 `.env`，并且 `DB_URL` 为必填项。

在项目根目录创建 `.env`：

```env
APP_NAME=MedImg Label & Access Control
DEBUG=false

DB_URL=mysql+pymysql://medimg_user:StrongPass!123@127.0.0.1:3306/medimg?charset=utf8mb4

JWT_SECRET=dev-secret
JWT_ALG=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

STORAGE_ROOT=./storage
```

注意：

* `DB_URL` 使用 SQLAlchemy 连接串格式，驱动为 `pymysql`（`mysql+pymysql://...`）。
* 若密码包含 `@`、`:`、`/` 等特殊字符，建议避免或对密码做 URL 编码。

---

## 6. 启动后端

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后：

* Swagger：`http://127.0.0.1:8000/docs`
* Health：`http://127.0.0.1:8000/health`

---

## 7. 常见问题

### 7.1 启动时报 `Missing DB_URL in .env`

* 确保仓库根目录存在 `.env`
* 确保 `.env` 中包含 `DB_URL=...`
* 确保你在仓库根目录执行启动命令

### 7.2 MySQL 连接失败（Access denied / Can't connect）

* 检查 MySQL 是否启动、端口是否正确
* 检查账号密码是否正确
* 检查授权主机是否匹配：`'medimg_user'@'localhost'` 仅允许本机连接

### 7.3 依赖缺失（ModuleNotFoundError）

* 确认虚拟环境已激活
* 重新安装依赖：

  pip install -r requirements.txt

## License and Usage

This project is developed as part of an academic course project.

- The source code is provided **for learning and research purposes only**
- **Direct copying, submission as coursework, or commercial use is prohibited**
- Any derivative work must clearly indicate the original source

© 2025 Forever. All rights reserved.
