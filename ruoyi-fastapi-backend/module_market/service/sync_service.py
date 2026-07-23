"""
行情同步服务：真实行情直写 InfluxDB

正式链路：外网真源（新浪美股日K）→ InfluxDB daily_kline（页面只读时序库）
可选补源：quant_trade / 本库 market_price_history_daily（仅历史迁移，不是业务中间层）

禁止写入随机模拟数据；同步过程不要求写 MySQL。
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import httpx
import pymysql

from config.env import DataBaseConfig
from module_market.constant.instruments import (
    INDEX_SOURCE_MAP,
    TARGET_INSTRUMENTS,
    get_target_symbols,
)
from utils.influx_util import InfluxUtil
from utils.log_util import logger

# 可选外部源库（老项目 quant_trade）
SOURCE_DB = 'quant_trade'
SOURCE_TABLE = 'us_stock_historical_data'

SINA_DAILY_URL = (
    'https://stock.finance.sina.com.cn/usstock/api/jsonp_v2.php/'
    'var%20t=/US_MinKService.getDailyK'
)
SINA_HEADERS = {
    'Referer': 'https://finance.sina.com.cn',
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'
    ),
}


class MarketSyncService:
    """行情数据同步服务（同步 IO，可放线程池）。"""

    @classmethod
    def _app_db_conn(cls) -> pymysql.connections.Connection:
        return pymysql.connect(
            host=DataBaseConfig.db_host,
            port=int(DataBaseConfig.db_port),
            user=DataBaseConfig.db_username,
            password=DataBaseConfig.db_password,
            database=DataBaseConfig.db_database,
            charset='utf8mb4',
            autocommit=True,
        )

    @classmethod
    def _quant_db_conn(cls) -> pymysql.connections.Connection | None:
        try:
            return pymysql.connect(
                host=DataBaseConfig.db_host,
                port=int(DataBaseConfig.db_port),
                user=DataBaseConfig.db_username,
                password=DataBaseConfig.db_password,
                database=SOURCE_DB,
                charset='utf8mb4',
            )
        except Exception as e:
            logger.info(f'[行情同步] quant_trade 不可用: {e}')
            return None

    @classmethod
    def ensure_history_table(cls) -> None:
        """确保本地历史日K表存在（仅用于存量迁移读取，非写入必经层）。"""
        sql = """
        CREATE TABLE IF NOT EXISTS market_price_history_daily (
          id BIGINT NOT NULL AUTO_INCREMENT,
          symbol VARCHAR(32) NOT NULL,
          market VARCHAR(10) NOT NULL DEFAULT 'US',
          trade_date VARCHAR(10) NOT NULL,
          open_price DOUBLE NULL,
          high_price DOUBLE NULL,
          low_price DOUBLE NULL,
          close_price DOUBLE NULL,
          volume DOUBLE NULL,
          turnover DOUBLE NULL,
          source VARCHAR(32) NULL DEFAULT 'sina',
          update_time DATETIME NULL,
          PRIMARY KEY (id),
          UNIQUE KEY uniq_symbol_trade_date (symbol, trade_date),
          KEY ix_symbol (symbol),
          KEY ix_trade_date (trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='日K历史行情表(存量迁移用)'
        """
        try:
            conn = cls._app_db_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
            finally:
                conn.close()
        except Exception as e:
            logger.info(f'[行情同步] 本地历史表检查跳过: {e}')

    @classmethod
    def _start_date(cls, years: int) -> date:
        today = date.today()
        try:
            return today.replace(year=today.year - years)
        except ValueError:
            return today.replace(year=today.year - years, day=28)

    @classmethod
    def _sina_symbol(cls, symbol: str) -> str:
        """内部符号转新浪美股接口符号。"""
        if symbol in INDEX_SOURCE_MAP:
            return INDEX_SOURCE_MAP[symbol]['sina']
        return symbol.replace('^', '')

    @classmethod
    def _fetch_sina_daily(cls, sina_symbol: str) -> list[dict[str, Any]]:
        """拉取新浪美股/指数全量日K [{d,o,h,l,c,v,a}]。"""
        try:
            resp = httpx.get(
                SINA_DAILY_URL,
                params={'symbol': sina_symbol, '___qn': '3n'},
                headers=SINA_HEADERS,
                timeout=60,
                trust_env=False,
            )
            resp.raise_for_status()
            text = resp.text
            start, end = text.find('['), text.rfind(']')
            if start == -1 or end <= start:
                logger.warning(f'[行情同步] 新浪 {sina_symbol} 响应无数组')
                return []
            arr = json.loads(text[start : end + 1])
            return arr if isinstance(arr, list) else []
        except Exception as e:
            logger.warning(f'[行情同步] 新浪 {sina_symbol} 拉取失败: {e}')
            return []

    @classmethod
    def _rows_from_sina(
        cls, symbol: str, market: str, years: int
    ) -> list[dict[str, Any]]:
        sina_symbol = cls._sina_symbol(symbol)
        arr = cls._fetch_sina_daily(sina_symbol)
        if not arr:
            return []
        start_str = cls._start_date(years).strftime('%Y-%m-%d')
        rows: list[dict[str, Any]] = []
        for item in arr:
            d = str(item.get('d', ''))[:10]
            if not d or d < start_str:
                continue
            try:
                rows.append(
                    {
                        'symbol': symbol,
                        'market': market,
                        'trade_date': d,
                        'open': float(item.get('o') or 0),
                        'high': float(item.get('h') or 0),
                        'low': float(item.get('l') or 0),
                        'close': float(item.get('c') or 0),
                        'volume': float(item.get('v') or 0),
                        'turnover': float(item.get('a') or 0),
                        'source': 'sina',
                    }
                )
            except (TypeError, ValueError):
                continue
        return rows

    @classmethod
    def _rows_from_quant_mysql(cls, symbol: str, market: str, years: int) -> list[dict[str, Any]]:
        conn = cls._quant_db_conn()
        if conn is None:
            return []
        start_str = cls._start_date(years).strftime('%Y-%m-%d')
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT symbol, trade_date, open_price, high_price, low_price, close_price, volume '
                    f'FROM {SOURCE_TABLE} WHERE symbol=%s AND trade_date>=%s ORDER BY trade_date ASC',
                    (symbol, start_str),
                )
                records = cur.fetchall()
        except Exception as e:
            logger.warning(f'[行情同步] quant_trade 查询失败 {symbol}: {e}')
            return []
        finally:
            conn.close()
        rows = []
        for r in records or []:
            td = r[1]
            if hasattr(td, 'strftime'):
                td = td.strftime('%Y-%m-%d')
            else:
                td = str(td)[:10]
            rows.append(
                {
                    'symbol': symbol,
                    'market': market,
                    'trade_date': td,
                    'open': float(r[2] or 0),
                    'high': float(r[3] or 0),
                    'low': float(r[4] or 0),
                    'close': float(r[5] or 0),
                    'volume': float(r[6] or 0),
                    'turnover': 0.0,
                    'source': 'quant_trade',
                }
            )
        return rows

    @classmethod
    def _rows_from_local_mysql(cls, symbol: str, market: str, years: int) -> list[dict[str, Any]]:
        """从本库 market_price_history_daily 读取（可选存量迁移源）。"""
        try:
            cls.ensure_history_table()
            start_str = cls._start_date(years).strftime('%Y-%m-%d')
            conn = cls._app_db_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        'SELECT symbol, market, trade_date, open_price, high_price, low_price, close_price, volume '
                        'FROM market_price_history_daily WHERE symbol=%s AND trade_date>=%s ORDER BY trade_date',
                        (symbol, start_str),
                    )
                    records = cur.fetchall()
            finally:
                conn.close()
        except Exception as e:
            logger.info(f'[行情同步] 本库历史表不可用 {symbol}: {e}')
            return []
        rows = []
        for r in records or []:
            rows.append(
                {
                    'symbol': r[0],
                    'market': (r[1] or market or 'US').upper(),
                    'trade_date': str(r[2])[:10],
                    'open': float(r[3] or 0),
                    'high': float(r[4] or 0),
                    'low': float(r[5] or 0),
                    'close': float(r[6] or 0),
                    'volume': float(r[7] or 0),
                    'source': 'local_mysql',
                }
            )
        return rows

    @classmethod
    def _merge_rows(cls, *sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        按 trade_date 合并多源日K。
        优先级：sina > quant_trade > local_mysql（后写覆盖前写时用更高优先级）。
        """
        priority = {'sina': 3, 'quant_trade': 2, 'local_mysql': 1}
        by_date: dict[str, dict[str, Any]] = {}
        for rows in sources:
            for r in rows or []:
                d = str(r.get('trade_date') or '')[:10]
                if not d:
                    continue
                close = float(r.get('close') or 0)
                if close <= 0:
                    continue
                src = r.get('source') or ''
                existing = by_date.get(d)
                if existing is None or priority.get(src, 0) >= priority.get(existing.get('source') or '', 0):
                    by_date[d] = r
        return [by_date[k] for k in sorted(by_date.keys())]

    @classmethod
    def _save_influx(cls, market: str, rows: list[dict[str, Any]]) -> int:
        """写入 Influx daily_kline（唯一正式落库）。"""
        if not rows:
            return 0
        payload = [
            {
                'symbol': r['symbol'],
                'trade_date': r['trade_date'],
                'open': r.get('open'),
                'high': r.get('high'),
                'low': r.get('low'),
                'close': r.get('close'),
                'volume': r.get('volume'),
            }
            for r in rows
        ]
        return InfluxUtil.write_klines(market, payload)

    @classmethod
    def sync_symbol(cls, symbol: str, market: str = 'US', years: int = 10) -> int:
        """
        同步单个标的到 Influx（无 MySQL 中间层）：
        - 主源：新浪外网日K
        - 补源：quant_trade / 本库历史表（仅填补缺失日期）
        - 只写 Influx
        """
        symbol = (symbol or '').strip()
        market = (market or 'US').strip().upper()
        if not symbol:
            return 0

        sina_rows = cls._rows_from_sina(symbol, market, years)
        quant_rows = cls._rows_from_quant_mysql(symbol, market, years)
        local_rows = cls._rows_from_local_mysql(symbol, market, years)
        rows = cls._merge_rows(local_rows, quant_rows, sina_rows)

        if not rows:
            logger.warning(f'[行情同步] {symbol} 无可用真实行情数据')
            return 0

        # 统计主源
        src_counts: dict[str, int] = {}
        for r in rows:
            s = r.get('source') or 'unknown'
            src_counts[s] = src_counts.get(s, 0) + 1
        primary = max(src_counts, key=src_counts.get) if src_counts else 'unknown'

        n_influx = cls._save_influx(market, rows)
        logger.info(
            f'[行情同步] {symbol} 完成 primary={primary} sources={src_counts} '
            f'influx={n_influx} range={rows[0]["trade_date"]}~{rows[-1]["trade_date"]} '
            f'last_close={rows[-1].get("close")}'
        )
        return n_influx

    @classmethod
    def sync_all(cls, years: int = 10) -> dict[str, Any]:
        details: dict[str, int] = {}
        failed: list[str] = []
        total = 0
        for symbol, _name, market, _category in TARGET_INSTRUMENTS:
            try:
                pts = cls.sync_symbol(symbol, market, years)
                details[symbol] = pts
                total += pts
                if pts == 0:
                    failed.append(symbol)
            except Exception as e:
                logger.error(f'[行情同步] {symbol} 失败: {e}')
                failed.append(symbol)
                details[symbol] = 0
        return {
            'synced_symbols': [s for s, n in details.items() if n > 0],
            'total_points': total,
            'details': details,
            'failed': failed,
        }

    @classmethod
    def sync(cls, symbol: str | None = None, years: int = 10) -> dict[str, Any]:
        if symbol:
            meta_market = 'US'
            for s, _n, m, _c in TARGET_INSTRUMENTS:
                if s == symbol:
                    meta_market = m
                    break
            pts = cls.sync_symbol(symbol, meta_market, years)
            return {
                'synced_symbols': [symbol] if pts > 0 else [],
                'total_points': pts,
                'details': {symbol: pts},
                'failed': [] if pts > 0 else [symbol],
            }
        return cls.sync_all(years)

    @classmethod
    def get_all_target_symbols(cls) -> list[str]:
        return get_target_symbols()

    @classmethod
    def mysql_to_influx(cls, symbol: str | None = None, market: str = 'US') -> dict[str, Any]:
        """
        仅从 MySQL 日K 表转存到 Influx（存量迁移，不访问外网）。
        """
        cls.ensure_history_table()
        try:
            conn = cls._app_db_conn()
        except Exception as e:
            return {'total_points': 0, 'markets': [], 'message': f'MySQL 不可用: {e}'}
        try:
            with conn.cursor() as cur:
                if symbol:
                    cur.execute(
                        'SELECT symbol, market, trade_date, open_price, high_price, low_price, close_price, volume '
                        'FROM market_price_history_daily WHERE symbol=%s ORDER BY trade_date',
                        (symbol,),
                    )
                else:
                    cur.execute(
                        'SELECT symbol, market, trade_date, open_price, high_price, low_price, close_price, volume '
                        'FROM market_price_history_daily ORDER BY symbol, trade_date'
                    )
                records = cur.fetchall()
        finally:
            conn.close()

        by_market: dict[str, list[dict[str, Any]]] = {}
        for r in records or []:
            m = (r[1] or market or 'US').upper()
            close = float(r[6] or 0)
            if close <= 0:
                continue
            by_market.setdefault(m, []).append(
                {
                    'symbol': r[0],
                    'trade_date': str(r[2])[:10],
                    'open': float(r[3] or 0),
                    'high': float(r[4] or 0),
                    'low': float(r[5] or 0),
                    'close': close,
                    'volume': float(r[7] or 0),
                }
            )
        total = 0
        for m, rows in by_market.items():
            total += cls._save_influx(m, rows)
        return {
            'total_points': total,
            'markets': list(by_market.keys()),
            'symbols': sorted({r['symbol'] for rows in by_market.values() for r in rows}),
            'message': f'已迁移 {total} 点到 Influx',
        }
