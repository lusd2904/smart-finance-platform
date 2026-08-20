from datetime import datetime, timezone
from typing import Any

from module_market.constant.instruments import get_instrument_meta
from utils.influx_util import InfluxUtil


def _flux_from_ts(ts: int | None, fallback: str) -> str:
    if not ts:
        return fallback
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _normalize_resolution(resolution: str) -> str:
    text = str(resolution or 'D').upper()
    if text in {'D', '1D'}:
        return 'D'
    if text in {'W', '1W'}:
        return 'W'
    if text in {'M', '1M'}:
        return 'M'
    return text


def _resample_klines(klines: list[dict[str, Any]], how: str) -> list[dict[str, Any]]:
    if not klines or how == 'D':
        return klines
    try:
        import pandas as pd
    except Exception:
        return klines
    df = pd.DataFrame(klines)
    if df.empty or 'date' not in df.columns:
        return klines
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    rule = 'W-FRI' if how == 'W' else 'ME'
    agg = (
        df.resample(rule)
        .agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
        .dropna(subset=['open', 'close'])
    )
    out: list[dict[str, Any]] = []
    for idx, row in agg.iterrows():
        out.append(
            {
                'date': idx.strftime('%Y-%m-%d'),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row.get('volume') or 0),
            }
        )
    return out


class TradingViewDatafeedService:
    """
    TradingView UDF 适配器：对接 Influx 日K。
    分钟级分辨率当前无分时库，返回 no_data。
    """

    @classmethod
    def get_config(cls) -> dict[str, Any]:
        return {
            'supported_resolutions': ['D', 'W', 'M'],
            'supports_group_request': False,
            'supports_marks': False,
            'supports_search': True,
            'supports_time': True,
            'supports_timescale_marks': False,
        }

    @classmethod
    def get_symbol_info(cls, symbol: str) -> dict[str, Any]:
        clean_symbol = symbol.strip().upper()
        meta = get_instrument_meta(clean_symbol)
        name = meta[1] if meta else clean_symbol
        return {
            'name': clean_symbol,
            'ticker': clean_symbol,
            'description': f'{name} ({clean_symbol})',
            'type': 'stock',
            'session': '0930-1600',
            'timezone': 'America/New_York',
            'exchange': 'US' if clean_symbol.endswith('.US') else ('HK' if clean_symbol.endswith('.HK') else 'CN'),
            'minmov': 1,
            'pricescale': 100,
            'has_intraday': False,
            'has_daily': True,
            'has_weekly_and_monthly': True,
            'supported_resolutions': ['D', 'W', 'M'],
            'volume_precision': 0,
            'data_status': 'endofday',
        }

    @classmethod
    async def get_history_bars(
        cls, symbol: str, from_ts: int | None = None, to_ts: int | None = None, resolution: str = 'D'
    ) -> dict[str, Any]:
        clean_symbol = symbol.strip().upper()
        market = 'US'
        query_symbol = clean_symbol
        if clean_symbol.endswith('.HK'):
            market = 'HK'
            query_symbol = clean_symbol[:-3]
        elif clean_symbol.endswith('.US'):
            query_symbol = clean_symbol[:-3]
        elif clean_symbol.endswith('.SH') or clean_symbol.endswith('.SZ'):
            market = 'CN'
            query_symbol = clean_symbol[:-3]

        how = _normalize_resolution(resolution)
        if how not in {'D', 'W', 'M'}:
            return {'s': 'no_data', 'nextTime': None}

        start = _flux_from_ts(from_ts, '-2y')
        stop = _flux_from_ts(to_ts, 'now()')
        try:
            klines = InfluxUtil.query_klines(market, query_symbol, start=start, stop=stop, limit=800)
        except Exception:
            klines = []
        klines = _resample_klines(klines, how)
        if not klines:
            return {'s': 'no_data', 'nextTime': None}

        t_list, o_list, h_list, l_list, c_list, v_list = [], [], [], [], [], []
        for k in klines:
            date_str = k.get('date')
            try:
                if len(str(date_str)) == 10:
                    dt = datetime.strptime(str(date_str), '%Y-%m-%d').replace(tzinfo=timezone.utc)
                else:
                    dt = datetime.fromisoformat(str(date_str))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                ts = int(dt.timestamp())
            except Exception:
                continue
            if from_ts and ts < int(from_ts):
                continue
            if to_ts and ts > int(to_ts):
                continue
            t_list.append(ts)
            o_list.append(float(k.get('open', 0) or 0))
            h_list.append(float(k.get('high', 0) or 0))
            l_list.append(float(k.get('low', 0) or 0))
            c_list.append(float(k.get('close', 0) or 0))
            v_list.append(float(k.get('volume', 0) or 0))

        if not t_list:
            return {'s': 'no_data', 'nextTime': None}
        return {'s': 'ok', 't': t_list, 'o': o_list, 'h': h_list, 'l': l_list, 'c': c_list, 'v': v_list}
