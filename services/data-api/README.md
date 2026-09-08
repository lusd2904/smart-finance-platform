# data-api

Go HTTP microservice that offloads remaining `/market/` and `/quant/` routes from Python `sentiment-data` (excluding hot-read paths already served by `market-read`).

## Module

`github.com/lusd2904/smart-finance-platform/services/data-api`

Shared auth/config/response/cache/timeutil/influx are imported from `../market-read/pkg/*` (re-exports of market-read internals) via `go.mod` `replace`.

Longbridge trade/content routes use `../trade-exec` (openapi-go) and `internal/longbridge` HTTP client.

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
| `DB_HOST` | `sentiment-mysql` | MySQL compose service name |
| _(same as market-read)_ | | `JWT_*`, `DB_*`, `REDIS_*`, `INFLUX_*` |
| `CREDENTIAL_ENCRYPTION_KEY` | _(optional)_ | Fernet key for Longbridge creds in DB |

## Health

`GET /health` — no auth.

## Native routes (production)

All 11 former legacy routes are implemented in Go — see `docs/SENTIMENT-DATA-OFFLOAD.md`. Python `sentiment-data` has been removed from the repo.

## Tests

```bash
go test ./...
go build ./...
```
