# sfp-scheduler

Go replacement for the Python `sentiment-jobs` APScheduler process (`APP_ROLE=scheduler`, `APP_JOB_GROUP=none`).

The process **only** reads `sys_job` (+ cron) and enqueues the same Redis payloads that `sfp-market-worker` / `sfp-quant-worker` / `sfp-notify-worker` already consume. It does not run job bodies.

## Behaviour

| Concern | Go scheduler | Python delta |
|---------|--------------|--------------|
| Job source | `SELECT` from `sys_job`; `status='0'` is scheduled | same |
| Pause / resume | DB status + Redis `sfp:scheduler:command` `{action:sync}` every 30s | same channels |
| Immediate run | `{action:run, jobId}` on `sfp:scheduler:command` | same |
| Cron | Quartz 6/7-field, `?`, lists, steps | `L` / `W` / `#` not implemented (unused by analysis jobs) |
| Timezone | `SCHEDULER_TZ` default **Asia/Shanghai** | Python used process-local TZ (UTC in Docker). Existing `sys_job` hours were authored as UTC wall-clock (e.g. `0 25 7 * * ?` = 15:25 Beijing). Compose pins `SCHEDULER_TZ=UTC` so fire times stay identical. |
| Misfire | policy `3`: one catch-up within 7 days (Python grace is ~1e12s); policy `2`: one catch-up within 24h; else ~1s | catch-up capped at **one** fire (no stampede after downtime) |
| Heartbeat | `sfp:scheduler:heartbeat` TTL 25s | same key so 任务中心 stays 「jobs 在线」 |
| Lock | `app:scheduler:lock` | same key — do not run Python and Go together |
| Redis | DB **2**, `LPUSH` + ticket `sfp:job:ticket:{jobId}` | same |

## Enabled job checklist (cursor-1)

| sys_job | type | queue | payload |
|--------:|------|-------|---------|
| 101 | `market_sync` | market | `{"years":10}` |
| 103 | `finance_briefings` | market | `{}` |
| 104 | `symbol_content` | market | `{}` |
| 107 | `indicator_refresh` | quant | `{}` |
| 113 | `market_heat_collect` | market | `{"market":"CN","tradeDate":null}` |
| 114 | `market_heat_collect` | market | `{"market":"HK","tradeDate":null}` |
| 115 | `market_heat_collect` | market | `{"market":"US","tradeDate":null}` |
| 117 | `feishu_push` | llm | `{}` |
| 121 | `eod_kline_sync` | market | `{"market":"CN"}` |
| 122 | `eod_kline_sync` | market | `{"market":"HK"}` |
| 123 | `eod_kline_sync` | market | `{"market":"US"}` |

## Local

```bash
cd services/sfp-scheduler
go test ./...
go build -o bin/sfp-scheduler ./cmd/sfp-scheduler
```

## Compose

Default slim/full stack starts **`sfp-scheduler`** (host `127.0.0.1:19098`). Python `sentiment-jobs` is on profile `python-scheduler`.

Rollback (Python on, Go off):

```bash
sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  -f docker-compose.sentiment.scheduler-python.yml \
  up -d --no-deps sentiment-jobs
sudo docker rm -f sfp-scheduler
```

Side-by-side notes for cursor-1: [docs/SFP-SCHEDULER.md](../../docs/SFP-SCHEDULER.md).
