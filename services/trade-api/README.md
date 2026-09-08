# Go trade-api — native portal `/trade/*` (no Python sentiment-trade by default).

All frontend trade routes are served by `sentiment-trade-api` using the official Longbridge Go SDK (`services/trade-exec`). Trade HTTP is request-scoped; quote depth/trades/kline/snapshot share **one** Longbridge Quote websocket per credential (see `docs/TRADE-GO-MIGRATION.md`).

- Account, positions, orders, submit/cancel, halt, quotes (realtime/depth/trades/kline/snapshot)
- Auto trade status/settings/run, backtest, risk, strategy profiles, notices, AI batch enqueue, Feishu config

`strategy_evaluate` for auto-scan calls Go `sfp-backend` `/internal/jobs/run` via `INTERNAL_JOBS_URL` (not trade HTTP, not a Python container). Default slim does not start Python trade.
