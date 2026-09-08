# Heat Top50 `last` backfill runbook

Heat H5/Flutter reads `top50[].last`. Rows collected before the `last` column or before public EOD rank sources included price fields show `--` in the Top card.

This runbook fills **only** missing `market_top50_snapshot.last` from stored daily bars (`market_price_history_daily.close_price` on the same `trade_date`). It does **not** wipe Influx/MySQL or re-run public rank collection.

## When to run

- After deploying PR #63 (collector + read-path fixes).
- When historical dates (e.g. `2026-08-27`) still show `--` for Top50 last prices.
- Safe to re-run: only updates rows where `last IS NULL` or `last = 0`.

## Prerequisites

- MySQL reachable with `market_top50_snapshot` and `market_price_history_daily` populated for the target dates.
- If `stillMissing` > 0, sync daily K for missing symbols first (`scripts/sync_klines_slow.py` or `klines_slow` job).

## Option A — Python one-shot (recommended on host)

From repo root on the cloud host (default dockersentiment DB on `127.0.0.1:13306`):

```bash
# Dry-run: counts only
python3 scripts/backfill_heat_top50_last.py \
  --from 2026-08-27 --to 2026-08-27 --dry-run

# Apply for one day, all markets
python3 scripts/backfill_heat_top50_last.py \
  --from 2026-08-27 --to 2026-08-27

# Date range
python3 scripts/backfill_heat_top50_last.py \
  --from 2026-08-20 --to 2026-08-29 --markets CN,HK,US
```

Inside `sentiment-backend` container:

```bash
docker exec -it sentiment-backend python3 /app/scripts/backfill_heat_top50_last.py \
  --from 2026-08-27 --to 2026-08-27 --env dockersentiment
```

Env overrides (host defaults):

| Variable | Default |
|----------|---------|
| `LISTING_DB_HOST` | `127.0.0.1` |
| `LISTING_DB_PORT` | `13306` |
| `LISTING_DB_NAME` | `sentiment-ai` |

## Option B — Go binary (market-worker path)

Build once:

```bash
cd workers/market-worker
go build -o bin/heat-backfill-last ./cmd/heat-backfill-last
```

Run with the same `DB_*` env as `sfp-market-worker`:

```bash
export DB_HOST=127.0.0.1 DB_PORT=13306 DB_USERNAME=root DB_PASSWORD=... DB_DATABASE=sentiment-ai

./bin/heat-backfill-last --from 2026-08-27 --to 2026-08-27 --dry-run
./bin/heat-backfill-last --from 2026-08-27 --to 2026-08-27
./bin/heat-backfill-last --from 2026-08-20 --to 2026-08-29 --market ALL
```

## Verify

```bash
# API (replace token)
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:12580/prod-api/market/heat/daily?market=CN&tradeDate=2026-08-27" \
  | jq '.data.top50[:3] | .[].last'

# SQL spot-check
mysql -h127.0.0.1 -P13306 -uroot -p sentiment-ai -e \
  "SELECT trade_date, COUNT(*) total, SUM(last IS NULL OR last=0) missing
   FROM market_top50_snapshot WHERE trade_date='2026-08-27' GROUP BY trade_date;"
```

Expect `missing = 0` after a successful backfill (or after daily K sync for any remaining symbols).

## Output fields

| Field | Meaning |
|-------|---------|
| `scanned` | Top50 rows with null/zero last in range |
| `patched` | Rows updated (or would update in dry-run) |
| `stillMissing` | No `close_price` on that trade_date — sync K-lines |

## Do not

| Action | Why |
|--------|-----|
| `DELETE FROM market_top50_snapshot` | Destroys rank history |
| Re-run `market_heat_collect` for old dates | Public APIs return **today** prices, not historical EOD |
| `docker compose down` / drop Influx volumes | Unrelated; risks data loss |

## Going forward

New EOD rows from `market_heat_collect` (Go `sfp-market-worker`) include `last` from Sina/Tencent/Eastmoney. Read-path enrichment in `MarketHeatService.get_daily_services` still fills transient gaps from board cache / latest daily quotes but the backfill above is the durable fix for historical gaps.
