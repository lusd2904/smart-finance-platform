# 部署指南

默认生产栈是 **MySQL + Redis + InfluxDB + FastAPI + Vue3 Nginx**，编排文件为 `docker-compose.sentiment.yml`。

完整 OpenAPI：启动后端后访问 `http://127.0.0.1:19099/docs`（Docker 反代路径为 `/docker-api/docs`）。

云上日常更新看下面 **「云主机怎么部署」**。本机资源更大，和云机共用同一份 compose，**不要按云主机内存去砍容器上限**。

---

## 云主机怎么部署（日常更新）

适用：**一台 Docker 云主机，里面是本平台 + grok2api**。不要改 grok2api，不要 `compose down`，不要删 Influx 命名卷。

### 这次上线会改什么

拉 `main` 并滚动**业务容器**之后生效：

- 下单走你配置的长桥账户（模拟就是模拟、真实就是真实）；自动交易开关打开才会委托
- 美股盘前 / 盘后 / 夜盘下单（长桥模拟账户本身仍只撮合常规盘）
- 操作日志只由 `sentiment-backend` 消费，其它 API 不再抢 Redis 日志流
- K 线 / 指标 / 历史在 Influx 侧 `tail`，不再默认拉两年再截断

**不要**为了「给 16G 封顶」去重建 MySQL / Influx / Redis。数据层保持不动。

### 步骤

在云主机仓库根目录（有 `docker-compose.sentiment.yml` 的那层）：

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
```

可选：关闭容器内文件日志（Docker 已有 stdout）。编辑已挂载的 `ruoyi-fastapi-backend/.env.dockersentiment`：

```ini
LOG_FILE_ENABLED = false
```

未改过就保持原样，不影响这次功能。

只重建业务容器（先 API / jobs，再前端）：

```bash
docker compose -f docker-compose.sentiment.yml up -d --no-deps --build \
  sentiment-backend sentiment-trade sentiment-ai sentiment-news \
  sentiment-market sentiment-quant \
  sentiment-jobs sentiment-jobs-market sentiment-jobs-quant sentiment-jobs-llm

docker compose -f docker-compose.sentiment.yml up -d --no-deps --build sentiment-frontend
```

或直接：

```bash
bash scripts/deploy_and_verify.sh
```

脚本同样**不碰** MySQL / Redis / Influx。

### 验收

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
curl -sf http://127.0.0.1:19099/health && echo
curl -sf http://127.0.0.1:12580/ -o /dev/null -w '%{http_code}\n'
```

- `sentiment-backend` / `sentiment-trade` / `sentiment-frontend` 应为 healthy
- `jobs-market` / `jobs-quant` / `jobs-llm` 重建后应出现 `(healthy)`
- 登录页能开；行情/量化在 Influx 未就绪时可能 502，等 `sentiment-influxdb` healthy 即可
- 浏览器强刷一次前端静态资源

### 不要做

| 不要 | 原因 |
|------|------|
| `docker compose down` | 会停整栈；Influx 冷启动可到 10 分钟 |
| `down -v` 或删 `sentiment-influxdb-data` | 行情时序没了 |
| 把 mysql / redis / influx 和业务绑一次 `up --build` | 数据层被顺带重建 |
| 改 grok2api | 独立服务，本次无关 |
| 开 `docker-compose.monitor.yml` | 可选监控，云上不必为部署打开 |

Redis 只有在仍是 `redis:latest`、且还没有 `sentiment-redis-data` 时，才单独 `up ruoyi-redis`。第一次挂新卷会清空登录态，用户要重新登录。不需要就别动。

日常备份（本机/云机均可，产物不要进 git）：

```bash
bash scripts/backup_data.sh
# 或 BACKUP_DIR=/var/backups/sfp bash scripts/backup_data.sh
```

生产用 compose 服务 `sfp-backup`（容器 `sentiment-backup`）：启动立刻跑 `scripts/backup_loop.sh`，随后每 86400 秒再备份。不要 `compose down`。容器内设 `SKIP_CD=1`，脚本不 `cd` 仓库根。

```bash
docker compose -f docker-compose.sentiment.yml up -d --no-deps sfp-backup
```

### 备份（必做，Influx 卷没有副本）

数据在本机 Docker 卷里：`ruoyi-mysql-data`、`sentiment-redis-data`、`sentiment-influxdb-data`。**没有定时备份就会在磁盘故障时丢掉行情历史。** 备份产物不要放进 git。不要另写 mysqldump / `influx backup` 流程，一律：

```bash
bash scripts/backup_data.sh
```

