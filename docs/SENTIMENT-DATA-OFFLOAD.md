# sentiment-data 热路径 offload（P3 finish）

目标：门户 + 行情 WS 在**默认 slim 栈**上不再依赖 fat Python `sentiment-data`（典型 RSS ~424Mi）。  
Python `sentiment-data` 与 `--profile legacy-python` overlay **已从 main 删除**（[PYTHON-REMOVED.md](./PYTHON-REMOVED.md)）。

---

## 路由归属（slim nginx，2026-09）

| 路径 | 默认 upstream | 进程 |
|------|---------------|------|
| 热读 + 指数条 + live quotes | `sentiment-market-read:8080` | Go |
| `WS /ws/market/quotes` | 同上 | Go |
| 其余 `/market/` + 全部 `/quant/` | `sentiment-data-api:8081` | Go |
| `WS /ws/jobs` | `sfp-backend:9099` | Go platform |
| `/sentiment/`、`/ai/`、`/open/` | `sfp-intel:8080` | Go |
| `/trade/*` | `sentiment-trade-api:8080` | Go |

**默认不启动** Python fat 容器（`sentiment-data` / `sentiment-backend` / `sentiment-intel` / `sentiment-trade`）。11 条原 legacy 路由已在 `sentiment-data-api` 原生实现（Go 指标 / 因子、openapi-go 长桥）。

`legacy-python` profile **仅作紧急回退**，不是生产路径：

```bash
# 紧急回退示例（不推荐常态使用）
docker compose -f docker-compose.sentiment.yml -f docker-compose.sentiment.slim.yml \
  --profile legacy-python up -d --build sentiment-data sentiment-frontend
# 并将 nginx catch-all 改回 sentiment-data:9099（不要提交进 slim conf）
```

---

## Go data-api 原生路由（原 11 条 legacy）

| 路径 | 实现 |
|------|------|
| `GET /market/indicators` | Go 指标序列（`internal/indicators`） |
| `GET /market/ai/analyze/stream` | 入队 `ai_analyze` + SSE 回读 `symbol_ai_analysis` |
| `GET /market/symbols/{s}/content` | openapi-go 长桥资讯 + MySQL 缓存 |
| `GET /quant/factor/compute` | Go 因子引擎（`internal/factor`，与 quant-worker 同源） |
| `POST /quant/scan/indicators` | 读模型 board 快照刷新 |
| `POST /quant/scan/positions` | openapi-go 持仓 + 止损监控 |
| `GET/PUT /quant/longbridge/config` | MySQL CRUD + Fernet 加解密 |
| `GET /quant/longbridge/test` | openapi-go 连通性 |
| `POST /quant/daily-list/open` | 长桥下单 + 清单状态 |
| `POST /quant/daily-list/auto` | 清单自动交易开关 |

---

## Compose 服务名

MySQL compose 服务键为 **`sentiment-mysql`**（容器名同）。`DB_HOST=sentiment-mysql`。

---

## 预期 RSS

| 容器 | Before（P3 前） | After（默认 slim） | 说明 |
|------|-----------------|-------------------|------|
| `sentiment-data` | ~424Mi / 512m | **0**（未启动） | `--profile legacy-python` 紧急回退 |
| `sentiment-market-read` | ~数十–320m | ~320m | 热读 + WS |
| `sentiment-data-api` | — | **~80–180m / 256m** | MySQL + Redis + 短 HTTP |
| 整栈净减 | — | **~250–400Mi** | 主要来自去掉默认 data 容器 |

---

## 回退

### A. 全量回退 Python（紧急）

1. `--profile legacy-python` 启动 `sentiment-data`。
2. 改 `nginx.dockersentiment.slim.conf`：`/market/`、`/quant/` → `http://sentiment-data:9099/...`。
3. `docker compose ... up -d --no-deps --build sentiment-frontend`。

### B. Full 栈

`nginx.dockersentiment.conf` catch-all 指向 `sentiment-data-api:8081`。

---

## Influx Phase A（无 MySQL）

Phase A **只起 Redis + Influx**，不再启动 Python `sentiment-data`。热度/K 线读等 Phase B（Go `market-read` / `data-api`，需 MySQL）。

---

## 验证

```bash
bash scripts/deploy_and_verify_slim.sh
docker stats --no-stream sentiment-data-api sentiment-market-read
curl -sf http://127.0.0.1:8081/health  # 在 data-api 容器内
```
