medimg-backend/
├─ app/
│  ├─ main.py                # 应用入口：创建 FastAPI 实例、注册路由、初始化数据库/目录
│  ├─ config.py              # 全局配置：JWT 秘钥/算法、数据库URL、token有效期、storage路径等
│  ├─ db.py                  # 数据库初始化与会话管理：engine、建表、Session依赖(get_session)
│  ├─ models.py              # 领域模型(ORM)：User/Dataset/Sample/Annotation/Approval/AuditLog 等
│  ├─ auth.py                # 认证相关：密码哈希/校验、JWT 生成/解析（与 config 绑定）
│  ├─ deps.py                # 依赖注入：获取当前用户、角色检查(require_role)等
│  ├─ audit.py               # 审计封装：统一写入 AuditLog（谁/何时/做了什么/对象/IP/结果）
│  ├─ routers/
│  │   ├─ auth_router.py         # 认证模块：注册/登录，返回 JWT；可额外提供改密/刷新token
│  │   ├─ datasets_router.py     # 数据集：创建/查询；（MVP）可见性=group；记录创建者
│  │   ├─ samples_router.py      # 样本上传：白名单/MIME 校验、SHA256、落盘到 storage、写库
│  │   ├─ annotations_router.py  # 标注：新增/查询；（MVP）状态 submitted，后续加审核流
│  │   ├─ approvals_router.py    # 下载审批：提交申请/管理员审批/过期时间；为下载放行做准备
│  │   └─ health_router.py       # 健康检查：/health 返回 ok，给监控与自检用
├─ storage/                    # 样本物理文件目录（后续可换对象存储，保持路径/适配器一致）
├─ .env                        # （可选）环境变量：JWT_SECRET、DB_URL 等，便于不同环境切换
├─ requirements.txt            # Python 运行依赖（后端MVP所需）
├─ help.md                     # 个人帮助文档
├─ mything.md                  # 记录借助chatgpt和个人的想法
└─ README.md                   # 启动说明、接口约定、目录解释、后续计划

# 环境与启动
conda activate medimg
pip install -r requirements.txt

# 配置
- .env 放在项目根目录
- DB_URL 用 mysql+pymysql://user:pass@host:3306/db?charset=utf8mb4

# MySQL 速记
CREATE DATABASE medimg CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'medimg_user'@'localhost' IDENTIFIED BY 'StrongPass!123';
GRANT ALL PRIVILEGES ON medimg.* TO 'medimg_user'@'localhost';
FLUSH PRIVILEGES;
