
.env设计：
JWT_SECRET=change-this-in-prod
JWT_ALG=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
DB_URL=sqlite:///./medimg.db
STORAGE_ROOT=./storage
原理：
JWT_SECRET：后端签发/校验登录令牌（JWT）的密钥。放在环境变量里而不是代码里，防止泄露、方便换环境（本地/服务器）时更改。上线前必须换成足够随机的长字符串。

JWT_ALG=HS256：JWT 的签名算法。把算法固定下来，避免代码里“写死+到处改”，也防止在不同环境里不一致。

ACCESS_TOKEN_EXPIRE_MINUTES=480：令牌有效期（分钟）。调参不改代码，方便课堂演示/实际部署时快速调整安全策略。

DB_URL=…：数据库连接串。把“用什么库、在哪儿、怎么连”交给配置，便于从 SQLite 切换到 MySQL（你现在就要 MySQL，也只改这里）。

STORAGE_ROOT=./storage：你要把图片/切片临时存哪儿（本地磁盘）。后面如果改成 MinIO/S3，也只要改存储适配和这个路径/桶配置。

目的：可移植、可配置、避免把敏感信息写进仓库。课程验收时，老师看代码不会看到你真实密码/密钥；换台电脑只要改 .env 就能跑。
