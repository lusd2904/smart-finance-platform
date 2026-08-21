import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.market_service import MarketService
from module_quant.service.longbridge_service import LongbridgeService
from module_quant.service.readmodel_service import ReadModelService
from module_sentiment.service.analyzer_service import SentimentAiAnalyzer
from module_market.service.finance_news_service import FinanceNewsService
from module_market.service.tradingview_service import TradingViewDatafeedService


def test_quote_from_two_real_bars() -> None:
    quote = MarketService._build_quote_from_klines(
        [
            {'date': '2024-06-03', 'open': 10, 'high': 11, 'low': 9.5, 'close': 10.5, 'volume': 100},
            {'date': '2024-06-04', 'open': 10.5, 'high': 12, 'low': 10.4, 'close': 11.55, 'volume': 120},
        ]
    )
    assert quote['last'] == 11.55
    assert quote['prevClose'] == 10.5
    assert quote['change'] == pytest.approx(1.05, rel=1e-3)
    assert MarketService._build_quote_from_klines([]) == {}


def test_flatten_account_unconfigured_is_null_not_zero() -> None:
    flat = LongbridgeService.flatten_account({'configured': False, 'message': '长桥凭据未配置', 'balances': []})
    assert flat['configured'] is False
    assert flat['totalCash'] is None
    assert flat['netAssets'] is None
    assert flat['availableCash'] is None


@pytest.mark.asyncio
async def test_board_quotes_never_calls_longbridge() -> None:
    fake_bars = {
        'AAPL': [
            {'date': '2024-06-03', 'open': 190, 'high': 192, 'low': 189, 'close': 191, 'volume': 1000},
            {'date': '2024-06-04', 'open': 191, 'high': 193, 'low': 190, 'close': 192, 'volume': 1100},
        ]
    }

    with (
        patch.object(
            MarketService,
            'get_instrument_list_services',
            new=AsyncMock(
                return_value=[{'symbol': 'AAPL', 'name': 'Apple', 'market': 'US', 'category': 'stock'}]
            ),
        ),
        patch('module_market.service.market_service.InfluxUtil.query_latest_klines', return_value=fake_bars),
    ):
        payload = await MarketService.get_board_quotes_services(AsyncMock(), category=None, market='US')

    assert payload['source'] == 'influx'
    assert payload['quotes'][0]['source'] == 'influx'
    assert payload['quotes'][0]['price'] == 192


@pytest.mark.asyncio
async def test_readmodel_overview_null_when_unconfigured() -> None:
    with (
        patch.object(ReadModelService, '_get', new=AsyncMock(return_value=None)),
        patch.object(ReadModelService, '_set', new=AsyncMock()),
        patch.object(
            LongbridgeService,
            'get_account_balance_async',
            new=AsyncMock(return_value={'configured': False, 'message': '长桥凭据未配置', 'balances': []}),
        ),
        patch.object(
            LongbridgeService,
            'get_positions_async',
            new=AsyncMock(return_value={'configured': False, 'positions': []}),
        ),
    ):
        snap = await ReadModelService.get_platform_overview_snapshot()
    assert snap['configured'] is False
    assert snap['asset']['totalCash'] is None
    assert snap['asset']['netAssets'] is None
    assert snap['position']['positions'] == []


@pytest.mark.asyncio
async def test_analyzer_429_does_not_retry() -> None:
    calls = {'n': 0}

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            calls['n'] += 1
            req = httpx.Request('POST', 'https://example.test/chat/completions')
            return httpx.Response(429, headers={'Retry-After': '30'}, request=req)

    with patch('module_sentiment.service.analyzer_service.httpx.AsyncClient', DummyClient):
        result = await SentimentAiAnalyzer.analyze(
            base_url='https://example.test',
            api_key='dummy',
            model_name='demo',
            news_list=[{'title': 't', 'content': 'c', 'source': 's', 'pub_time': ''}],
        )
    assert result['ok'] is False
    assert result['code'] == 429
    assert result['retryAfter'] == 30
    assert calls['n'] == 1


@pytest.mark.asyncio
async def test_google_news_503_returns_empty() -> None:
    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            req = httpx.Request('GET', 'https://news.google.com/rss/search')
            return httpx.Response(503, request=req)

    with patch('module_market.service.finance_news_service.httpx.AsyncClient', DummyClient):
        rows = await FinanceNewsService._fetch_google_news(MagicMock(), 'US', __import__('datetime').datetime.now())
    assert rows == []
    assert FinanceNewsService._last_google_status['ok'] is False


@pytest.mark.asyncio
async def test_tradingview_history_empty_falls_back_to_aapl() -> None:
    def fake_query(market, symbol, start='-2y', stop='now()', limit=800):
        if symbol == 'AAPL':
            return [
                {'date': '2024-06-03', 'open': 190, 'high': 192, 'low': 189, 'close': 191, 'volume': 1000}
            ]
        return []

    with patch('module_market.service.tradingview_service.InfluxUtil.query_klines', side_effect=fake_query):
        empty = await TradingViewDatafeedService.get_history_bars(symbol='', resolution='D')
        missing = await TradingViewDatafeedService.get_history_bars(symbol='0700.HK', resolution='D')
    assert empty['s'] == 'ok'
    assert empty['c'][0] == 191
    # specific symbol with no bars must not invent, and must not steal AAPL
    assert missing['s'] == 'no_data'


def test_tradingview_hk_candidate_query_order() -> None:
    seen = []

    def fake_query(market, symbol, start='-2y', stop='now()', limit=800):
        seen.append((symbol, market))
        if symbol == '0700.HK':
            return [{'date': '2024-06-03', 'open': 300, 'high': 310, 'low': 290, 'close': 305, 'volume': 10}]
        return []

    with patch('module_market.service.tradingview_service.InfluxUtil.query_klines', side_effect=fake_query):
        bars = TradingViewDatafeedService._query_first_available('0700.HK', '-2y', 'now()', allow_aapl_fallback=False)
    assert seen[0] == ('0700.HK', 'HK')
    assert bars[0]['close'] == 305
