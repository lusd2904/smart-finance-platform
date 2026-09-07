# Go Market Worker

Low-memory consumer for the Redis `sfp:job:queue:market` queue. Replaces the Python `sentiment-jobs-market` process (~1.5 GiB) with a ~384 MiB Go binary.

## Responsibilities

| Job type | Handler |
|----------|---------|
| `eod_kline_sync` | Go: daily K + minute K → Influx |
| `market_sync` | Go: featured/target pool sync |
| `klines_slow` | Go: full-universe slow daily K |
| `mysql_to_influx` | Go: MySQL → Influx migration |
| `market_heat_collect` | Delegates to Python `/internal/jobs/run` |
| `finance_briefings` | Delegates to Python |
| `board_warmup` | Delegates to Python |
| `symbol_content` | Delegates to Python |
| `listings_sync` | Delegates to Python |

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

## Slim compose (P1)

P1 may collapse quant/llm workers; this service stays independent so market K-line fetch does not share a Python runtime with LLM jobs. Memory budget: **384m** limit.
