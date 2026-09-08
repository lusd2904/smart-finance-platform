# Go Quant Worker

Low-memory consumer for Redis `sfp:job:queue:quant` (Redis DB **2**). Job `type` strings stay aligned with MySQL `sys_job` / `JobQueue.enqueue`.

## Job routing

| Job type | Runtime | Notes |
|----------|---------|-------|
| `indicator_refresh` | **Go** | Featured-pool board snapshot → MySQL + Redis `readmodel:scheduled:board` |
| `factor_scan` | **Go** | 8-family metrics + score + Alpha101/158 subset + CS ranks → `quant_factor_snapshot` / alpha tables / `readmodel:scheduled:factors` |
| `factor_qc` | **Go** | Alphalens-style Spearman IC / IR / quantile spread → `quant_factor_qc` |
| `strategy_run` | **Go** | Per-user watchlist (or payload `symbols`) → signals in `quant_strategy_run` / `quant_strategy_signal`. **No orders.** |
| `daily_list_scan` | **Go** | CN calendar + BUY signals → `quant_daily_list` / items. **Generation only.** |
| `position_monitor` | **Go (read-only)** | Longbridge HTTP `GET /v1/asset/stock` + Influx last price; stop-loss alerts → `plat_risk_event`. `soldCount` is always **0**. |
| `daily_list_open` | **Python / #78** | Queued open / Longbridge submit. Stay on `delegateJobs` so #78 can claim native trade. |
| `auto_trade_scan` | **Python / #78** | Auto-trade execute. Stay on `delegateJobs` so #78 can claim native trade. |

Python `/internal/jobs/run` still accepts the native types as a fallback.

### P1 / #78 handoff

- `position_monitor` writes danger risk events when PnL ≤ −8%. It does **not** call `submit_order`. After #78 lands Longbridge trade execution, that path can consume the same alerts / `auto_trade_enabled` and place SELL MOs.
- `daily_list_open` and `auto_trade_scan` stay in `handler.delegateJobs` (HTTP `/internal/jobs/run`). #78 should add them to native routing; do not flip them here.

## Redis / MySQL contract

- Queue: `sfp:job:queue:quant` on `REDIS_DATABASE=2`
- Claims / processing / tickets unchanged (`sfp:job:claims`, `sfp:job:processing:quant`, `sfp:job:ticket:{jobId}`)
- Read-model keys: `readmodel:scheduled:{board,factors,overview,positions}`
- Profile bind: `plat_user_strategy_bind` + `plat_strategy_profile(_user)`

## Local build

```bash
cd workers/quant-worker
go test ./...
go build -o bin/quant-worker ./cmd/quant-worker
```

Health: `http://127.0.0.1:19096/health` (host) / `:9097/health` (compose). Body lists `nativeJobs` and `deferredToP1`.

Required env: `REDIS_*`, `DB_*`, `INFLUX_*`.

Optional (position monitor): `LONGPORT_*`, `JWT_SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY` (Fernet, same derivation as Python `CryptoUtil`).

`PYTHON_DELEGATE_URL` / `INTERNAL_JOB_TOKEN` remain for P1 jobs.

## Host smoke (cursor-1 slim)

Do **not** `compose down` or wipe volumes. Rebuild workers only:

```bash
cd /workspace/sfp-slim-64   # or the slim checkout
source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data

sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --no-deps --build sfp-quant-worker

curl -sf http://127.0.0.1:19096/health
# expect nativeJobs to include factor_scan / strategy_run / daily_list_scan / position_monitor
# deferredToP1: daily_list_open, auto_trade_scan

# After scheduler enqueue (or JobQueue.submit), tickets stay on Redis DB 2:
# docker exec sentiment-redis redis-cli -n 2 LLEN sfp:job:queue:quant
```

If JWT / Fernet keys are not in the compose `.env`, position_monitor still runs: env `LONGPORT_*` fallback, or skip accounts whose DB secrets cannot be decrypted.
