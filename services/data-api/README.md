# data-api

Go HTTP microservice that offloads remaining `/market/` and `/quant/` routes from Python `sentiment-data` (excluding hot-read paths already served by `market-read`).

## Module

`github.com/lusd2904/smart-finance-platform/services/data-api`

Shared auth/config/response/cache/timeutil/influx are imported from `../market-read` via `go.mod` `replace`.

## Run locally

```bash
cd services/data-api
export JWT_SECRET_KEY=...
export DB_PASSWORD=...
export INFLUX_TOKEN=...
export LISTEN_ADDR=:8081
go run ./cmd/data-api
```

## Environment

| Variable | Default | Notes |
|----------|---------|-------|
| `LISTEN_ADDR` | `:8081` | HTTP bind address |
| `LEGACY_DATA_URL` | _(empty)_ | e.g. `http://sentiment-data:9099` — reverse-proxy Longbridge/pandas/SSE routes |
| _(same as market-read)_ | | `JWT_*`, `DB_*`, `REDIS_*`, `INFLUX_*` |

## Health

`GET /health` — no auth.

## Legacy routes

When `LEGACY_DATA_URL` is unset, legacy handlers return the standard error envelope explaining that `--profile legacy-data` is required.

## Tests

```bash
go test ./...
go build ./...
```
