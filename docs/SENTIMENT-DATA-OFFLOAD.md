# sentiment-data 热路径 offload（P3）

目标：让门户 / 行情 WS 不再绑在 fat Python `sentiment-data`（典型 RSS ~424Mi）上。  
**不删** `sentiment-data`。回退只改 nginx upstream，不改前端契约。

对外 URL、JWT、WS 帧格式与 PR #75 之前相同。

---

## Before / after（slim nginx）

| 路径 | Before（#75 后） | After（本 PR） | 进程 |
|------|------------------|----------------|------|
| `GET /market/kline` | Go | Go | `sentiment-market-read` |
| `GET /market/board/quotes` | Go | Go | 同上 |
| `GET /market/heat/{daily,trend,dates,config}` | Go | Go | 同上 |
| `GET /market/index/quotes` | Go **只读 Redis**（Python WS 当 writer） | Go **Tencent 拉取 + Redis 30s** | 同上 |
| `GET /market/symbols/*/history` | Go | Go | 同上 |
| `GET /market/quotes/live` | Python | Go（Tencent + Redis 5s） | 同上 |
| `WS /ws/market/quotes` | Python `QuoteSubscribeHub` + 长桥 | Go（指数/个股 Tencent，协议不变） | 同上 |
| 其余 `/market/` | Python | Python | `sentiment-data` |
| `/quant/` | Python | Python | `sentiment-data` |
| `WS /ws/jobs` | platform | platform | `sentiment-backend` |
| 其它 `/ws/` | Python | Python catch-all | `sentiment-data` |

`sentiment-data` 仍必须保留：量化 HTTP、行情写/入队、AI SSE、自选 CRUD、长桥测试/开仓。

---

## 预期 RSS

| 容器 | Before | After（预期） | 说明 |
|------|--------|---------------|------|
| `sentiment-data` | ~424Mi / `mem_limit` 512m | **仍可能 350–424Mi** | FastAPI + pandas + longport **仍会 import**（quant / 回退路径）。热连接离开后可在 cursor-1 **实测再降** `mem_limit` 512→384 |
| `sentiment-market-read` | ~数十–百余 Mi / 256m | **+WS 后预算 320m** | 多连接 + 腾讯 HTTP；无 pandas |
| 整栈 | — | **净减主要来自 WS 不再钉住 Python** | 不要指望本 PR 单独把 data 砍到 200Mi |

本 PR **不**从 Python 卸 `longport` / pandas（P1 交易、P2 量化因子仍要用）。

---

## 回退（nginx upstream）

只改前端容器挂载的 conf，reload，**不要** `compose down`。

**Slim**（`nginx.dockersentiment.slim.conf`）：

```nginx
# 把这两条改回 Python
location /prod-api/ws/market/quotes {
    proxy_pass http://sentiment-data:9099/ws/market/quotes;
    # … Upgrade 头保持
}
location /prod-api/market/quotes/live {
    proxy_pass http://sentiment-data:9099/market/quotes/live;
}
```

`/docker-api/` 对称改。`/ws/` catch-all 本来就指向 `sentiment-data`。

**Full** 回退目标是 `sentiment-market:9099`（不是 data）。

```bash
# 改 conf 后
sudo docker compose -f docker-compose.sentiment.yml -f docker-compose.sentiment.slim.yml \
  up -d --no-deps --build sentiment-frontend
```

Python handler **保留**（`# DEPRECATED(ws-offload|read-offload)`），回退后契约仍在。

---

## 仍必须留在 Python 的路由

### 等到 P1（Longbridge 交易）之后才能动

| 路径 | 原因 |
|------|------|
| `POST /quant/daily-list/open` | 长桥下单 |
| `POST /quant/scan/positions` | 长桥持仓 + 可能触发卖出 |
| `GET /quant/longbridge/test` | SDK 连通 |
| `GET /quant/readmodel/overview` | 含长桥余额 |
| `PUT /quant/longbridge/config` | 凭据写入（可后迁，但别和 P1 抢） |
| 行情 WS 的 **长桥推送提前唤醒** | Go 网关用腾讯间隔推送；长桥 `QuoteContext` 仍在 Python 回退路径 |

P1 主包（`module_trade` / `sentiment-trade`）本 PR **未改**。

### 等到 P2（quant native job）之后才能动

| 路径 | 原因 |
|------|------|
| `GET /quant/factor/compute` | 进程内 pandas/numpy |
| `POST /quant/scan/indicators` | Influx 批量 + 写库 |
| 全部 `POST /quant/*/run|scan` 入队 | **薄代理**，队列契约属 P2 worker。本 PR **不**迁这些 HTTP，避免抢 job runner |
| `GET /quant/factor/snapshots*` / `qc` / `strategy/history` / `scan-runs` / `daily-list` | 读模型与 P2 表结构绑定 |

`sfp-quant-worker` **未改**。

### 等到 P4 / 现有 worker 即可（本 PR 不迁）

薄 `JobQueue.submit` 仍走 Python，避免另写一套 ticket：

- `POST /market/sync`、`/sync/mysql-to-influx`
- `POST /market/heat/collect`、`/picks/run`、`/picks/mood/refresh`
- `POST /market/ai/analyze`、`/symbols/{s}/ai-analyze`
- `POST /market/watchlist/analyze`、`/review/analyze`
- `GET /market/jobs/{job_id}`

### 本 PR 有意留下的行情读（非热路径）

复杂度 / 外部源 / 写路径，下一轮再迁 Go：

- TradingView datafeed（`/market/tradingview/*`）
- `GET /market/instrument/{list,universe}`
- `GET /market/picks/*`（读）
- `GET /market/indicators`（pandas）
- `GET /market/symbols/{s}/{overview,content,ai/latest}`
- `GET /market/finance/briefings`、`/flow/board`
- 自选 CRUD + overview / analysis / backtest / correlation
- `GET /market/review/{latest,history}`
- `GET /market/ai/analyze/stream`（SSE + LLM）

---

## 渐进切流

1. 本 PR 合并后：cursor-1 `deploy_and_verify_slim.sh`（**Coordinator 主机测**，Agent 不 merge）。
2. 浏览器：登录 → 顶栏指数条 LIVE → 自选 / 热度 / K 线订阅个股 → 手机 `/m`。
3. 确认 `docker stats sentiment-market-read` 远低于 320m；`sentiment-data` 连接数下降。
4. 若 WS 异常：按上文把 `/ws/market/quotes` 指回 Python，reload 前端。
5. 实测 data RSS 稳定后再考虑 512→384（**单独 PR**）。

---

## 与并行 PR 的边界

| 包 | 本 PR | 留给谁 |
|----|-------|--------|
| `services/market-read` | 扩展 WS / live / index 刷新 | P3 |
| `ruoyi-fastapi-frontend/bin/nginx*.conf` | 加 location | P3 |
| `workers/quant-worker` | **不改** | P2 |
| `module_trade` / Longbridge 下单 | **不改** | P1 |
| `sentiment-jobs` / scheduler | **不改** | P4 |
| grok2api / 公开 cutover / volume | **不碰** | — |
