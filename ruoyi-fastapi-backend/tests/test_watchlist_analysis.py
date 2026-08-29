import os
import sys
from types import SimpleNamespace

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.watchlist_analyzer import WatchlistAiAnalyzer, rule_based_analysis
from module_market.service.watchlist_service import (
    REC_SIGN,
    forward_returns_from_klines,
    parse_note_groups,
    resolve_watchlist_groups,
)


def test_rule_based_bullish_ma() -> None:
    result = rule_based_analysis(
        {
            'price': 110,
            'changePercent': 1.2,
            'indicators': {'close': 110, 'ma': {'ma20': 100}, 'macd': {'macd': 0.4}, 'rsi': {'rsi12': 55}},
            'news': [{'title': 'n1'}],
            'sentimentNews': [],
        }
    )
    assert result['stance'] == '偏多'
    assert result['recommendation'] in {'持有', '买入', '加仓'}
    assert 30 <= result['confidence'] <= 80
    assert '资讯' in result['news_review']


def test_rule_based_overbought() -> None:
    result = rule_based_analysis(
        {
            'indicators': {'close': 120, 'ma': {'ma20': 100}, 'rsi': {'rsi12': 82}, 'macd': {'macd': 1}},
            'news': [],
            'sentimentNews': [{'title': 'x'}],
        }
    )
    assert result['recommendation'] == '减仓'


def test_forward_returns_from_analysis_date() -> None:
    klines = [
        {'date': '2024-06-03', 'close': 100},
        {'date': '2024-06-04', 'close': 110},
        {'date': '2024-06-05', 'close': 105},
        {'date': '2024-06-06', 'close': 108},
        {'date': '2024-06-07', 'close': 112},
        {'date': '2024-06-10', 'close': 120},
    ]
    out = forward_returns_from_klines(klines, '2024-06-03 15:00:00')
    assert out['fwd1'] == 10.0
    assert out['fwd5'] == 20.0
    pending = forward_returns_from_klines(klines, '2024-06-10')
    assert pending['fwd1'] is None
    assert pending['fwd5'] is None
    assert REC_SIGN['买入'] == 1
    assert REC_SIGN['卖出'] == -1


def test_parse_note_groups_splits_comma() -> None:
    assert parse_note_groups('七巨头,光') == ['七巨头', '光']
    assert parse_note_groups('七巨头，持仓,七巨头') == ['七巨头', '持仓']
    assert parse_note_groups('') == []
    assert parse_note_groups(None) == []


def test_resolve_watchlist_groups_prefers_groups_column() -> None:
    row = SimpleNamespace(groups='核心,持仓', note='这是备注,不是分组')
    assert resolve_watchlist_groups(row) == ['核心', '持仓']
    legacy = SimpleNamespace(groups=None, note='七巨头,持仓')
    assert resolve_watchlist_groups(legacy) == ['七巨头', '持仓']


def test_backtest_batches_klines_by_market() -> None:
    import asyncio
    from unittest.mock import AsyncMock, patch

    from module_market.service.watchlist_service import MarketWatchlistService

    rows = [
        SimpleNamespace(
            analysis_id=1,
            symbol='AAPL',
            market='US',
            recommendation='买入',
            stance='偏多',
            confidence=60,
            analysis_time=None,
            price=100,
        ),
        SimpleNamespace(
            analysis_id=2,
            symbol='MSFT',
            market='US',
            recommendation='卖出',
            stance='偏空',
            confidence=55,
            analysis_time=None,
            price=200,
        ),
        SimpleNamespace(
            analysis_id=3,
            symbol='0700',
            market='HK',
            recommendation='买入',
            stance='偏多',
            confidence=50,
            analysis_time=None,
            price=300,
        ),
    ]
    calls: list[tuple] = []

    def fake_many(market, symbols, start='-1y', limit=320):
        calls.append((market, tuple(symbols), start, limit))
        return {
            s: [{'date': '2024-01-02', 'close': 10}, {'date': '2024-01-03', 'close': 11}] for s in symbols
        }

    async def _run():
        with (
            patch(
                'module_market.service.watchlist_service.MarketWatchlistAnalysisDao.list_recent_by_user',
                AsyncMock(return_value=rows),
            ),
            patch('module_market.service.watchlist_service.InfluxUtil.query_klines_many', fake_many),
        ):
            return await MarketWatchlistService.backtest_services(SimpleNamespace(), 1)

    result = asyncio.run(_run())
    assert {c[0] for c in calls} == {'US', 'HK'}
    us_call = next(c for c in calls if c[0] == 'US')
    assert set(us_call[1]) == {'AAPL', 'MSFT'}
    assert result['count'] == 3


