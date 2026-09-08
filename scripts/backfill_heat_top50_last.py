#!/usr/bin/env python3
"""
One-shot backfill for Heat Top50 missing last prices.

Reads market_top50_snapshot rows where last IS NULL/0, fills from
market_price_history_daily.close_price on that trade_date (or nearest
prior bar within 7 days). Expands HK/CN/US symbol aliases.
Does not wipe Influx/MySQL or re-run public EOD rank collection.

Example (host, dockersentiment DB on 13306):
  python3 scripts/backfill_heat_top50_last.py --from 2026-08-27 --to 2026-08-27
  python3 scripts/backfill_heat_top50_last.py --from 2026-08-20 --to 2026-08-29 --markets CN,HK,US --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'ruoyi-fastapi-backend'
if not (BACKEND / 'config').exists() and (Path('/app') / 'config').exists():
    BACKEND = Path('/app')


def parse_cli(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Backfill Heat Top50 last from stored daily bars')
    parser.add_argument('--from', dest='start_date', required=True, help='Start trade date YYYY-MM-DD')
    parser.add_argument('--to', dest='end_date', required=True, help='End trade date YYYY-MM-DD (inclusive)')
    parser.add_argument('--markets', default='CN,HK,US', help='Comma-separated markets (default CN,HK,US)')
    parser.add_argument('--dry-run', action='store_true', help='Report counts without writing')
    parser.add_argument('--env', default=os.environ.get('APP_ENV', 'dockersentiment'), help='Config env name')
    parser.add_argument('--host', default=os.environ.get('LISTING_DB_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('LISTING_DB_PORT', '13306')))
    parser.add_argument('--user', default=os.environ.get('LISTING_DB_USER', 'root'))
    parser.add_argument('--password', default=os.environ.get('LISTING_DB_PASSWORD', 'CHANGE_ME_DB_PASSWORD'))
    parser.add_argument('--database', default=os.environ.get('LISTING_DB_NAME', 'sentiment-ai'))
    return parser.parse_args(argv)


def _apply_env(args: argparse.Namespace) -> None:
    os.environ['APP_ENV'] = str(args.env)
    os.environ['DB_HOST'] = str(args.host)
    os.environ['DB_PORT'] = str(args.port)
    os.environ['DB_USERNAME'] = str(args.user)
    os.environ['DB_PASSWORD'] = str(args.password)
    os.environ['DB_DATABASE'] = str(args.database)


async def _run(args: argparse.Namespace) -> dict:
    from config.database import AsyncSessionLocal
    from module_market.service.heat_service import MarketHeatService

    markets = [item.strip().upper() for item in str(args.markets).split(',') if item.strip()]
    async with AsyncSessionLocal() as db:
        return await MarketHeatService.backfill_top50_last(
            db,
            start_date=args.start_date,
            end_date=args.end_date,
            markets=markets,
            dry_run=args.dry_run,
        )


def main() -> int:
    args = parse_cli()
    _apply_env(args)
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    result = asyncio.run(_run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('stillMissing', 0) == 0 or args.dry_run else 0


if __name__ == '__main__':
    raise SystemExit(main())
