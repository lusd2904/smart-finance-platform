# Go trade-api — native portal `/trade/*` (no Python sentiment-trade by default).

All frontend trade routes are served by `sentiment-trade-api` using the official Longbridge Go SDK (`services/trade-exec`).

- Account, positions, orders, submit/cancel, halt, quotes (realtime/depth/trades/kline/snapshot)
- Auto trade status/settings/run, backtest, risk, strategy profiles, notices, AI batch enqueue, Feishu config

`strategy_evaluate` for auto-scan delegates to `sfp-backend` `/internal/jobs/run` via `INTERNAL_JOBS_URL` (not trade HTTP).

Optional rollback: `docker-compose.sentiment.trade-python-fallback.yml` + `--profile legacy-python` re-enables `sentiment-trade` + `TRADE_HTTP_FALLBACK_URL`. Default slim does not start Python trade.
