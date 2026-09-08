# sentiment-data 热路径 offload（P3 finish）

目标：门户 + 行情 WS 在**默认 slim 栈**上不再依赖 fat Python `sentiment-data`（典型 RSS ~424Mi）。  
回退只改 nginx upstream / compose profile，不改前端契约。

---

## 路由归属（slim nginx，2026-09）

| 路径 | 默认 upstream | 进程 |
|------|---------------|------|
| 热读 + 指数条 + live quotes | `sentiment-market-read:8080` | Go |
| `WS /ws/market/quotes` | 同上 | Go |
| 其余 `/market/` + 全部 `/quant/` | `sentiment-data-api:8081` | Go |
| `WS /ws/jobs` | `sentiment-backend:9099` | platform |
| `/sentiment/`、`/ai/`、`/open/` | `sentiment-intel:9099` | Python intel |
| `/trade/*` | `sentiment-trade:9099` | Python trade |

**默认不启动** `sentiment-data`。仅当需要 Longbridge / pandas / SSE 回退时加 profile：

```bash
export LEGACY_DATA_URL=http://sentiment-data:9099
docker compose -f docker-compose.sentiment.yml -f docker-compose.sentiment.slim.yml \
  --profile legacy-data up -d --build sentiment-data sentiment-data-api sentiment-frontend
```

`sentiment-data-api` 会把 11 条 legacy 路由反向代理到 `LEGACY_DATA_URL`；未设置时返回明确错误（提示启用 `--profile legacy-data`）。

---

## 仍留在 Python 的 legacy 路由（11）

| 路径 | 原因 |
|------|------|
| `GET /market/indicators` | pandas 指标序列 |
| `GET /market/ai/analyze/stream` | SSE + LLM |
| `GET /market/symbols/{s}/content` | 长桥资讯缓存/刷新 |
| `GET /quant/factor/compute` | 进程内 pandas/numpy |
| `POST /quant/scan/indicators` | 同步指标快照 |
| `POST /quant/scan/positions` | 长桥持仓监控 |
| `GET/PUT /quant/longbridge/config` | 凭据 CRUD |
| `GET /quant/longbridge/test` | SDK 连通 |
| `POST /quant/daily-list/open` | 长桥下单 |
| `POST /quant/daily-list/auto` | 自动交易开关 |

P1（Longbridge 交易）完成后可再迁 `daily-list/open`、`scan/positions` 等。

---

## 预期 RSS

| 容器 | Before（P3 前） | After（默认 slim） | 说明 |
|------|-----------------|-------------------|------|
| `sentiment-data` | ~424Mi / 512m | **0**（未启动） | `--profile legacy-data` 时仍 ~350–424Mi |
| `sentiment-market-read` | ~数十–320m | ~320m | 热读 + WS |
| `sentiment-data-api` | — | **~80–180m / 256m** | MySQL + Redis + 短 HTTP，无 pandas/longport import |
| 整栈净减 | — | **~250–400Mi** | 主要来自去掉默认 data 容器 |

---

## 回退

### A. 全量回退 Python（slim）

1. 启动 legacy：`--profile legacy-data`，并 `LEGACY_DATA_URL=http://sentiment-data:9099`。
2. 改 `nginx.dockersentiment.slim.conf`：`/market/`、`/quant/` → `http://sentiment-data:9099/...`；热读/WS 改回 `sentiment-data:9099`（见下方片段）。
3. `docker compose ... up -d --no-deps --build sentiment-frontend`。

```nginx
location /prod-api/market/ {
    proxy_pass http://sentiment-data:9099/market/;
}
location /prod-api/quant/ {
    proxy_pass http://sentiment-data:9099/quant/;
}
```

### B. 仅 legacy 子集（推荐）

保持 nginx 指向 `data-api`，只启 `sentiment-data` + `LEGACY_DATA_URL`。门户与 job 入队仍走 Go。

### C. Full 栈

`nginx.dockersentiment.conf` 中 catch-all 已指向 `sentiment-data-api:8081`；拆分 `sentiment-market` / `sentiment-quant` 仅在 `--profile full-split` 下存在，默认不启。

---

## Influx Phase A（无 MySQL）

仍可用 **`--profile influx-phase`** 临时起 Python `sentiment-data` 做 Influx-only 读：

```bash
bash scripts/up_slim_influx_phase.sh
```

全栈登录/舆情/Go API 需 Phase B（`deploy_and_verify_slim.sh`）。

---

## 验证

```bash
bash scripts/deploy_and_verify_slim.sh
docker stats --no-stream sentiment-data-api sentiment-market-read
# 默认不应看到 sentiment-data
curl -sf http://127.0.0.1:8081/health  # 在 data-api 容器内
```

浏览器：登录 → 首页（自选/简报/复盘）→ 行情中心 → 量化概览（无长桥时降级空状态）→ 顶栏 LIVE / WS。

---

## 并行 PR 边界

| 包 | 本 PR | 留给谁 |
|----|-------|--------|
| `services/data-api` | 新增 | — |
| `services/market-read/pkg/*` | 共享 re-export | — |
| `workers/*` | 不改 | P2/P4 |
| `module_trade` | 不改 | P1 |
| `sentiment-jobs` scheduler | 不改 | P4 |
