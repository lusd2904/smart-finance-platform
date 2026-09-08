# Go trade migration (P1)

Two layers: **background jobs** in `sfp-quant-worker`, **portal HTTP** in `sentiment-trade-api` (with Python fallback).

---

## 1. Background jobs — `sfp-quant-worker`

Native Longbridge trade jobs run in `sfp-quant-worker`. Shared logic lives in `services/trade-exec` (symbol / guard / paper / FX / official SDK).

### Choice: extend quant-worker

Jobs already sit on Redis `sfp:job:queue:quant`. Adding `workers/trade-worker` would need a new queue + compose service + slim memory line. `services/trade-exec` is consumed by both the quant worker and `trade-api`.

### Paper / sim (do not assume old flags)

Verified in current Python (`trade_client.py`, `test_auto_trade_guardrails.py`, `test_trade_order_input_validation.py`, CHANGELOG):

| Flag / kwarg | Status |
|--------------|--------|
| `LONGPORT_PAPERTRADING` | unused |
| `require_paper` | stripped from runtime config |
| `submit_order_async(allow_sim=…)` | parameter removed |
| `longport_trading_enabled` | removed |

Orders go to the Longbridge account in `quant_longbridge_config`. Paper token → paper fills. Live token → live. **Do not enable real-money by default:** `auto_trade_enabled` stays `'0'` unless the user turns it on. Trade jobs never admin-fallback credentials.

### Slim rollout (quant-worker only)

```bash
git fetch origin && git checkout main && git pull --ff-only origin main
source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data
sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --build --no-deps sfp-quant-worker sentiment-backend sentiment-data
```

(or `bash scripts/deploy_and_verify_slim.sh` for a full slim rebuild **without** `down -v`).

Confirm `sfp-quant-worker` healthy on `:19096/health` and mem_limit still **256m**. `.env.dockersentiment` must contain `CREDENTIAL_ENCRYPTION_KEY` / `JWT_SECRET_KEY`.

Python `/internal/jobs/run` still accepts the four trade job types as an emergency fallback; the Go worker no longer delegates them wholesale.

---

## 2. Portal HTTP — `sentiment-trade-api`

Portal `/trade/*` nginx 默认指向 Go **`sentiment-trade-api`**。**默认 compose 不再启动 `sentiment-trade`（Python trade HTTP）**。

### 架构

| 组件 | 角色 |
|------|------|
| `services/trade-exec` | Longbridge official SDK：trade HTTP + **shared** quote WS |
| `services/trade-api` | JWT/RBAC HTTP；全部 `/trade/*` 原生 |
| `sentiment-backend` | `strategy_evaluate` internal job delegate（非 trade HTTP） |

### Go 原生路径（全部 `/trade/*`）

含 #83 热路径 + 本次补齐：

| 类别 | 路径 |
|------|------|
| 长桥 | account/positions/orders/submit/cancel/halt/realtime/depth/trades/kline/snapshot |
| 自动交易 | auto/status, auto/settings, **auto/run** |
| 平台 | backtest, risk, strategy-profiles, notices, notifications, coverage, ai-trade-runs, auto/decisions |
| AI/飞书 | ai/batch*, feishu/* |

`auto_trade_enabled` 默认 off；paper/sim 由 DB 长桥 token 决定（`require_paper` 语义不变）。

### Quote websocket invariant

Depth / trades / kline / snapshot still need Longbridge `QuoteContext` (protobuf WS). **Do not** call `quote.NewFromCfg` per HTTP request — the protocol client reconnects forever after `1006 unexpected EOF`, and `Close()` does not stop an in-flight reconnect loop.

`services/trade-exec` keeps **at most one live QuoteContext per credential signature**. Concurrent callers singleflight the Dial. Failed creates back off with jitter and open a circuit after repeated EOF. Handlers must not `Close` the shared session; `CloseQuoteSessions()` runs on trade-api shutdown. Token rotate Closes the previous conn.

### Python 回滚（可选 overlay）

```bash
sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  -f docker-compose.sentiment.trade-python-fallback.yml \
  up -d --build sentiment-trade sentiment-trade-api sentiment-frontend
```

或 nginx catch-all 改回 `sentiment-trade:9099`（保留 conf 回滚位）。

### Slim 部署

```bash
git fetch origin && git checkout main && git pull --ff-only origin main
source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data
sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --build sentiment-trade-api sentiment-frontend
```

**默认 slim 栈无 `sentiment-trade` 容器。**

### 冒烟（仅模拟账户，无实盘）

1. `curl -fsS http://127.0.0.1:8080/health`（trade-api 容器内）
2. 登录门户 → 交易终端：账户/持仓/委托/盘口/K线/快照
3. **模拟 token** 下提交小单 → 撤单
4. 紧急停机 PUT `/trade/halt` → 确认 POST `/trade/order` 被拦
5. 回测 / 风控 / AI 批量 / 自动扫描页可打开（全 Go）

---

## Remaining Python trade surfaces

- Portal `/trade/*` HTTP — **fully migrated to Go trade-api** (this PR). Optional `sentiment-trade` via `trade-python-fallback` overlay only.
- `strategy_evaluate` for auto-scan signals — still Python internal job on `sentiment-backend` (same as quant-worker).
- DailyListService HTTP on sentiment-data (unchanged).
- Feishu trade digest scheduled push on notify-worker (unchanged).

## CI

- `services/trade-exec` — guard / paper / crypto 单测
- `services/trade-api` — build + compile
- `workers/quant-worker` — trade job handler tests
