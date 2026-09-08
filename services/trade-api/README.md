# Go trade-api — native portal `/trade/*` (no Python sentiment-trade by default).

All frontend trade routes are served by `sentiment-trade-api` using the official Longbridge Go SDK (`services/trade-exec`).

- Account, positions, orders, submit/cancel, halt, quotes (realtime/depth/trades/kline/snapshot)
- Auto trade status/settings/run, backtest, risk, strategy profiles, notices, AI batch enqueue, Feishu config

`strategy_evaluate` for auto-scan still delegates to `sentiment-backend` `/internal/jobs/run` (not trade HTTP).

Optional rollback: `docker-compose.sentiment.trade-python-fallback.yml` re-enables `sentiment-trade` + `TRADE_PYTHON_URL`.
