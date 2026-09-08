# Go Market Worker

Low-memory consumer for Redis `sfp:job:queue:market`. Replaces the Python `sentiment-jobs-market` process (~1.5 GiB) with a ~384 MiB Go binary.

## Job routing

| Job type | Runtime | Notes |
|----------|---------|-------|
| `eod_kline_sync` | **Go** | EOD daily K + minute K → Influx |
| `market_sync` | **Go** | Featured/target pool sync |
| `klines_slow` | **Go** | Full-universe slow daily K |
| `mysql_to_influx` | **Go** | MySQL → Influx migration |
| `board_warmup` | **Go** | Influx latest bars → Redis `sfp:cache:board:quotes` |
| `listings_sync` | **Go** | Influx symbol tags → `market_instrument` (listed) |
| `finance_briefings` | **Go** | RSS + internal pulse/tech scan → `finance_briefing` |
| `market_heat_collect` | **Go** | Public EOD ranks (Sina / Tencent / Eastmoney) → `market_heat_daily` + Top50 |

### One-shot: backfill Top50 `last`

Historical rows may lack `last` (H5 shows `--`). Fill from MySQL daily bars — see [docs/runbooks/heat-top50-last-backfill.md](../../docs/runbooks/heat-top50-last-backfill.md).

```bash
cd workers/market-worker
go build -o bin/heat-backfill-last ./cmd/heat-backfill-last
DB_HOST=127.0.0.1 DB_PORT=13306 DB_DATABASE=sentiment-ai ./bin/heat-backfill-last --from 2026-08-27 --to 2026-08-27
```

Or from repo root: `python3 scripts/backfill_heat_top50_last.py --from 2026-08-27 --to 2026-08-27`.
| `symbol_content` | **Go** | Longbridge HTTP filings/news/topics (HMAC, no Python SDK) |

## Related Go workers

- `sfp-quant-worker` — quant queue: #77 factor/strategy/daily_list_scan + #78 Longbridge trade (`daily_list_open`, `auto_trade_scan`, position_monitor MO sell)
- `sfp-notify-worker` — `feishu_push` on llm queue

## Influx contract (unchanged)

- `daily_kline` / `minute_kline` measurements
- Tags: `symbol`, `market`
- Fields: `open`, `high`, `low`, `close`, `volume`
- US bucket → `market_us`; CN/HK → `market_data`

## Local build

```bash
cd workers/market-worker
go test ./...
go build -o bin/market-worker ./cmd/market-worker
```

## Docker

Service name: `sfp-market-worker` in `docker-compose.sentiment.yml`.

Health: `http://127.0.0.1:19097/health` (host) or `http://sfp-market-worker:9098/health` (compose network).

Required env: `REDIS_*`, `DB_*`, `INFLUX_*`.

Optional: `LONGPORT_APP_KEY` / `LONGPORT_APP_SECRET` / `LONGPORT_ACCESS_TOKEN` / `LONGPORT_REGION` (default `cn`) for `symbol_content`. Heat does not need Longbridge. `INTERNAL_JOBS_URL` / `INTERNAL_JOB_TOKEN` for emergency job fallback via `sfp-backend`.

## Slim compose

P1 slim stack: `sfp-scheduler` enqueues from `sys_job`; Go workers consume market/quant/llm queues. Memory budget: **64m** scheduler + **384m** market + **256m** quant + **256m** notify.
