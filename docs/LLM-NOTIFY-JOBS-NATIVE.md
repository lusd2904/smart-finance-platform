# Native LLM / notify jobs (no Python delegate)

Slim production no longer runs `sentiment-intel` / `sentiment-backend` Python containers. The `sfp:job:queue:llm` consumer is **`sfp-notify-worker`** (Go).

## Execution matrix

| Job type | Status | Handler |
|----------|--------|---------|
| `feishu_push` | **Native** | `notify-worker` → MySQL `plat_feishu_subscription` |
| `user_notice` | **Native** | `notify-worker` → `plat_notification` insert |
| `sentiment_analyze` | **Native** | `notify-worker` → OpenAI-compatible gateway + `sentiment_analysis` |
| `sentiment_collect` | **Native (X-monitor path)** | Counts pending `sentiment_news` from ingest; RSS scrapers not ported — use `POST /sentiment/ingest/x_monitor` |
| `daily_review` | **Native wrapper** | Same as `sentiment_collect` with `analyze=true` (runs analyze when `auto_analyze=1`) |
| `req_send` | **Native** | `notify-worker` → parallel bot LLM round + `ai_req_message` / `ai_req_item` |
| `req_summarize` | **Native** | Same as `req_send` with `summarize=true` |
| `watchlist_analyze` | **Native** | Factor scoring + stock-pick LLM → `market_watchlist_analysis` |
| `stock_pick_run` | **Native** | Heat/top50 candidates + factor scoring + optional AI → `market_stock_pick` |
| `market_review` | **Native** | Influx benchmarks + briefings/sentiment + AI/rule fallback → `market_daily_review` |
| `ai_analyze` | **Native** | `analyze_symbol` + persist `symbol_ai_analysis` |
| `ai_batch` | **Native** | Batch `ai_analyze` + `plat_ai_batch_run` / `plat_ai_batch_item` |

All LLM jobs return real handler results (no `skipped: true` stubs).

## Routing changes

- **`sfp-backend` `/internal/jobs/run`**: all LLM jobs above are in `NativeGoWorkerTypes` → Redis `sfp:job:queue:llm`. `IntelBridgeTypes` is empty; `INTEL_JOBS_URL` default is blank.
- **`sfp-notify-worker`**: no `INTERNAL_JOBS_URL` / `PYTHON_DELEGATE_URL`; consumes Redis directly.
- **`sentiment-trade-api`**: still uses `PYTHON_DELEGATE_URL=http://sfp-backend:9099/internal/jobs/run` for **`strategy_evaluate` only** (quant bridge → `QUANT_JOBS_URL`).

## Env (notify-worker)

- `DB_*`, `REDIS_*`
- `INFLUX_URL`, `INFLUX_TOKEN`, `INFLUX_ORG`, `INFLUX_BUCKET_US`, `INFLUX_BUCKET_CN` — klines for factor scoring and market review
- `JWT_SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY` — decrypt `ai_models.api_key` (Fernet)

## Kill list (removed Python delegation paths)

| Reference | Action |
|-----------|--------|
| `notify-worker` → `delegateJobs` → `INTERNAL_JOBS_URL` | Removed; all llm types native |
| `sfp-backend` `IntelBridgeTypes` → `INTEL_JOBS_URL/internal/jobs/run` | Cleared |
| `INTEL_JOBS_URL` default `http://sentiment-intel:9099` | Default `""` in compose + config |
| `sfp-notify-worker` `INTERNAL_JOBS_URL` | Removed from compose |
| `workers/notify-worker/internal/delegate/python.go` | Deleted |
| `workers/notify-worker/internal/jobs/stub.go` | Deleted — deferred handlers implemented |

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