自动循环即上面的 `sfp-backup`。恢复前停业务容器、不要 `compose down -v`。Redis 512mb + `noeviction` 写满会拒绝写入（会话/任务票失败），监控内存水位，不要改成 `volatile-lru` 除非接受踢会话。

更细的队列 / Influx / 客户端行为见下面 [§2.1](#21-本次改动注意事项队列--influx--redis--客户端)。

---

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
- 量化读写已走 `market_watchlist`，旧表 `quant_watchlist` 保留只读历史（不 DROP）。

## 2.1 本次改动注意事项（队列 / Influx / Redis / 客户端）

合并 PR #31、#32 后滚动业务容器即可生效。下面这些行为会和旧栈不一样，上线前先过一遍。

### 禁止事项

- **禁止 `docker compose down` 整栈。** 命名卷 `sentiment-influxdb-data` 不能删、不能 `-v`。
- **不要**把 `ruoyi-redis` / `sentiment-influxdb` / `ruoyi-mysql` 和业务容器绑在一次 `up --build` 里「顺便重建」。数据层单独决策。
- 自动交易扫描只入 `quant` 队列；是否真下单仍看该账户 `auto_trade_enabled`。平台不再做纸账户拦截，委托直接进配置的长桥账户（模拟或真实由凭据决定）。

推荐滚动（先 API，再前端；脚本 `scripts/deploy_and_verify.sh` 已按这个顺序）：

```bash
docker compose -f docker-compose.sentiment.yml up -d --no-deps --build \
  sentiment-backend sentiment-trade sentiment-ai sentiment-news \
  sentiment-market sentiment-quant \
  sentiment-jobs sentiment-jobs-market sentiment-jobs-quant sentiment-jobs-llm
docker compose -f docker-compose.sentiment.yml up -d --no-deps --build sentiment-frontend
```

`market` / `quant` / `jobs-market` / `jobs-quant` 会等 Influx `healthy`。Influx 冷启动可达 10 分钟，期间这四个起不来是预期，**登录 API 不应跟着挂**。

### Influx 与登录

- `sentiment-backend`（登录/系统）、`trade`、`news`、`ai`、`jobs`、`jobs-llm` **不再** `depends_on` Influx healthy。
- 前端也不再等 `market`/`quant`。Influx 未就绪时：登录页可以开，行情/量化接口可能 502 或业务码 500。
- 旧容器的 `depends_on` 只在**创建时**生效；正在跑的栈要按上面 `--no-deps` 重建业务容器后，新依赖才算数。

### Redis（要单独重建才换镜像/策略）

compose 现为 `redis:7-alpine`，AOF、`maxmemory 512mb`、`maxmemory-policy noeviction`、卷 `sentiment-redis-data`。

- **正在跑的** `sentiment-redis` 若仍是 `redis:latest`、无数据卷，则上述配置**尚未生效**。需要时才：

  ```bash
  docker compose -f docker-compose.sentiment.yml up -d ruoyi-redis
  ```

- 第一次挂上新卷会是**空库**：会话、验证码、任务队列、ticket 全没。MySQL / Influx **不受影响**。重建后用户需重新登录；排队中的 Grok/采集任务会丢，可在任务中心再跑一次。
- `noeviction`：内存到 512mb 后 **写入失败**，而不是踢掉 JWT / ticket。看到 Redis OOM 或 `OOM command not allowed` 时加内存或清缓存，不要改回 `volatile-lru`（会先淘汰带 TTL 的登录态和 job ticket）。

### 队列与 HTTP

- 单标的研判、批量研判、自选分析、收盘复盘、选股、热度采集：**HTTP 只入队并立即返回 ticket**（`accepted` / `jobId` / `status`）。前端轮询 `GET /market/jobs/{jobId}`。
- ticket 状态：`queued` → `running` → 失败且还会重试时为 **`retrying`** → 成功 `done` / 进死信才 `failed`。前端只把 `done`/`failed` 当终态。
- **SSE** `GET /market/ai/analyze/stream` 仍在市场 API 进程里跑 Grok，会占 worker。
- 调度入队失败**不再在 scheduler 里内联**重任务。Redis 短暂不可用时，这一轮 cron 会跳过。收盘 K 线、开盘送单、自动交易扫描这类一天一次/开盘窗口任务，入队失败不会补跑，需要任务中心手动再执行，或等下一周期。
- HTTP「自选分析全部」只分析**当前登录用户**的启用自选。全站小时任务仍是 scheduler 的 `watchlist_analyze`（无 `userId`）。
- `APP_ROLE=api|scheduler|worker` 启动时**跳过** `metadata.create_all`。新库靠 compose 初始化 SQL + `scripts/sql_migrate.py`。只 `compose up`、不跑迁移时，登录可能通，热度/选股/复盘等表会缺。`APP_ROLE=all` 的本地单体仍会 `create_all`。

### 客户端

- Web：后台标签页会停报价轮询；需求沟通只在有 `jobId` 时轮询。自选 overview 有约 10s Redis 缓存，刚分析完若列表未变，等一轮或手动刷新。
- nginx `/docker-api/trade/ai/` 读超时 180s（必须写在通用 `/trade/` 30s 之前）。批量研判已入队，一般秒回。
- Flutter **Debug**：默认 `http://127.0.0.1:12580`，Android 模拟器 `http://10.0.2.2:12580`，已存的模拟器地址**保留**。真机 Debug 请在网关页改成局域网 IP，不要用 `10.0.2.2`。
- Flutter **Release**：默认 `https://sfp.luapi.top`；若还存着 `10.0.2.2`/`10.0.3.2` 会改回线上（避免调试残留带到生产包）。
- 指数 WS 默认间隔 15s（对齐指数 30s 缓存）。客户端传 `interval=5` 仍允许，但会反复打同一份缓存。

### 美股盘前 / 盘后 / 夜盘

长桥实盘支持美股延长时段，本仓库下单现已打开：

| 时段 | 美东时间 | `outside_rth` |
|------|----------|----------------|
| 盘前 | 周一至周五 04:00–09:30 | `AnyTime` |
| 盘中 | 周一至周五 09:30–16:00 | `AnyTime`（常规盘成交，未成交可进盘后） |
| 盘后 | 周一至周五 16:00–20:00 | `AnyTime` |
| 夜盘 | 周日～周四 20:00–次日 03:50 | `Overnight` |

- 港股 / A 股不传 `outside_rth`。
- **长桥模拟账户**：官方不撮合美股盘前、盘后、夜盘，只在常规盘模拟成交。延长时段下单可能被拒或挂着不成交，这是券商限制，平台不再另套纸账户层。
- 夜盘行情依赖 SDK `enable_overnight=True`（代码已写死，不必再配 `LONGPORT_ENABLE_OVERNIGHT`）。
- 滚动 `sentiment-trade`（以及会下单的 `sentiment-quant` / `jobs-quant`）后生效。不要 `compose down`。

### jobs worker 健康检查

`jobs-market` / `jobs-quant` / `jobs-llm` 的 `/health` 写在 compose 里，**只对重建后的容器生效**。`docker ps` 里这三项没有 `(healthy)` 时，用上面的 `--no-deps` 重建三个 worker（不要 down 整栈）。

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

登录后（Web 会话 JWT）：

```bash
curl -s -H "Authorization: Bearer <token>" http://127.0.0.1:19099/ai/req/items/export
```

脚本 / 外部拉取先用用户名密码换短期令牌（60 分钟，不再使用固定 `REQUIREMENTS_EXPORT_TOKEN`）。**密码必须 RSA-OAEP + AES-256-GCM 信封**，与 `/open/sync/token` 相同；明文 POST 会被拒绝。实现见 `scripts/sync_from_prod.py` 的 `encrypted_json`：

```python
key = load_public_key('https://sfp.luapi.top/prod-api')
data = encrypted_json(
    'https://sfp.luapi.top/prod-api',
    '/open/token',
    {'username': 'admin', 'password': '<密码>'},
    key,
)
token = data['token']
```

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://sfp.luapi.top/prod-api/open/requirements?status=pending"
```

「总结并写入清单」和群聊发送都只入 Redis `llm` 队列并立即返回 `jobId`，由 `sentiment-jobs-llm` 调 Grok。测完在「AI 需求清单」手动改状态。

## 8. 上线检查

1. 改默认密码与 JWT。
2. AI 模型管理填写真实模型。
3. 长桥配置填写凭证。
4. 确认 `sentiment-jobs` 健康（`/health`），再在「任务中心 / 自动分析任务」启用自选小时分析、行情同步、因子日扫。长任务进 Redis 分队列，由对应消费组执行，不会打到 API 进程。
5. 合并功能分支 PR，不要直接推 `main`。
6. 云上日常更新按文首「云主机怎么部署」滚业务容器。过一遍 [§2.1 注意事项](#21-本次改动注意事项队列--influx--redis--客户端)：Influx 未就绪时只保证登录；Redis 重建会丢会话；研判看 ticket 不要等同步返回。
7. Widget / 需求清单换令牌必须走传输层信封（与 `/open/sync/token` 相同）；重建 `sentiment-news` / `sentiment-ai` 后 `.env.dockersentiment` 的 `TRANSPORT_CRYPTO_REQUIRED_PATHS` 才包含新路径。
