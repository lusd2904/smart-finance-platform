# 部署指南

默认生产栈是 **MySQL + Redis + InfluxDB + FastAPI + Vue3 Nginx**，编排文件为 `docker-compose.sentiment.yml`。

完整 OpenAPI：启动后端后访问 `http://127.0.0.1:19099/docs`（Docker 反代路径为 `/docker-api/docs`）。

## 1. 环境变量

```bash
cp ruoyi-fastapi-backend/.env.dockersentiment.example ruoyi-fastapi-backend/.env.dockersentiment
cp ruoyi-fastapi-frontend/.env.docker.example ruoyi-fastapi-frontend/.env.docker
```

至少修改：

- `JWT_SECRET_KEY`
- MySQL 密码（与 compose 中一致）
- 默认 `admin / admin123`

可选：长桥凭证、AI Base URL / API Key。

## 2. 启动业务栈

```bash
docker compose -f docker-compose.sentiment.yml up -d --build
```

| 服务 | 端口 |
|------|------|
| 前端 | http://127.0.0.1:12580 |
| 后端 | http://127.0.0.1:19099 |
| MySQL | 13306 |
| Redis | 16379 |
| InfluxDB | 18086 |

已有库需要执行增量 SQL：

```bash
docker exec -i sentiment-mysql mysql -uroot -pCHANGE_ME_DB_PASSWORD sentiment-ai \
  < ruoyi-fastapi-backend/sql/web-polish.sql
```

空库还需按 README 导入 `sql/` 下的菜单脚本。

## 3. 监控（可选）

```bash
docker compose -f docker-compose.monitor.yml up -d
```

- Prometheus：http://127.0.0.1:19090
- Grafana：http://127.0.0.1:13000（默认 admin / admin，请改密码）
- 后端指标：`GET /metrics`

## 4. PostgreSQL（可选，不是默认栈）

`docker-compose.pg.yml` 与 `ruoyi-fastapi-backend/sql/ruoyi-fastapi-pg.sql` 已提供。  
当前推荐生产仍用 MySQL；切换 Postgres 需要独立评估数据迁移，不要直接替换正在跑的 sentiment 栈。

## 5. 桌面端

```bash
cd desktop
npm install
npm start          # 开发：每次先配网关
npm run dist:mac   # 安装包同样先配网关
```

网关填前端入口（本机 Docker 为 `http://127.0.0.1:12580`），不要填后端 `19099`。

## 6. 回归

```bash
npm install
npx playwright install chromium
npm run e2e:web
```

后端单测在 `sentiment-backend` 容器内运行 `python -m pytest tests/ -q`。

## 7. 上线检查

1. 改默认密码与 JWT。
2. AI 模型管理填写真实模型。
3. 长桥配置填写凭证。
4. 任务管理启用自选小时分析、行情同步、因子日扫（长任务会进 Redis 队列，队列不可用则同步执行）。
5. 合并功能分支 PR，不要直接推 `main`。
