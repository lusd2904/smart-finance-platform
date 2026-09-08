# Go trade execution path (P1)

Native Longbridge trade jobs run in `sfp-quant-worker`. Portal HTTP stays on `sentiment-trade`.

## Choice: extend quant-worker

Jobs already sit on Redis `sfp:job:queue:quant`. Adding `workers/trade-worker` would need a new queue + compose service + slim memory line. A shared `services/trade-exec` module would break the current Docker build context (`workers/quant-worker` only). The reusable package is `workers/quant-worker/internal/tradeexec` (symbol / guard / paper / FX / official SDK). Extract to `services/trade-exec` later if HTTP trade-read offload lands.

## Paper / sim (do not assume old flags)

Verified in current Python (`trade_client.py`, `test_auto_trade_guardrails.py`, `test_trade_order_input_validation.py`, CHANGELOG):

| Flag / kwarg | Status |
|--------------|--------|
| `LONGPORT_PAPERTRADING` | unused |
| `require_paper` | stripped from runtime config |
| `submit_order_async(allow_sim=…)` | parameter removed |
| `longport_trading_enabled` | removed |

Orders go to the Longbridge account in `quant_longbridge_config`. Paper token → paper fills. Live token → live. **Do not enable real-money by default:** `auto_trade_enabled` stays `'0'` unless the user turns it on. Trade jobs never admin-fallback credentials.

## Slim / cursor-1 rollout

1. Merge this PR. Do **not** `compose down -v`. Do not touch grok2api or MySQL/Influx volumes.
2. On cursor-1:

```bash
git fetch origin && git checkout main && git pull --ff-only origin main
source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data
sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --build --no-deps sfp-quant-worker sentiment-backend sentiment-data
```

(or `bash scripts/deploy_and_verify_slim.sh` if you want a full slim rebuild **without** down -v).

3. Confirm `sfp-quant-worker` healthy on `:19096/health` and mem_limit still **256m**.
4. `.env.dockersentiment` must contain `CREDENTIAL_ENCRYPTION_KEY` / `JWT_SECRET_KEY` (worker now `env_file`s it to decrypt DB secrets).
5. Smoke on a **paper** account only — see `workers/quant-worker/README.md`.

`sentiment-trade` HTTP paths are unchanged. No nginx trade-read offload in this PR.

## Remaining Python trade surfaces

These still run in FastAPI (`sentiment-trade` / `sentiment-data`), not this worker:

- `GET/POST /trade/*` — account, positions, orders, manual submit/cancel, quotes, halt, auto status/run
- `TradeService.submit_order_services` / `cancel_order` (manual portal + H5 极速单)
- `AutoTradeService.get_status` / `save_user_trade_settings` / HTTP `POST /trade/auto/run`
- `DailyListService.get_latest` / `open_selected` / `set_auto` / `rebalance_auto` (HTTP)
- Strategy engine HTTP / portal; scheduled `factor_scan` / `strategy_run` / `daily_list_scan` are Go (#77). `auto_trade_scan` still calls Python `strategy_evaluate` for signals.
- Quote subscribe hub / live quotes used by the portal
- Credential save/encrypt UI (`QuantService.save_longbridge_config_services`)
- Feishu trade digest (`feishu_push` on notify-worker)

Python `/internal/jobs/run` still accepts the four trade job types as an emergency fallback; the Go worker no longer delegates them wholesale.
