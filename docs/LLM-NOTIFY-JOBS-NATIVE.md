# Native LLM / notify jobs (no Python delegate)

Slim production no longer runs `sentiment-intel` / `sentiment-backend` Python containers. The `sfp:job:queue:llm` consumer is **`sfp-notify-worker`** (Go).

## Execution matrix

| Job type | Status | Handler |
|----------|--------|---------|
| `feishu_push` | **Native** | `notify-worker` → MySQL `plat_feishu_subscription` |
| `user_notice` | **Native** | `notify-worker` → `plat_notification` insert |
| `sentiment_analyze` | **Native** | `notify-worker` → OpenAI-compatible gateway + `sentiment_analysis` |
| `sentiment_collect` | **Stub** | RSS scrapers not ported; use X monitor ingest (`POST /sentiment/ingest/x_monitor`) or `legacy-data` profile |
| `daily_review` | **Native wrapper** | Same as `sentiment_collect` with `analyze=true` (runs analyze when `auto_analyze=1`) |
| `req_send` | **Native** | `notify-worker` → parallel bot LLM round + `ai_req_message` / `ai_req_item` |
| `req_summarize` | **Native** | Same as `req_send` with `summarize=true` |
| `watchlist_analyze` | **Stub** | Needs FactorService + StockPickAnalyzer + Influx (market scope) |
| `stock_pick_run` | **Stub** | Needs full stock-pick scoring engine |
| `market_review` | **Stub** | Needs Influx benchmark context + market review analyzer |
| `ai_analyze` | **Stub** | Needs `StockPickService.analyze_symbol` |
| `ai_batch` | **Stub** | Depends on native `ai_analyze` |

Stubbed jobs return HTTP 200 with `{"skipped": true, "reason": "<job>_deferred", "message": "..."}` — they do **not** POST to Python.

## Routing changes

- **`sfp-backend` `/internal/jobs/run`**: all LLM jobs above are in `NativeGoWorkerTypes` → Redis `sfp:job:queue:llm`. `IntelBridgeTypes` is empty; `INTEL_JOBS_URL` default is blank.
- **`sfp-notify-worker`**: no `INTERNAL_JOBS_URL` / `PYTHON_DELEGATE_URL`; consumes Redis directly.
- **`sentiment-trade-api`**: still uses `PYTHON_DELEGATE_URL=http://sfp-backend:9099/internal/jobs/run` for **`strategy_evaluate` only** (quant bridge → `QUANT_JOBS_URL`).

## Env (notify-worker)

- `DB_*`, `REDIS_*`
- `JWT_SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY` — decrypt `ai_models.api_key` (Fernet)

## Kill list (removed Python delegation paths)

| Reference | Action |
|-----------|--------|
| `notify-worker` → `delegateJobs` → `INTERNAL_JOBS_URL` | Removed; all llm types native or stub |
| `sfp-backend` `IntelBridgeTypes` → `INTEL_JOBS_URL/internal/jobs/run` | Cleared |
| `INTEL_JOBS_URL` default `http://sentiment-intel:9099` | Default `""` in compose + config |
| `sfp-notify-worker` `INTERNAL_JOBS_URL` | Removed from compose |
| `workers/notify-worker/internal/delegate/python.go` | Deleted |

Still present (intentional):

| Reference | Reason |
|-----------|--------|
| `PYTHON_DELEGATE_URL` on `sentiment-trade-api` | `strategy_evaluate` quant bridge |
| `QUANT_JOBS_URL` on `sfp-backend` | `strategy_evaluate` → legacy Python data (optional profile) |
| `intel-python-fallback` compose profile | Rollback nginx → `sentiment-intel:9099` for HTTP only |
| Python `job_queue.HANDLERS` | Emergency fallback when Python workers are started manually |

## Rollback

HTTP intel rollback: `docker-compose.sentiment.intel-python-fallback.yml` + `nginx.dockersentiment.slim.python-intel.conf`.

Job execution rollback: start Python `sentiment-jobs-llm` container (profile) — not in slim default.
