#!/usr/bin/env python3
"""
Seed real daily K-lines into Influx daily_kline and MySQL
market_instrument / market_price_history_daily.

Primary sources: Sina + Tencent
Fallbacks: East Money / Yahoo / Stooq / NetEase (circuit-breakers)

Never invents OHLCV. A symbol with no real upstream bars is skipped.

Backend env.py also reads --env from argv; this script parses --years/--symbol
first and leaves the rest for that parser.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'ruoyi-fastapi-backend'


def parse_cli(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description='Seed real daily K-lines (no synthetic OHLCV).')
    parser.add_argument('--years', type=int, default=int(os.environ.get('KLINE_SEED_YEARS', '10')))
    parser.add_argument('--symbol', type=str, default=None, help='Optional single symbol')
    return parser.parse_known_args(argv)


def _prepare_backend_path() -> None:
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))


def upsert_instruments(rows: list[tuple[str, str, str, str]]) -> int:
    from module_market.service.sync_service import MarketSyncService
    from utils.log_util import logger

    conn = MarketSyncService._app_db_conn()
    if conn is None:
        logger.warning('[seed] MySQL unavailable, skip market_instrument')
        return 0
    sql = """
    INSERT INTO market_instrument (symbol, name, market, category, enabled, create_time)
    VALUES (%s, %s, %s, %s, '1', NOW())
    ON DUPLICATE KEY UPDATE
      name=VALUES(name),
      market=VALUES(market),
      category=VALUES(category),
      enabled='1'
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS market_instrument (
                  instrument_id BIGINT NOT NULL AUTO_INCREMENT,
                  symbol VARCHAR(32) NOT NULL,
                  name VARCHAR(100) NULL,
                  market VARCHAR(10) NOT NULL DEFAULT 'US',
                  category VARCHAR(20) NOT NULL DEFAULT 'star',
                  enabled CHAR(1) NOT NULL DEFAULT '1',
                  create_time DATETIME NULL,
                  PRIMARY KEY (instrument_id),
                  UNIQUE KEY uk_symbol (symbol)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            for symbol, name, market, category in rows:
                cur.execute(sql, (symbol, name, market, category))
        return len(rows)
    except Exception as exc:
        logger.warning(f'[seed] market_instrument upsert failed: {exc}')
        return 0
    finally:
        conn.close()


def upsert_price_history(rows: list[dict[str, Any]]) -> int:
    from module_market.service.sync_service import MarketSyncService
    from utils.log_util import logger

    if not rows:
        return 0
    MarketSyncService.ensure_history_table()
    conn = MarketSyncService._app_db_conn()
    if conn is None:
        logger.warning('[seed] MySQL unavailable, skip market_price_history_daily')
        return 0
    sql = """
    INSERT INTO market_price_history_daily
      (symbol, market, trade_date, open_price, high_price, low_price, close_price, volume, turnover, source, update_time)
    VALUES
      (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
      market=VALUES(market),
      open_price=VALUES(open_price),
      high_price=VALUES(high_price),
      low_price=VALUES(low_price),
      close_price=VALUES(close_price),
      volume=VALUES(volume),
      turnover=VALUES(turnover),
      source=VALUES(source),
      update_time=VALUES(update_time)
    """
    now = datetime.now()
    written = 0
    try:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    sql,
                    (
                        r['symbol'],
                        r['market'],
                        r['trade_date'],
                        r['open'],
                        r['high'],
                        r['low'],
                        r['close'],
                        r['volume'],
                        r.get('turnover') or 0,
                        r.get('source') or 'unknown',
                        now,
                    ),
                )
                written += 1
        return written
    except Exception as exc:
        logger.warning(f'[seed] market_price_history_daily upsert failed: {exc}')
        return 0
    finally:
        conn.close()


def write_influx(market: str, rows: list[dict[str, Any]]) -> int:
    from utils.influx_util import InfluxUtil
    from utils.log_util import logger

    if not rows:
        return 0
    payload = [
        {
            'symbol': r['symbol'],
            'trade_date': r['trade_date'],
            'open': r['open'],
            'high': r['high'],
            'low': r['low'],
            'close': r['close'],
            'volume': r['volume'],
        }
        for r in rows
    ]
    try:
        return InfluxUtil.write_klines(market, payload)
    except Exception as exc:
        logger.warning(f'[seed] Influx write failed market={market}: {exc}')
        return 0


def seed_symbol(symbol: str, name: str, market: str, category: str, years: int) -> dict[str, Any]:
    from module_market.service.kline_sources import fetch_real_klines
    from utils.log_util import logger

    rows, used = fetch_real_klines(symbol, market, years)
    if not rows:
        logger.warning(f'[seed] {symbol} no real OHLCV from any source')
        return {
            'symbol': symbol,
            'market': market,
            'bars': 0,
            'sources': [],
            'influx': 0,
            'mysql': 0,
        }
    mysql_n = upsert_price_history(rows)
    influx_n = write_influx(market, rows)
    logger.info(
        f'[seed] {symbol} bars={len(rows)} sources={used} '
        f'influx={influx_n} mysql={mysql_n} '
        f'range={rows[0]["trade_date"]}~{rows[-1]["trade_date"]}'
    )
    return {
        'symbol': symbol,
        'name': name,
        'market': market,
        'category': category,
        'bars': len(rows),
        'sources': used,
        'influx': influx_n,
        'mysql': mysql_n,
        'first': rows[0]['trade_date'],
        'last': rows[-1]['trade_date'],
        'lastClose': rows[-1]['close'],
    }


def seed_all(years: int = 10, symbol: str | None = None) -> dict[str, Any]:
    from module_market.constant.instruments import TARGET_INSTRUMENTS

    targets = TARGET_INSTRUMENTS
    if symbol:
        targets = [item for item in TARGET_INSTRUMENTS if item[0] == symbol]
        if not targets:
            targets = [(symbol, symbol, 'US', 'star')]

    upsert_instruments([(s, n, m, c) for s, n, m, c in targets])

    details: list[dict[str, Any]] = []
    failed: list[str] = []
    total_bars = 0
    for sym, name, market, category in targets:
        result = seed_symbol(sym, name, market, category, years)
        details.append(result)
        total_bars += int(result.get('bars') or 0)
        if not result.get('bars'):
            failed.append(sym)
    return {
        'totalBars': total_bars,
        'seeded': [d['symbol'] for d in details if d.get('bars')],
        'failed': failed,
        'details': details,
    }


def main(argv: list[str] | None = None) -> int:
    args, rest = parse_cli(argv)
    # Leave --env (and anything else) for ruoyi config.env argparse.
    sys.argv = [sys.argv[0], *rest]
    _prepare_backend_path()
    result = seed_all(years=args.years, symbol=args.symbol)
    print(
        f"seeded={len(result['seeded'])} failed={len(result['failed'])} "
        f"bars={result['totalBars']} skipped={result['failed']}"
    )
    return 0 if result['seeded'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
