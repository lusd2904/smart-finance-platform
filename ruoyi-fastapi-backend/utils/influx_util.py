"""
InfluxDB时序数据库工具类
封装行情/量化数据的写入与查询（Flux）。
measurement: daily_kline  tag: symbol,market  field: open,high,low,close,volume
"""

import re
from datetime import datetime, timezone
from typing import Any

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from config.env import InfluxConfig
from utils.log_util import logger
from utils.time_format_util import format_utc_as_beijing

_client: InfluxDBClient | None = None


_MAX_QUERY_LIMIT = 5000
_LATEST_KLINES_CHUNK = 80
_TS_LEN_FULL = 19  # 'YYYY-MM-DD HH:MM:SS' 长度
_TS_LEN_MIN = 16  # 'YYYY-MM-DD HH:MM' 长度


def _fmt_influx_minute(ts: datetime | None) -> str:
    """分钟 K 的 Influx _time 是 UTC，展示为北京时间。"""
    if ts is None:
        return ''
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return format_utc_as_beijing(ts, '%Y-%m-%d %H:%M') or ''


class InfluxQueryError(RuntimeError):
    """InfluxDB 查询失败（连接/语法/超时等）。与「无数据返回空」严格区分，避免上层把库故障当空行情。"""


def get_client() -> InfluxDBClient:
    """获取（懒加载）全局InfluxDB客户端。"""
    global _client  # noqa: PLW0603 - 模块级单例客户端，懒加载初始化
    if _client is None:
        _client = InfluxDBClient(
            url=InfluxConfig.influx_url,
            token=InfluxConfig.influx_token,
            org=InfluxConfig.influx_org,
            timeout=60_000,
        )
    return _client


def bucket_for_market(market: str) -> str:
    """按市场返回目标bucket。US->market_us，其余->market_data。"""
    return InfluxConfig.influx_bucket_us if str(market).upper() == 'US' else InfluxConfig.influx_bucket_cn


# Flux查询里symbol/时间参数均以f-string拼接，必须先白名单校验，防Flux注入
_SYMBOL_PATTERN = re.compile(r'^[A-Za-z0-9.^_-]{1,32}$')
_RELATIVE_TIME_PATTERN = re.compile(r'^-\d{1,4}(s|m|h|d|w|mo|y)$')
_RFC3339_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:?\d{2})?)?$')


def _safe_symbol(symbol: str) -> str | None:
    """校验symbol只含证券代码合法字符，非法返回None。"""
    text = str(symbol or '').strip()
    return text if _SYMBOL_PATTERN.match(text) else None


def _safe_time_clause(value: str) -> str | None:
    """把时间参数转成安全的Flux时间子句：相对时间/now()/RFC3339，其余拒绝。"""
    text = str(value or '').strip()
    if text in {'now()', '0'} or _RELATIVE_TIME_PATTERN.match(text):
        return text
    if _RFC3339_PATTERN.match(text):
        return f'time(v: "{text}")'
    return None


