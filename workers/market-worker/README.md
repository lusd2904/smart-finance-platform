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
| `market_heat_collect` | **Python delegate** | Longbridge live quotes + static info (no Go SDK) |
| `symbol_content` | **Python delegate** | Longbridge ContentContext filings/news |

## Related Go workers

- `sfp-quant-worker` — `indicator_refresh` on quant queue
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

Required env: `REDIS_*`, `DB_*`, `INFLUX_*`, `INTERNAL_JOB_TOKEN`, `PYTHON_DELEGATE_URL`.

## Slim compose

P1 slim stack: `sentiment-jobs` runs **scheduler only** (`APP_JOB_GROUP=none`); Go workers consume market/quant/llm queues. Memory budget: **384m** market + **256m** quant + **256m** notify.
