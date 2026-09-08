# Go Quant Worker

Low-memory consumer for Redis `sfp:job:queue:quant` (Redis DB **2**). Job `type` strings stay aligned with MySQL `sys_job` / `JobQueue.enqueue`.

## Job routing

| Job type | Runtime | Notes |
|----------|---------|-------|
| `indicator_refresh` | **Go** | Featured-pool board snapshot → MySQL + Redis `readmodel:scheduled:board` |
| `factor_scan` | **Go (#77)** | 8-family metrics + score + Alpha101/158 subset + CS ranks → `quant_factor_snapshot` / alpha tables / `readmodel:scheduled:factors` |
| `factor_qc` | **Go (#77)** | Alphalens-style Spearman IC / IR / quantile spread → `quant_factor_qc` |
| `strategy_run` | **Go (#77)** | Per-user watchlist (or payload `symbols`) → signals in `quant_strategy_run` / `quant_strategy_signal`. **No orders.** |
| `daily_list_scan` | **Go (#77)** | CN calendar + BUY signals → `quant_daily_list` / items. **Generation only.** |
| `position_monitor` | **Go (#78)** | Longbridge positions + −8% stop; MO sell only if `auto_trade_enabled` |
| `daily_list_open` | **Go (#78)** | Queued items, market session, MO buy via official `openapi-go` TradeContext |
| `auto_trade_scan` | **Go (#78)** | Universe / FX / guards / halt / LO submit; signals from Python `strategy_evaluate` |

Python `/internal/jobs/run` still accepts these types as an emergency fallback. Portal `/trade/*` stays on `sentiment-trade`.

## Why trade jobs stay on quant-worker (not a new trade-worker)

`position_monitor`, `auto_trade_scan`, `daily_list_scan`, and `daily_list_open` already route to the **quant** queue (`utils/job_queue.py` `JOB_GROUPS`). A second consumer on the same list would steal jobs; a new `trade` queue would change scheduler / ticket / slim compose and the 256m memory budget. The official Longbridge Go SDK therefore lives **inside this worker**.

Health: `http://127.0.0.1:19096/health` (host) / `:9097/health` (compose). Body lists `nativeJobs`.

## Paper / sim (verified against current Python)

`LONGPORT_PAPERTRADING`, `require_paper`, and `submit_order_async(allow_sim=…)` **do not exist** on the live path. Sim vs live is whichever Longbridge account is stored in `quant_longbridge_config`. This worker never falls back to admin (`user_id=1`) credentials to place orders. `auto_trade_enabled` defaults off; jobs only submit when that flag is `1`. Halt key `sfp:trade:halt` still blocks new orders.

## Smoke on a Longbridge **paper** account (no live money)

1. In the portal, save **paper** App Key / Secret / Token on the account. Do not enable a live token.
2. Leave **自动交易** off. Run `auto_trade_scan` from 任务中心 — expect scan + 台账, **zero** `plat_auto_trade_decision` with `submitted`.
3. Turn 自动交易 on for that paper account only. Re-run scan during US/HK hours. Expect LO orders on the paper book and `outsideRth` set for US.
4. Queue a daily-list item (`status=queued`) and run `daily_list_open` in session — MO buy on paper.
5. For stop-loss: a paper position ≥ 8% under cost + 自动交易 on + `position_monitor` → MO sell + risk event.

Required env (same as backend): `CREDENTIAL_ENCRYPTION_KEY` or (non-prod) `JWT_SECRET_KEY` so DB secrets decrypt. Compose mounts `.env.dockersentiment`.

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

Go **1.24+** (official `github.com/longbridge/openapi-go` v0.27 requires it).

Required env: `REDIS_*`, `DB_*`, `INFLUX_*`.

Optional (trade + position monitor): `LONGPORT_*`, `JWT_SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY` (Fernet, same derivation as Python `CryptoUtil`).

`INTERNAL_JOBS_URL` / `INTERNAL_JOB_TOKEN` route `strategy_evaluate` (auto_trade signals) through `sfp-backend`; set `STRATEGY_EVAL_URL` via `quant-python-fallback` + `--profile legacy-python` only for emergency rollback. Default slim does not start Python sentiment-data.

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
# expect nativeJobs to include factor_scan / strategy_run / daily_list_scan /
# position_monitor / daily_list_open / auto_trade_scan

# After scheduler enqueue (or JobQueue.submit), tickets stay on Redis DB 2:
# docker exec sentiment-redis redis-cli -n 2 LLEN sfp:job:queue:quant
```
