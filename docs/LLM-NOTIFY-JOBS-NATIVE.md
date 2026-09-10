# Native LLM / notify jobs (no Python delegate)

Slim production no longer runs `sentiment-intel` / `sentiment-backend` Python containers. The `sfp:job:queue:llm` consumer is **`sfp-notify-worker`** (Go).

## Execution matrix

| Job type | Status | Handler |
|----------|--------|---------|
| `feishu_push` | **Native** | `notify-worker` → MySQL `plat_feishu_subscription` |
| `user_notice` | **Native** | `notify-worker` → `plat_notification` insert |
| `sentiment_analyze` | **Native** | `notify-worker` → OpenAI-compatible gateway + `sentiment_analysis` |
| `sentiment_collect` | **Native** | Fetches public sources in `sentiment_ai_config.enabled_sources` (eastmoney / sina / ths / wallstreetcn / google_news / jin10) into `sentiment_news` with `analyzed='0'`. `x_monitor` stays ingest-only (`POST /sentiment/ingest/x_monitor`). Cron **job 100** `job_kwargs` = `{"analyze":true}` (omitted analyze still analyzes when `auto_analyze=1`) |
| `daily_review` | **Native wrapper** | Same as `sentiment_collect` with `analyze=true` (runs analyze when `auto_analyze=1`) |
| `req_send` | **Native** | `notify-worker` → parallel bot LLM round + `ai_req_message` / `ai_req_item` |
| `req_summarize` | **Native** | Same as `req_send` with `summarize=true` |
| `watchlist_analyze` | **Native** | Factor scoring + stock-pick LLM → `market_watchlist_analysis` |
| `stock_pick_run` | **Native** | Heat/top50 candidates + factor scoring + optional AI → `market_stock_pick` |
| `market_review` | **Native** | Influx benchmarks + briefings/sentiment + AI/rule fallback → `market_daily_review` |
| `ai_analyze` | **Native** | `analyze_symbol` + persist `symbol_ai_analysis` |
| `ai_batch` | **Native** | Batch `ai_analyze` + `plat_ai_batch_run` / `plat_ai_batch_item` |

All LLM jobs return real handler results (no `skipped: true` stubs).

### `sentiment_collect` sources

Reads `sentiment_ai_config.enabled_sources` (default `eastmoney,sina,ths,wallstreetcn,google_news`). Each enabled key is fetched independently; one source failing does not abort the job.

| Source | Status | Notes |
|--------|--------|-------|
| `eastmoney` | **Native** | 东财 7x24 `np-listapi` |
| `sina` | **Native** | 新浪 7x24 `zhibo` feed |
| `ths` | **Native** | 同花顺 `news.10jqka.com.cn` |
| `wallstreetcn` | **Native** | 华尔街见闻 lives API |
| `google_news` | **Native** | Google News RSS（中文财经关键词） |
| `jin10` | **Native** | 金十快讯；空正文的 VIP 条跳过 |
| `cls` | Alias | 回退 `ths`（无签名财联社接口） |
| `x_monitor` | **Ingest only** | `POST /sentiment/ingest/x_monitor`；采集器不拉、不写 |

New rows use `analyzed='0'` and the same `md5(source:title\|id)` hashes as the old Python collector. Analyze still runs for **all** pending rows in the 10-minute window (RSS + X ingest) when `analyze` is omitted/true and `auto_analyze=1`.

Follow-ups: unique index on `sentiment_news.uniq_hash` if missing; news-list filter for `x_monitor` (frontend, out of scope here); watch Google News geo/rate limits.

## Routing changes

- **`sfp-backend` `/internal/jobs/run`**: all LLM jobs above are in `NativeGoWorkerTypes` → Redis `sfp:job:queue:llm`. `IntelBridgeTypes` is empty; `INTEL_JOBS_URL` default is blank.
- **`sfp-notify-worker`**: no `INTERNAL_JOBS_URL`; consumes Redis directly.
- **`sentiment-trade-api`**: uses `INTERNAL_JOBS_URL=http://sfp-backend:9099/internal/jobs/run` for **`strategy_evaluate` only** (optional `STRATEGY_EVAL_URL` bridge via `quant-python-fallback` profile).

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
| `STRATEGY_EVAL_URL` on `sfp-backend` | `strategy_evaluate` → legacy Python data (`quant-python-fallback` + `--profile legacy-python`) |
| `--profile legacy-python` + intel overlay | Rollback nginx → `sentiment-intel:9099` for HTTP only |
| Python `job_queue.HANDLERS` | Emergency fallback when Python workers are started manually |

## Rollback

HTTP intel rollback: `docker-compose.sentiment.intel-python-fallback.yml` + `nginx.dockersentiment.slim.python-intel.conf`.

Job execution rollback: start Python `sentiment-jobs-llm` container (profile) — not in slim default.
