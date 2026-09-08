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

Portal `/trade/*` nginx 默认指向 Go **`sentiment-trade-api`**。`sentiment-trade`（Python）保留为进程内回退与回滚 upstream，**不删**。

### 架构选择：独立 `services/trade-api`

| 方案 | 结论 |
|------|------|
| 扩展 `market-read` | 行情只读服务，不应混入下单/长桥 TradeContext |
| `quant-worker` HTTP sidecar | worker 已是 Redis 消费者；混 HTTP 增加 RSS 与故障域 |
| **新建 `services/trade-api`** | 与 `market-read` 对称；JWT/RBAC 复用同一模式；`services/trade-exec` 供 worker 与 HTTP 共享 |

### Go 原生路径（paper/sim 与实盘均由 DB 凭据决定）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/trade/account` | 长桥余额 |
| GET | `/trade/positions` | 持仓 + 实时价 |
| GET | `/trade/orders` | today / history |
| GET | `/trade/order/{id}` | 单笔委托 |
| POST | `/trade/order` | 手工下单（halt + 护栏后提交） |
| POST | `/trade/order/{id}/cancel` | 撤单 |
| GET | `/trade/quote/realtime` | 批量 lastDone |
| GET/PUT | `/trade/halt` | Redis `sfp:trade:halt` |
| GET | `/trade/auto/status` | 护栏快照（简化） |
| PUT | `/trade/auto/settings` | `auto_trade_enabled` 等 |

未原生实现的路由由 trade-api **反向代理**到 `TRADE_PYTHON_URL`（默认 `http://sentiment-trade:9099`），前端契约不变。

### 仍走 Python（nginx 或 trade-api 回退）

| 路径 | 原因 |
|------|------|
| `POST /trade/auto/run` | 策略扫描 + 可选下单（nginx 直连 Python，180s） |
| `GET /trade/quote/snapshot` | Influx + static/calc 合并 |
| `GET /trade/quote/kline` | Influx + 长桥分钟回退 |
| `GET /trade/quote/depth` / `trades` | 盘口/逐笔（待迁 SDK HTTP） |
| `/trade/backtest/*` | pandas 回测引擎 |
| `/trade/risk/*` | 风控规则 + 事件工作流 |
| `/trade/strategy-profiles*` / `strategy-bind` | 策略配置写路径 |
| `/trade/notices*` / `notifications*` | DB 通知 |
| `/trade/ai/*` | JobQueue → LLM worker |
| `/trade/feishu/*` | 飞书 webhook |
| `GET /trade/coverage` | Influx 覆盖度 |
| `GET /trade/ai-trade-runs` / `auto/decisions` | 审计列表（复杂 join） |

### Nginx 回滚（Python profile）

只改前端 conf，reload，**不要** `compose down -v`：

```nginx
# 将 catch-all 改回 Python（slim / full 对称改 /docker-api/ 与 /prod-api/）
location /prod-api/trade/ {
    proxy_pass http://sentiment-trade:9099/trade/;
    # … 超时头保持
}
```

`POST /trade/auto/run`、`/trade/ai/`、`/trade/quote/snapshot` 的专用 location 可保持不变。

### Slim 部署（cursor-1 验证）

```bash
git fetch origin && git checkout main && git pull --ff-only origin main
source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data
sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --build sentiment-trade-api sentiment-trade sentiment-frontend
```

### 冒烟（仅模拟账户，无实盘）

1. `curl -fsS http://127.0.0.1:8080/health`（trade-api 容器内）
2. 登录门户 → 交易终端：账户/持仓/委托列表
3. **模拟 token** 下提交小单 → 撤单
4. 紧急停机 PUT `/trade/halt` → 确认 POST `/trade/order` 被拦
5. 回测 / 风控 / AI 批量页仍可打开（Python 回退）

验证通过后可停止 `sentiment-trade`（保留镜像与 conf 回滚位）；`sentiment-trade-api` 依赖其作 `TRADE_PYTHON_URL` 时须保留或改 env。

---

## Remaining Python trade surfaces

These still run in FastAPI (`sentiment-trade` / `sentiment-data`), not the Go workers:

- `TradeService.submit_order_services` / `cancel_order` (manual portal + H5 极速单) — **migrated to trade-api** for HTTP; Python remains fallback
- `AutoTradeService.get_status` / `save_user_trade_settings` — **status/settings in trade-api**; `POST /trade/auto/run` stays Python
- `DailyListService.get_latest` / `open_selected` / `set_auto` / `rebalance_auto` (HTTP)
- Strategy engine HTTP / portal; scheduled `factor_scan` / `strategy_run` / `daily_list_scan` are Go (#77). `auto_trade_scan` still calls Python `strategy_evaluate` for signals.
- Quote subscribe hub / live quotes used by the portal
- Credential save/encrypt UI (`QuantService.save_longbridge_config_services`)
- Feishu trade digest (`feishu_push` on notify-worker)

## CI

- `services/trade-exec` — guard / paper / crypto 单测
- `services/trade-api` — build + compile
- `workers/quant-worker` — trade job handler tests
