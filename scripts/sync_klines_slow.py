#!/usr/bin/env python3
"""
慢速同步日K到 Influx + MySQL。

源级最小间隔 + 标的间隔，精选池优先，已有足够新K线则跳过。
默认连本机 Docker MySQL/Influx。创建 logs/kline_sync.stop 可安全停。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'ruoyi-fastapi-backend'
if not (BACKEND / 'config').exists() and (Path('/app') / 'config').exists():
    BACKEND = Path('/app')


def parse_cli(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Slow-sync daily klines without tripping upstream limits')
    parser.add_argument('--markets', default='US,CN,HK')
    parser.add_argument('--years', type=int, default=10)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--featured-only', action='store_true')
    parser.add_argument('--symbol-interval', type=float, default=float(os.environ.get('KLINE_SYMBOL_INTERVAL', '1.5')))
    parser.add_argument('--source-interval', type=float, default=float(os.environ.get('KLINE_SOURCE_INTERVAL', '0.8')))
    parser.add_argument('--host', default=os.environ.get('LISTING_DB_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('LISTING_DB_PORT', '13306')))
    parser.add_argument('--user', default=os.environ.get('LISTING_DB_USER', 'root'))
    parser.add_argument('--password', default=os.environ.get('LISTING_DB_PASSWORD', 'CHANGE_ME_DB_PASSWORD'))
    parser.add_argument('--database', default=os.environ.get('LISTING_DB_NAME', 'sentiment-ai'))
    parser.add_argument('--influx-url', default=os.environ.get('INFLUX_URL', 'http://127.0.0.1:18086'))
    parser.add_argument('--influx-token', default=os.environ.get('INFLUX_TOKEN', 'CHANGE_ME_INFLUX_TOKEN'))
    parser.add_argument('--influx-org', default=os.environ.get('INFLUX_ORG', 'longbridge'))
    parser.add_argument('--stop-file', default=str(ROOT / 'logs' / 'kline_sync.stop'))
    return parser.parse_args(argv)


def _apply_env(args: argparse.Namespace) -> None:
    os.environ['DB_HOST'] = str(args.host)
    os.environ['DB_PORT'] = str(args.port)
    os.environ['DB_USERNAME'] = str(args.user)
    os.environ['DB_PASSWORD'] = str(args.password)
    os.environ['DB_DATABASE'] = str(args.database)
    os.environ['INFLUX_URL'] = str(args.influx_url)
    os.environ['INFLUX_TOKEN'] = str(args.influx_token)
    os.environ['INFLUX_ORG'] = str(args.influx_org)
    os.environ['KLINE_SOURCE_INTERVAL'] = str(args.source_interval)
    os.environ['KLINE_SYMBOL_INTERVAL'] = str(args.symbol_interval)


def main() -> int:
    args = parse_cli()
    _apply_env(args)
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from module_market.service.kline_sources import get_source_throttle
    from module_market.service.sync_service import MarketSyncService

    get_source_throttle().min_interval = max(0.0, float(args.source_interval))
    markets = [item.strip().upper() for item in str(args.markets).split(',') if item.strip()]
    Path(args.stop_file).parent.mkdir(parents=True, exist_ok=True)
    result = MarketSyncService.sync_universe(
        years=args.years,
        markets=markets,
        include_listed=not args.featured_only,
        limit=args.limit or None,
        symbol_interval=args.symbol_interval,
        skip_synced=True,
        stop_path=args.stop_file,
    )
    summary = {
        'scanned': result.get('scanned'),
        'synced': len(result.get('synced_symbols') or []),
        'skipped': len(result.get('skipped') or []),
        'failed': len(result.get('failed') or []),
        'totalPoints': result.get('total_points'),
        'failedSymbols': (result.get('failed') or [])[:30],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