def test_parse_json_from_markdown() -> None:
    raw = '```json\n{"stance": "中性", "recommendation": "观望", "confidence": 51}\n```'
    parsed = WatchlistAiAnalyzer.parse_response(raw)
    assert parsed['stance'] == '中性'
    assert parsed['confidence'] == 51


def _watchlist_row(user_id: int, symbol: str, name: str, row_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=row_id,
        user_id=user_id,
        symbol=symbol,
        market='US',
        name=name,
        note=None,
        groups=None,
        enabled='1',
        sort_order=0,
        create_time=None,
    )


def test_overview_seeds_live_then_mysql() -> None:
    import asyncio
    from unittest.mock import AsyncMock, patch

    from module_market.service.watchlist_service import MarketWatchlistService

    aapl = _watchlist_row(9, 'AAPL', 'Apple', 1)
    msft = _watchlist_row(9, 'MSFT', 'Microsoft', 2)
    live = {
        'items': [{'symbol': 'AAPL', 'last': 321, 'changeRate': 2.5, 'quoteTime': '2026-08-29 10:01:00'}],
        'source': 'longbridge',
        'cached': False,
    }

    async def _run():
        with (
            patch(
                'module_market.service.watchlist_service.MarketWatchlistDao.get_enabled',
                AsyncMock(return_value=[aapl, msft]),
            ),
            patch(
                'module_market.service.watchlist_service.MarketWatchlistAnalysisDao.list_latest_by_symbols',
                AsyncMock(return_value={}),
            ),
            patch(
                'module_market.service.live_quotes_service.LiveQuotesService.get_quotes',
                AsyncMock(return_value=live),
            ),
            patch(
                'module_market.service.watchlist_service.MarketInstrumentDao.get_latest_daily_quotes',
                AsyncMock(return_value={'MSFT': {'price': 400, 'changeRate': 1.0, 'tradeDate': '2026-08-01'}}),
            ) as mysql,
            patch('module_market.service.watchlist_service.InfluxUtil.query_latest_klines', return_value={}),
        ):
            payload = await MarketWatchlistService._build_overview(object(), 9)
        return payload, mysql

    payload, mysql = asyncio.run(_run())
    assert payload['quoteSource'] == 'live+mysql'
    by_sym = {row['symbol']: row for row in payload['items']}
    assert by_sym['AAPL']['last'] == 321
    assert by_sym['MSFT']['last'] == 400
    mysql.assert_awaited()
    assert mysql.await_args.args[1] == ['MSFT']


def test_overview_live_quotes_failure_falls_back_mysql() -> None:
    import asyncio
    from unittest.mock import AsyncMock, patch

    from module_market.service.watchlist_service import MarketWatchlistService

    aapl = _watchlist_row(9, 'AAPL', 'Apple', 1)

    async def _run():
        with (
            patch(
                'module_market.service.watchlist_service.MarketWatchlistDao.get_enabled',
                AsyncMock(return_value=[aapl]),
            ),
            patch(
                'module_market.service.watchlist_service.MarketWatchlistAnalysisDao.list_latest_by_symbols',
                AsyncMock(return_value={}),
            ),
            patch(
                'module_market.service.live_quotes_service.LiveQuotesService.get_quotes',
                AsyncMock(side_effect=RuntimeError('hub down')),
            ),
            patch(
                'module_market.service.watchlist_service.MarketInstrumentDao.get_latest_daily_quotes',
                AsyncMock(return_value={'AAPL': {'price': 100, 'changeRate': 0.5, 'tradeDate': '2026-08-01'}}),
            ),
            patch('module_market.service.watchlist_service.InfluxUtil.query_latest_klines', return_value={}),
        ):
            return await MarketWatchlistService._build_overview(object(), 9)

    payload = asyncio.run(_run())
    assert payload['quoteSource'] == 'mysql'
    assert payload['items'][0]['last'] == 100
