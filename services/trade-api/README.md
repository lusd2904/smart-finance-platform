# trade-api

Go HTTP service for portal `/trade/*`. Native handlers cover account, positions, orders, submit/cancel, halt, realtime quotes, and auto status/settings. All other routes reverse-proxy to Python `sentiment-trade` (`TRADE_PYTHON_URL`).

See [docs/TRADE-GO-MIGRATION.md](../../docs/TRADE-GO-MIGRATION.md).
