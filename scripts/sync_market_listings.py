#!/usr/bin/env python3
"""
把美股、A股、港股全市场股票代码写入本地 market_instrument。

默认连本机 Docker MySQL（13306 / sentiment-ai）。精选池分类不会被覆盖。
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
    parser = argparse.ArgumentParser(description='Sync US/CN/HK stock listings into market_instrument')
    parser.add_argument('--markets', default='US,CN,HK', help='Comma-separated markets')
    parser.add_argument('--host', default=os.environ.get('LISTING_DB_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('LISTING_DB_PORT', '13306')))
    parser.add_argument('--user', default=os.environ.get('LISTING_DB_USER', 'root'))
    parser.add_argument('--password', default=os.environ.get('LISTING_DB_PASSWORD', 'CHANGE_ME_DB_PASSWORD'))
    parser.add_argument('--database', default=os.environ.get('LISTING_DB_NAME', 'sentiment-ai'))
    return parser.parse_args(argv)


def main() -> int:
    args = parse_cli()
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from module_market.service.listing_service import ListingService

    markets = [item.strip().upper() for item in str(args.markets).split(',') if item.strip()]
    result = ListingService.sync(
        markets=markets,
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    fetched = result.get('fetched') or {}
    missing = [m for m, n in fetched.items() if int(n or 0) < 200]
    if missing:
        print(f'WARN thin listings: {missing}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
