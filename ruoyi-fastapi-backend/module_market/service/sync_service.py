"""
行情同步服务：真实行情直写 InfluxDB

正式链路：外网真源（新浪美股日K）→ InfluxDB daily_kline（页面只读时序库）
可选补源：quant_trade / 本库 market_price_history_daily（仅历史迁移，不是业务中间层）

禁止写入随机模拟数据；同步过程不要求写 MySQL。
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timedelta
from typing import Any

import httpx
import pymysql

from config.env import DataBaseConfig
from module_market.constant.instruments import (
    INDEX_SOURCE_MAP,
    LISTED_CATEGORY,
    TARGET_INSTRUMENTS,
    get_target_symbols,
)
from module_market.service.kline_sources import (
    PRIMARY_SOURCES,
    fetch_real_klines,
    fetch_tencent_minute,
    get_circuit_breaker,
)
from utils.influx_util import InfluxUtil
from utils.log_util import logger

# 连续失败达到该次数后触发指数冷却
_CONSECUTIVE_FAIL_COOLDOWN_AT = 8

# 可选外部源库（老项目 quant_trade）
SOURCE_DB = 'quant_trade'
SOURCE_TABLE = 'us_stock_historical_data'

SINA_DAILY_URL = (
    'https://stock.finance.sina.com.cn/usstock/api/jsonp_v2.php/'
    'var%20t=/US_MinKService.getDailyK'
)
DEFAULT_SYMBOL_INTERVAL = float(os.environ.get('KLINE_SYMBOL_INTERVAL', '1.5'))
SYNC_SKIP_MIN_BARS = int(os.environ.get('KLINE_SKIP_MIN_BARS', '200'))
SYNC_SKIP_FRESH_DAYS = int(os.environ.get('KLINE_SKIP_FRESH_DAYS', '10'))

def eod_session_date(market: str, now: datetime | None = None) -> date:
    """该市场刚刚结束的那个交易日（当地时区，收盘后才切到当天）。"""
    from zoneinfo import ZoneInfo

    tz_name = {'CN': 'Asia/Shanghai', 'HK': 'Asia/Hong_Kong', 'US': 'America/New_York'}.get(
        (market or 'US').upper(), 'America/New_York'
    )
    close_hour = {'CN': 15, 'HK': 16, 'US': 16}.get((market or 'US').upper(), 16)
    tz = ZoneInfo(tz_name)
    local = (now or datetime.now(tz)).astimezone(tz) if now and now.tzinfo else datetime.now(tz)
    day = local.date()
    if local.hour < close_hour or (local.hour == close_hour and local.minute < 5):
        day = day - timedelta(days=1)
    while day.weekday() >= 5:
        day = day - timedelta(days=1)
    return day


def should_skip_eod(last_date: str | None, session_date: date | None = None) -> bool:
    """收盘增量：本地已有该交易日日K则跳过。"""
    if not last_date:
        return False
    try:
        last = date.fromisoformat(str(last_date)[:10])
    except ValueError:
        return False
    as_of = session_date or date.today()
    return last >= as_of


def should_skip_synced(
    bars: int,
    last_date: str | None,
    *,
    min_bars: int = SYNC_SKIP_MIN_BARS,
    fresh_days: int = SYNC_SKIP_FRESH_DAYS,
    today: date | None = None,
) -> bool:
    """本地已有足够且较新的日K时跳过外网，避免重复打源。"""
    if int(bars or 0) < int(min_bars):
        return False
    if not last_date:
        return False
    try:
        last = date.fromisoformat(str(last_date)[:10])
    except ValueError:
        return False
    as_of = today or date.today()
    return (as_of - last).days <= int(fresh_days)


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
    def _app_db_conn(cls) -> pymysql.connections.Connection | None:
        try:
            return pymysql.connect(
                host=DataBaseConfig.db_host,
                port=int(DataBaseConfig.db_port),
                user=DataBaseConfig.db_username,
                password=DataBaseConfig.db_password,
                database=DataBaseConfig.db_database,
                charset='utf8mb4',
                autocommit=True,
            )
        except Exception as e:
            logger.info(f'[行情同步] 业务数据库直连跳过 (非MySQL或不可用): {e}')
            return None

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
            if conn is None:
                return
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
            td = td.strftime('%Y-%m-%d') if hasattr(td, 'strftime') else str(td)[:10]
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
            if conn is None:
                return []
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
        return [
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
            for r in records or []
        ]

    @classmethod
    def _merge_rows(cls, *sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        按 trade_date 合并多源日K。
        优先级：sina > quant_trade > local_mysql（后写覆盖前写时用更高优先级）。
        """
        priority = {
            'sina': 6,
            'tencent': 5,
            'eastmoney': 4,
            'yahoo': 4,
            'stooq': 3,
            'netease': 3,
            'quant_trade': 2,
            'local_mysql': 1,
        }
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
    def _save_mysql(cls, rows: list[dict[str, Any]]) -> int:
        """顺带写入本库日K，便于全市场慢同步断点续跑。"""
        if not rows:
            return 0
        cls.ensure_history_table()
        conn = cls._app_db_conn()
        if conn is None:
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
        payload = [
            (
                r['symbol'],
                r.get('market') or 'US',
                r['trade_date'],
                r.get('open'),
                r.get('high'),
                r.get('low'),
                r.get('close'),
                r.get('volume'),
                r.get('turnover') or 0,
                r.get('source') or 'unknown',
                now,
            )
            for r in rows
        ]
        try:
            with conn.cursor() as cur:
                for i in range(0, len(payload), 400):
                    cur.executemany(sql, payload[i : i + 400])
            return len(payload)
        except Exception as exc:
            logger.warning(f'[行情同步] 写本库日K失败: {exc}')
            return 0
        finally:
            conn.close()

    @classmethod
    def _wait_if_primaries_blocked(cls) -> None:
        """仅当 sina、腾讯都熔断才整段暂停；单源冷却不挡住另一源。"""
        still_up = [name for name in PRIMARY_SOURCES if get_circuit_breaker(name).allow()]
        if still_up:
            return
        blocked_until = 0.0
        for name in PRIMARY_SOURCES:
            br = get_circuit_breaker(name)
            blocked_until = max(blocked_until, float(br.opened_until or 0))
        if blocked_until <= 0:
            return
        wait = min(30.0, max(2.0, blocked_until - time.time() + 1.0))
        logger.warning(f'[行情同步] 主源均熔断，暂停 {wait:.0f}s')
        time.sleep(wait)

    @classmethod
    def sync_symbol(
        cls,
        symbol: str,
        market: str = 'US',
        years: int = 10,
        use_fallbacks: bool = True,
    ) -> int:
        """
        同步单个标的：外网真源 → Influx，并写入本库日K便于续跑。
        全市场慢同步关闭 fallbacks，避免 Yahoo 429 把进程睡死。
        """
        symbol = (symbol or '').strip()
        market = (market or 'US').strip().upper()
        if not symbol:
            return 0

        real_rows, used_sources = fetch_real_klines(
            symbol, market, years, use_fallbacks=use_fallbacks
        )
        quant_rows = cls._rows_from_quant_mysql(symbol, market, years)
        local_rows = cls._rows_from_local_mysql(symbol, market, years)
        rows = cls._merge_rows(local_rows, quant_rows, real_rows)
        if used_sources:
            logger.info(f'[行情同步] {symbol} 外网真源={used_sources}')

        if not rows:
            logger.warning(f'[行情同步] {symbol} 无可用真实行情数据')
            return 0

        src_counts: dict[str, int] = {}
        for r in rows:
            s = r.get('source') or 'unknown'
            src_counts[s] = src_counts.get(s, 0) + 1
        primary = max(src_counts, key=src_counts.get) if src_counts else 'unknown'

        n_influx = cls._save_influx(market, rows)
        cls._save_mysql(rows)
        logger.info(
            f'[行情同步] {symbol} 完成 primary={primary} sources={src_counts} '
            f'influx={n_influx} range={rows[0]["trade_date"]}~{rows[-1]["trade_date"]} '
            f'last_close={rows[-1].get("close")}'
        )
        return n_influx

    @classmethod
    def _iter_universe(
        cls,
        markets: list[str] | None = None,
        include_listed: bool = True,
    ) -> list[tuple[str, str, str, str, int, str | None]]:
        conn = cls._app_db_conn()
        if conn is None:
            return [(s, n, m, c, 0, None) for s, n, m, c in TARGET_INSTRUMENTS]
        wanted = [m.upper() for m in (markets or ['US', 'CN', 'HK'])]
        placeholders = ','.join(['%s'] * len(wanted))
        sql = f"""
        SELECT i.symbol, i.name, i.market, i.category,
               COALESCE(p.bars, 0) AS bars, p.last_date
        FROM market_instrument i
        LEFT JOIN (
          SELECT symbol, COUNT(*) AS bars, MAX(trade_date) AS last_date
          FROM market_price_history_daily
          GROUP BY symbol
        ) p ON p.symbol = i.symbol
        WHERE i.enabled='1' AND i.market IN ({placeholders})
        """
        params: list[Any] = list(wanted)
        if not include_listed:
            sql += ' AND i.category <> %s'
            params.append(LISTED_CATEGORY)
        sql += " ORDER BY (i.category = 'listed'), FIELD(i.market, 'US','HK','CN'), i.symbol"
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() or []
        finally:
            conn.close()
        out: list[tuple[str, str, str, str, int, str | None]] = []
        for row in rows:
            last = row[5]
            if last is not None:
                last = str(last)[:10]
            out.append((row[0], row[1] or row[0], row[2], row[3], int(row[4] or 0), last))
        return out

    @classmethod
    def sync_all(cls, years: int = 10) -> dict[str, Any]:
        return cls.sync_universe(years=years, include_listed=False, symbol_interval=DEFAULT_SYMBOL_INTERVAL)

    @classmethod
    def sync_universe(
        cls,
        years: int = 10,
        markets: list[str] | None = None,
        include_listed: bool = True,
        limit: int | None = None,
        symbol_interval: float | None = None,
        skip_synced: bool = True,
        stop_path: str | None = None,
    ) -> dict[str, Any]:
        """
        慢速全市场日K同步：精选优先，源级限流，已有足够新K线则跳过。
        创建 stop_path 文件可安全停。
        """
        interval = DEFAULT_SYMBOL_INTERVAL if symbol_interval is None else max(0.0, float(symbol_interval))
        targets = cls._iter_universe(markets=markets, include_listed=include_listed)
        if limit:
            targets = targets[: max(0, int(limit))]
        details: dict[str, int] = {}
        failed: list[str] = []
        skipped: list[str] = []
        total = 0
        consecutive_fail = 0
        for idx, (symbol, _name, market, _category, bars, last_date) in enumerate(targets, start=1):
            if stop_path and os.path.exists(stop_path):
                logger.info(f'[行情同步] 收到停止文件 {stop_path}，已处理 {idx - 1}/{len(targets)}')
                break
            if skip_synced and should_skip_synced(bars, last_date):
                skipped.append(symbol)
                details[symbol] = 0
                continue
            pts = 0
            try:
                pts = cls.sync_symbol(symbol, market, years, use_fallbacks=False)
                details[symbol] = pts
                total += pts
                if pts == 0:
                    failed.append(symbol)
                    consecutive_fail += 1
                else:
                    consecutive_fail = 0
            except Exception as e:
                logger.error(f'[行情同步] {symbol} 失败: {e}')
                failed.append(symbol)
                details[symbol] = 0
                consecutive_fail += 1
            if consecutive_fail >= _CONSECUTIVE_FAIL_COOLDOWN_AT and consecutive_fail % 20 == 0:
                logger.warning(f'[行情同步] 连续失败 {consecutive_fail}，跳过空标的继续')
            if pts > 0 and interval > 0:
                time.sleep(interval)
            if idx % 20 == 0:
                logger.info(
                    f'[行情同步] 进度 {idx}/{len(targets)} ok={len([s for s, n in details.items() if n > 0])} '
                    f'skip={len(skipped)} fail={len(failed)} points={total}'
                )
        return {
            'synced_symbols': [s for s, n in details.items() if n > 0],
            'skipped': skipped,
            'total_points': total,
            'details': details,
            'failed': failed,
            'scanned': len(targets),
        }

    @classmethod
    def _eod_minute_targets(cls, market: str, cap: int = 80) -> list[tuple[str, str]]:
        market = (market or 'US').upper()
        seen: set[str] = set()
        out: list[tuple[str, str]] = []
        conn = cls._app_db_conn()
        if conn is not None:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT symbol, name FROM market_top50_snapshot
                        WHERE market=%s AND trade_date=(
                          SELECT MAX(trade_date) FROM market_top50_snapshot WHERE market=%s
                        )
                        ORDER BY rank_no
                        """,
                        (market, market),
                    )
                    for symbol, name in cur.fetchall() or []:
                        code = str(symbol or '').strip()
                        if code and code not in seen:
                            seen.add(code)
                            out.append((code, name or code))
            finally:
                conn.close()
        for symbol, name, mkt, category in TARGET_INSTRUMENTS:
            if mkt != market or category == 'index':
                continue
            if symbol not in seen:
                seen.add(symbol)
                out.append((symbol, name))
        return out[: max(1, int(cap))]

    @classmethod
    def sync_minutes(cls, market: str, symbol_interval: float = 0.4) -> dict[str, Any]:
        """收盘后拉取当日分时（腾讯 last session），写入 Influx minute_kline。"""
        market = (market or 'US').upper()
        targets = cls._eod_minute_targets(market)
        synced: list[str] = []
        failed: list[str] = []
        total = 0
        interval = max(0.0, float(symbol_interval))
        for idx, (symbol, _name) in enumerate(targets, start=1):
            try:
                rows = fetch_tencent_minute(symbol, market)
                written = InfluxUtil.write_minute_klines(market, rows) if rows else 0
                if written:
                    synced.append(symbol)
                    total += written
                else:
                    failed.append(symbol)
            except Exception as exc:
                logger.warning(f'[收盘分时] {symbol}({market}) 失败: {exc}')
                failed.append(symbol)
            if interval and idx < len(targets):
                time.sleep(interval)
        logger.info(f'[收盘分时] market={market} ok={len(synced)} fail={len(failed)} points={total}')
        return {
            'market': market,
            'scanned': len(targets),
            'synced_symbols': synced,
            'failed': failed,
            'total_points': total,
        }

    @classmethod
    def sync_eod_market(cls, market: str, years: int = 2, symbol_interval: float = 0.4) -> dict[str, Any]:
        """某一市场收盘后：增量日K（缺当日才拉）+ 精选/Top50 分时。"""
        market = (market or 'US').upper()
        session = eod_session_date(market)
        interval = max(0.0, float(symbol_interval))
        targets = cls._iter_universe(markets=[market], include_listed=True)
        details: dict[str, int] = {}
        failed: list[str] = []
        skipped: list[str] = []
        total = 0
        for idx, (symbol, _name, mkt, _category, _bars, last_date) in enumerate(targets, start=1):
            if should_skip_eod(last_date, session):
                skipped.append(symbol)
                continue
            pts = 0
            try:
                pts = cls.sync_symbol(symbol, mkt, years, use_fallbacks=False)
            except Exception as exc:
                logger.warning(f'[收盘日K] {symbol}({market}) 失败: {exc}')
            details[symbol] = pts
            total += pts
            if pts <= 0:
                failed.append(symbol)
            elif interval:
                time.sleep(interval)
            if idx % 50 == 0:
                logger.info(f'[收盘日K] {market} {idx}/{len(targets)} points={total} skip={len(skipped)}')
        minutes = cls.sync_minutes(market, symbol_interval=interval)
        return {
            'market': market,
            'sessionDate': session.isoformat(),
            'daily': {
                'scanned': len(targets),
                'synced_symbols': [s for s, n in details.items() if n > 0],
                'skipped': skipped,
                'failed': failed,
                'total_points': total,
            },
            'minute': minutes,
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
