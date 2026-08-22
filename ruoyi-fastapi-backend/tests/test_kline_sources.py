import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.kline_sources import (
    CircuitBreaker,
    SourceThrottle,
    fetch_real_klines,
    merge_real_rows,
    parse_eastmoney_klines,
    parse_sina_daily_items,
    parse_stooq_csv,
    parse_tencent_kline_payload,
    parse_yahoo_chart,
    reset_circuit_breakers,
    validate_ohlcv_row,
)
from module_market.service.sync_service import should_skip_synced
from module_market.service.tradingview_service import resolve_symbol_candidates


def test_validate_rejects_invented_or_incomplete_bars() -> None:
    assert validate_ohlcv_row({'symbol': 'AAPL', 'market': 'US', 'trade_date': '2024-01-02', 'source': 'sina'}) is None
    assert validate_ohlcv_row(
        {
            'symbol': 'AAPL',
            'market': 'US',
            'trade_date': '2024-01-02',
            'open': 1,
            'high': 2,
            'low': 3,
            'close': 1.5,
            'volume': 10,
            'source': 'sina',
        }
    ) is None
    assert validate_ohlcv_row(
        {
            'symbol': 'AAPL',
            'market': 'US',
            'trade_date': '2024-01-02',
            'open': 10,
            'high': 12,
            'low': 9,
            'close': 0,
            'volume': 10,
            'source': 'sina',
        }
    ) is None
    ok = validate_ohlcv_row(
        {
            'symbol': 'AAPL',
            'market': 'US',
            'trade_date': '2024-01-02',
            'open': 10,
            'high': 12,
            'low': 9,
            'close': 11,
            'volume': 100,
            'source': 'sina',
        }
    )
    assert ok is not None
    assert ok['close'] == 11


def test_circuit_breaker_opens_after_threshold() -> None:
    reset_circuit_breakers()
    br = CircuitBreaker(fail_threshold=2, cooldown_seconds=60)
    now = 1_700_000_000.0
    assert br.allow(now) is True
    br.record_failure(now)
    assert br.allow(now) is True
    br.record_failure(now)
    assert br.allow(now) is False
    assert br.allow(now + 61) is True


def test_parse_sina_and_tencent_real_payloads() -> None:
    years = max(1, date.today().year - 2020)
    sina = parse_sina_daily_items(
        [{'d': '2024-06-03', 'o': 190.1, 'h': 192.0, 'l': 189.5, 'c': 191.2, 'v': 1000}],
        'AAPL',
        'US',
        years,
    )
    assert len(sina) == 1
    assert sina[0]['source'] == 'sina'
    tencent = parse_tencent_kline_payload(
        {'data': {'usAAPL': {'qfqday': [['2024-06-03', '190.1', '191.2', '192.0', '189.5', '1000']]}}},
        'AAPL',
        'US',
        years,
    )
    assert len(tencent) == 1
    assert tencent[0]['high'] == 192.0


def test_parse_eastmoney_yahoo_stooq() -> None:
    years = max(1, date.today().year - 2020)
    em = parse_eastmoney_klines(
        {'data': {'klines': ['2024-06-03,190.1,191.2,192.0,189.5,1000,2000']}},
        'AAPL',
        'US',
        years,
    )
    assert em[0]['close'] == 191.2
    yahoo = parse_yahoo_chart(
        {
            'chart': {
                'result': [
                    {
                        'timestamp': [1717372800],
                        'indicators': {
                            'quote': [
                                {
                                    'open': [190.1],
                                    'high': [192.0],
                                    'low': [189.5],
                                    'close': [191.2],
                                    'volume': [1000],
                                }
                            ]
                        },
                    }
                ]
            }
        },
        'AAPL',
        'US',
        years,
    )
    assert yahoo and yahoo[0]['close'] == 191.2
    stooq = parse_stooq_csv(
        'Date,Open,High,Low,Close,Volume\n2024-06-03,190.1,192.0,189.5,191.2,1000\n',
        'AAPL',
        'US',
        years,
    )
    assert stooq[0]['source'] == 'stooq'


def test_merge_does_not_invent_missing_dates() -> None:
    a = [
        {
            'symbol': 'AAPL',
            'market': 'US',
            'trade_date': '2024-06-03',
            'open': 1,
            'high': 2,
            'low': 1,
            'close': 1.5,
            'volume': 10,
            'source': 'sina',
        }
    ]
    merged = merge_real_rows(a, [])
    assert [r['trade_date'] for r in merged] == ['2024-06-03']


def test_seed_cli_keeps_years_and_symbol() -> None:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scripts'))
    from seed_real_klines import parse_cli

    args, rest = parse_cli(['--years', '2', '--symbol', 'AAPL', '--env', 'dev'])
    assert args.years == 2
    assert args.symbol == 'AAPL'
    assert rest == ['--env', 'dev']


def test_resolve_symbol_candidates_keeps_hk() -> None:
    cands = resolve_symbol_candidates('0700.HK')
    assert cands[0] == ('0700.HK', 'HK')
    assert ('0700', 'HK') in cands
    assert all(market == 'HK' for _, market in cands)


def test_source_throttle_spaces_same_source() -> None:
    throttle = SourceThrottle(min_interval=0.4)
    throttle.wait('sina', sleeper=lambda _s: None)
    pause = throttle.wait('sina', sleeper=lambda _s: None)
    assert pause >= 0.35
    other = throttle.wait('tencent', sleeper=lambda _s: None)
    assert other == 0.0


def test_should_skip_synced_fresh_history() -> None:
    today = date(2026, 8, 22)
    assert should_skip_synced(500, '2026-08-21', min_bars=200, fresh_days=10, today=today) is True
    assert should_skip_synced(20, '2026-08-21', min_bars=200, fresh_days=10, today=today) is False
    assert should_skip_synced(500, '2026-07-01', min_bars=200, fresh_days=10, today=today) is False
    assert should_skip_synced(500, None, today=today) is False


def test_fetch_stops_after_first_good_primary(monkeypatch) -> None:
    from module_market.service import kline_sources as ks

    reset_circuit_breakers()
    bars = []
    for i in range(50):
        day = f'2024-06-{(i % 28) + 1:02d}'
        row = validate_ohlcv_row(
            {
                'symbol': 'AAPL',
                'market': 'US',
                'trade_date': day if i < 28 else f'2024-07-{(i - 27):02d}',
                'open': 10,
                'high': 12,
                'low': 9,
                'close': 11,
                'volume': 100,
                'source': 'sina',
            }
        )
        assert row is not None
        bars.append(row)
    called: list[str] = []

    def sina(_symbol: str, _market: str, _years: int) -> list[dict]:
        called.append('sina')
        return bars

    def tencent(_symbol: str, _market: str, _years: int) -> list[dict]:
        called.append('tencent')
        return [bars[0]] * 50

    monkeypatch.setitem(ks._FETCHERS, 'sina', sina)
    monkeypatch.setitem(ks._FETCHERS, 'tencent', tencent)
    rows, used = fetch_real_klines('AAPL', 'US', 2)
    assert used == ['sina']
    assert called == ['sina']
    assert len(rows) >= 40
