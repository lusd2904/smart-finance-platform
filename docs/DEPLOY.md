# 部署指南

默认生产栈是 **MySQL + Redis + InfluxDB + FastAPI + Vue3 Nginx**，编排文件为 `docker-compose.sentiment.yml`。

完整 OpenAPI：启动后端后访问 `http://127.0.0.1:19099/docs`（Docker 反代路径为 `/docker-api/docs`）。

## 1. 环境变量

```bash
cp ruoyi-fastapi-backend/.env.dockersentiment.example ruoyi-fastapi-backend/.env.dockersentiment
cp ruoyi-fastapi-frontend/.env.docker.example ruoyi-fastapi-frontend/.env.docker
```

至少修改：

- `JWT_SECRET_KEY`（随机强密钥，泄露即会话可伪造）
- `MYSQL_ROOT_PASSWORD` / `REDIS_PASSWORD` / `INFLUXDB_PASSWORD` / `INFLUXDB_TOKEN` / `GRAFANA_ADMIN_PASSWORD`
- `INITIAL_ADMIN_PASSWORD`：**仅对新库首次初始化生效**；示例值是占位符，切勿直接上生产

> ⚠️ 历史版本曾在示例文件中提交过真实初始密码（已从代码与 git 历史清除）。
> 在此之前部署的环境请立即登录后台修改 admin 密码。

可选：长桥凭证、AI Base URL / API Key。

## 2. 启动业务栈

```bash
docker compose -f docker-compose.sentiment.yml up -d --build
```

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 / 网关 | http://127.0.0.1:12580（对外仍走 sfp.luapi.top） | 容器内非特权 nginx，监听 8080 |
| 平台 API | http://127.0.0.1:19099（仅本机回环） | OpenAPI `/docs`；云上经网关反代访问 |
| jobs 调度 | http://127.0.0.1:19098/health（仅本机回环） | |
| MySQL / Redis / InfluxDB | 不暴露宿主端口 | 业务容器走内网访问；本机调试临时改映射 |

同一套后端镜像，按环境变量拆进程（共享 MySQL / Redis / Influx，不分库）：

- `sentiment-backend`：`APP_ROLE=api`，只提供 HTTP
- `sentiment-trade` / `market` / `quant` / `news` / `ai`：板块 API，交易实时单独低延迟
- `sentiment-jobs`：`APP_ROLE=scheduler APP_JOB_GROUP=none`，只跑 APScheduler
- `sentiment-jobs-market` / `quant` / `llm`：三个队列消费组，一组挂掉不影响另外两组和 API

**禁止 `compose down` 整栈，禁止改 grok2api。** 只加服务：

```bash
docker compose -f docker-compose.sentiment.yml up -d --no-deps --build sentiment-jobs sentiment-jobs-market sentiment-jobs-quant sentiment-jobs-llm sentiment-trade sentiment-market sentiment-quant sentiment-news sentiment-ai sentiment-backend sentiment-frontend
```

### 增量 SQL（schema_version 登记制）

增量 SQL 由 `scripts/sql_migrate.py` 统一管理（版本登记在 `sentiment-ai.schema_version` 表），
`deploy_and_verify.sh` 第 [3/5] 段会自动执行。手动用法：

```bash
python3 scripts/sql_migrate.py apply --dry-run          # 查看待执行计划（不连库）
MYSQL_ROOT_PASSWORD=<密码> python3 scripts/sql_migrate.py apply --keep-going
python3 scripts/sql_migrate.py status                   # 查看已登记/待执行
```

- 新环境：compose 首次挂载初始化全量基线后，迁移器自动预登记同一批基线文件，只补真正的增量。
- 新增增量脚本：放进 `ruoyi-fastapi-backend/sql/*.sql`（kebab-case 命名、幂等可重放），下次 apply 自动消费；
  细节见 `ruoyi-fastapi-backend/sql/README.md`。
- 服务层不再运行时建表：代码依赖的表（如 `market_price_history_daily`）缺失时按日志提示执行迁移即可。

## 3. 监控（可选）

```bash
docker compose -f docker-compose.monitor.yml up -d
```

- Prometheus：http://127.0.0.1:19090（仅本机回环）
- Grafana：http://127.0.0.1:13000（仅本机回环；默认 admin / admin，请改密码）
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

## 7. 需求清单对外接口

登录后：

```bash
curl -s -H "Authorization: Bearer <token>" http://127.0.0.1:19099/ai/req/items/export
```

生产可用 Token（环境变量 `REQUIREMENTS_EXPORT_TOKEN`）：

```bash
curl -s -H "X-Req-Token: $REQUIREMENTS_EXPORT_TOKEN" \
  "https://sfp.luapi.top/prod-api/open/requirements?status=pending"
```

「总结并写入清单」和群聊发送都只入 Redis `llm` 队列并立即返回 `jobId`，由 `sentiment-jobs-llm` 调 Grok。测完在「AI 需求清单」手动改状态。

## 8. 上线检查

1. 改默认密码与 JWT。
2. AI 模型管理填写真实模型。
3. 长桥配置填写凭证。
4. 确认 `sentiment-jobs` 健康（`/health`），再在「任务中心 / 自动分析任务」启用自选小时分析、行情同步、因子日扫。长任务进 Redis 分队列，由对应消费组执行，不会打到 API 进程。
5. 合并功能分支 PR，不要直接推 `main`。