class InfluxUtil:
    """行情时序库读写封装。"""

    MEASUREMENT = 'daily_kline'
    MEASUREMENT_MINUTE = 'minute_kline'

    @classmethod
    def write_klines(cls, market: str, rows: list[dict[str, Any]]) -> int:
        """
        批量写入日K线。
        rows: [{symbol, trade_date(date/datetime/str), open, high, low, close, volume}]
        返回写入条数。
        """
        if not rows:
            return 0
        bucket = bucket_for_market(market)
        points: list[Point] = []
        for r in rows:
            td = r.get('trade_date')
            if isinstance(td, str):
                ts = datetime.strptime(td[:10], '%Y-%m-%d')
            elif isinstance(td, datetime):
                ts = td
            else:  # date
                ts = datetime(td.year, td.month, td.day)
            p = (
                Point(cls.MEASUREMENT)
                .tag('symbol', str(r['symbol']))
                .tag('market', str(market).upper())
                .field('open', float(r.get('open') or 0))
                .field('high', float(r.get('high') or 0))
                .field('low', float(r.get('low') or 0))
                .field('close', float(r.get('close') or 0))
                .field('volume', float(r.get('volume') or 0))
                .time(ts, WritePrecision.S)
            )
            points.append(p)
        write_api = get_client().write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=bucket, record=points)
        return len(points)

    @classmethod
    def write_minute_klines(cls, market: str, rows: list[dict[str, Any]]) -> int:
        """批量写入分时/分钟K（measurement=minute_kline）。trade_date 需带时分。"""
        if not rows:
            return 0
        bucket = bucket_for_market(market)
        points: list[Point] = []
        for row in rows:
            td = row.get('trade_date')
            if isinstance(td, datetime):
                ts = td
            elif isinstance(td, str):
                text = td.replace('T', ' ').strip()
                # 19 位='YYYY-MM-DD HH:MM:SS'，16 位='YYYY-MM-DD HH:MM'
                text = text[:_TS_LEN_FULL] if len(text) >= _TS_LEN_FULL else text[:_TS_LEN_MIN]
                try:
                    ts = datetime.strptime(
                        text, '%Y-%m-%d %H:%M:%S' if len(text) >= _TS_LEN_FULL else '%Y-%m-%d %H:%M'
                    )
                except ValueError:
                    continue
            else:
                continue
            points.append(
                Point(cls.MEASUREMENT_MINUTE)
                .tag('symbol', str(row.get('symbol') or ''))
                .tag('market', str(market).upper())
                .field('open', float(row.get('open') or 0))
                .field('high', float(row.get('high') or 0))
                .field('low', float(row.get('low') or 0))
                .field('close', float(row.get('close') or 0))
                .field('volume', float(row.get('volume') or 0))
                .time(ts, WritePrecision.S)
            )
        if not points:
            return 0
        write_api = get_client().write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=bucket, record=points)
        return len(points)

    @classmethod
    def query_klines(
        cls,
        market: str,
        symbol: str,
        start: str = '-2y',
        stop: str = 'now()',
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        查询单标的日K线，按时间升序。
        start/stop 为Flux时间（如 '-1y' 或 RFC3339）。
        limit 取时间序列末尾 N 根（因子/AI 场景不必拉满历史）。
        默认 start='-2y' 是刻意保留的大窗口：因子计算（长周期均线/波动率等）
        需要足够历史样本，且该参数由调用方按需收窄，不做渐进放宽。
        返回 [{date, open, high, low, close, volume}]
        Influx 不可用时返回空列表，避免接口 500。
        """
        try:
            bucket = bucket_for_market(market)
            symbol = _safe_symbol(symbol)
            start_clause = _safe_time_clause(start)
            stop_clause = _safe_time_clause(stop)
            if symbol is None or start_clause is None or stop_clause is None:
                logger.warning(f'[Influx] 非法查询参数被拒绝 symbol={symbol} start={start} stop={stop}')
                return []
            tail_clause = ''
            if isinstance(limit, int) and 1 <= limit <= _MAX_QUERY_LIMIT:
                tail_clause = f'\n  |> tail(n: {int(limit)})'
            flux = f'''
from(bucket: "{bucket}")
  |> range(start: {start_clause}, stop: {stop_clause})
  |> filter(fn: (r) => r._measurement == "{cls.MEASUREMENT}")
  |> filter(fn: (r) => r.symbol == "{symbol}")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"]){tail_clause}
'''
            tables = get_client().query_api().query(flux)
            return [
                {
                    'date': record.get_time().strftime('%Y-%m-%d'),
                    'open': record.values.get('open'),
                    'high': record.values.get('high'),
                    'low': record.values.get('low'),
                    'close': record.values.get('close'),
                    'volume': record.values.get('volume'),
                }
                for table in tables
                for record in table.records
            ]
        except Exception as exc:
            # 库故障必须显式暴露：静默返回空列表会让 AI 研判/回测基于"无数据"给出错误结论
            logger.error(f'[Influx] 查询K线失败 market={market} symbol={symbol}: {exc}')
            raise InfluxQueryError(f'InfluxDB 查询K线失败: {market}/{symbol}') from exc

    @classmethod
    def query_latest_klines(
        cls,
        market: str,
        symbols: list[str],
        n: int = 2,
        start: str = '-60d',
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Batch-read the latest N daily bars for many symbols in one Flux query.
        Returns {symbol: [{date, open, high, low, close, volume}, ...]} ascending.
        Large symbol lists are chunked to avoid Flux payload limits.
        """
        safe_symbols = []
        for raw in symbols or []:
            cleaned = _safe_symbol(raw)
            if cleaned:
                safe_symbols.append(cleaned)
        if not safe_symbols:
            return {}
        if len(safe_symbols) <= _LATEST_KLINES_CHUNK:
            return cls._query_latest_klines_chunk(market, safe_symbols, n, start)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for i in range(0, len(safe_symbols), _LATEST_KLINES_CHUNK):
            chunk = safe_symbols[i : i + _LATEST_KLINES_CHUNK]
            grouped.update(cls._query_latest_klines_chunk(market, chunk, n, start))
        return grouped

    @classmethod
    def _query_latest_klines_chunk(
        cls,
        market: str,
        safe_symbols: list[str],
        n: int = 2,
        start: str = '-60d',
    ) -> dict[str, list[dict[str, Any]]]:
        start_clause = _safe_time_clause(start)
        if start_clause is None:
            return {}
        limit = max(1, min(int(n or 2), 10))
        set_literal = ', '.join(f'"{s}"' for s in safe_symbols)
        try:
            bucket = bucket_for_market(market)
            flux = f'''
from(bucket: "{bucket}")
  |> range(start: {start_clause})
  |> filter(fn: (r) => r._measurement == "{cls.MEASUREMENT}")
  |> filter(fn: (r) => contains(value: r.symbol, set: [{set_literal}]))
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> group(columns: ["symbol"])
  |> sort(columns: ["_time"])
  |> tail(n: {limit})
'''
            tables = get_client().query_api().query(flux)
            grouped: dict[str, list[dict[str, Any]]] = {}
            for table in tables:
                for record in table.records:
                    sym = str(record.values.get('symbol') or '')
                    if not sym:
                        continue
                    grouped.setdefault(sym, []).append(
                        {
                            'date': record.get_time().strftime('%Y-%m-%d'),
                            'open': record.values.get('open'),
                            'high': record.values.get('high'),
                            'low': record.values.get('low'),
                            'close': record.values.get('close'),
                            'volume': record.values.get('volume'),
                        }
                    )
            for bars in grouped.values():
                bars.sort(key=lambda x: x.get('date') or '')
            return grouped
        except Exception as exc:
            logger.error(f'[Influx] 批量最新K线失败 market={market}: {exc}')
            raise InfluxQueryError(f'InfluxDB 批量查询失败: {market}') from exc

    @classmethod
    def query_minute_klines(
        cls,
        market: str,
        symbol: str,
        start: str = '-2d',
        stop: str = 'now()',
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        查询分钟 K（measurement=minute_kline）。库中无该序列时返回空列表，不补造。
        返回 [{date, open, high, low, close, volume}]，date 带时分。
        """
        try:
            bucket = bucket_for_market(market)
            symbol = _safe_symbol(symbol)
            start_clause = _safe_time_clause(start)
            stop_clause = _safe_time_clause(stop)
            if symbol is None or start_clause is None or stop_clause is None:
                logger.warning(f'[Influx] 非法分钟K参数 symbol={symbol} start={start} stop={stop}')
                return []
            tail_clause = ''
            if isinstance(limit, int) and 1 <= limit <= _MAX_QUERY_LIMIT:
                tail_clause = f'\n  |> tail(n: {int(limit)})'
            flux = f'''
from(bucket: "{bucket}")
  |> range(start: {start_clause}, stop: {stop_clause})
  |> filter(fn: (r) => r._measurement == "{cls.MEASUREMENT_MINUTE}")
  |> filter(fn: (r) => r.symbol == "{symbol}")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"]){tail_clause}
'''
            tables = get_client().query_api().query(flux)
            return [
                {
                    'date': _fmt_influx_minute(record.get_time()),
                    'open': record.values.get('open'),
                    'high': record.values.get('high'),
                    'low': record.values.get('low'),
                    'close': record.values.get('close'),
                    'volume': record.values.get('volume'),
                }
                for table in tables
                for record in table.records
            ]
        except Exception as exc:
            logger.error(f'[Influx] 查询分钟K失败 market={market} symbol={symbol}: {exc}')
            raise InfluxQueryError(f'InfluxDB 查询分钟K失败: {market}/{symbol}') from exc

    @classmethod
    def latest_date(cls, market: str, symbol: str) -> str | None:
        """返回某标的在时序库中的最新交易日(YYYY-MM-DD)，无数据返回None。"""
        bucket = bucket_for_market(market)
        symbol = _safe_symbol(symbol)
        if symbol is None:
            return None
        # 渐进窗口：绝大多数标的近7天内有交易，避免每次都全历史(-10y)扫描；
        # 依次放宽到 7d/90d/2y/10y，首个非空结果即返回，全空返回 None。
        windows = ('-7d', '-90d', '-2y', '-10y')
        fluxes = [
            f'''
from(bucket: "{bucket}")
  |> range(start: {window})
  |> filter(fn: (r) => r._measurement == "{cls.MEASUREMENT}")
  |> filter(fn: (r) => r.symbol == "{symbol}")
  |> filter(fn: (r) => r._field == "close")
  |> last()
'''
            for window in windows
        ]
        try:
            query_api = get_client().query_api()
            for flux in fluxes:
                tables = query_api.query(flux)
                for table in tables:
                    for record in table.records:
                        return record.get_time().strftime('%Y-%m-%d')
                # 当前窗口无数据，放宽到下一级窗口继续查
        except Exception as e:
            logger.error(f'latest_date查询失败 {symbol}: {e}')
            raise InfluxQueryError(f'InfluxDB latest_date 失败: {market}/{symbol}') from e
        return None

    @classmethod
    def list_symbols(cls, market: str) -> list[str]:
        """返回某市场时序库中所有symbol。"""
        bucket = bucket_for_market(market)
        flux = f'''
import "influxdata/influxdb/schema"
schema.tagValues(bucket: "{bucket}", tag: "symbol")
'''
        symbols: list[str] = []
        try:
            tables = get_client().query_api().query(flux)
            symbols.extend(record.get_value() for table in tables for record in table.records)
        except Exception as e:
            logger.warning(f'list_symbols查询失败: {e}')
        return symbols
