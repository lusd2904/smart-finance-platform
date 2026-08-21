import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_market.service.heat_service import MarketHeatService
from module_quant.service.longbridge_service import LongbridgeService
from utils.longbridge_breaker import LongbridgeBreaker


def setup_function() -> None:
    LongbridgeBreaker.reset()


def test_top50_cap_filter_us() -> None:
    candidates = [
        {'symbol': 'A', 'name': 'A', 'market_cap': 5e8, 'turnover': 1e9, 'change_pct': 1.0, 'currency': 'USD'},
        {'symbol': 'B', 'name': 'B', 'market_cap': 5e9, 'turnover': 2e9, 'change_pct': -1.0, 'currency': 'USD'},
        {'symbol': 'C', 'name': 'C', 'market_cap': 50e9, 'turnover': 3e9, 'change_pct': 2.0, 'currency': 'USD'},
        {'symbol': 'D', 'name': 'D', 'market_cap': 200e9, 'turnover': 9e9, 'change_pct': 0.5, 'currency': 'USD'},
    ]
    top = MarketHeatService.filter_top50_candidates('US', candidates)
    symbols = [item['symbol'] for item in top]
    assert symbols == ['C', 'B']
    assert top[0]['rankNo'] == 1


def test_top50_cap_filter_cn() -> None:
    candidates = [
        {'symbol': '600519', 'name': '茅台', 'market_cap': 15e9, 'turnover': 8e9, 'change_pct': 1.0, 'currency': 'CNY'},
        {'symbol': '000001', 'name': '平安', 'market_cap': 250e9, 'turnover': 9e9, 'change_pct': -0.5, 'currency': 'CNY'},
    ]
    top = MarketHeatService.filter_top50_candidates('CN', candidates)
    assert len(top) == 1
    assert top[0]['symbol'] == '600519'


def test_compute_heat_score_weighted() -> None:
    weights = {'index': 0.4, 'turnover': 0.3, 'advance_decline': 0.3}
    score = MarketHeatService.compute_heat_score(weights, 2.0, 1e10, 120, 80, 8e9)
    assert 0 <= score <= 100


def test_static_info_blocked_when_circuit_open() -> None:
    LongbridgeBreaker.record_failure(RuntimeError('401004 access token invalid'))
    with patch.object(LongbridgeService, 'is_configured', return_value=True):
        res = LongbridgeService.get_static_info(['AAPL.US'])
    assert res['reason'] == 'circuit_open'
    assert res['items'] == []


@pytest.mark.asyncio
async def test_watchlist_job_short_circuits_on_breaker() -> None:
    from module_market.service.watchlist_service import MarketWatchlistService

    LongbridgeBreaker.record_failure(RuntimeError('401004 access token invalid'))
    db = AsyncMock()
    result = await MarketWatchlistService.run_hourly_job(db)
    assert result['skipped'] is True
    assert result['reason'] == 'circuit_open'


@pytest.mark.asyncio
async def test_market_watchlist_add_idempotent() -> None:
    from common.vo import CrudResponseModel
    from module_market.entity.vo.market_vo import AddMarketWatchlistModel
    from module_market.service.watchlist_service import MarketWatchlistService

    db = AsyncMock()
    with patch('module_market.service.watchlist_service.MarketWatchlistDao.get_by_symbol', new=AsyncMock(return_value=object())):
        result = await MarketWatchlistService.add_services(
            db, AddMarketWatchlistModel(symbol='AAPL', market='US'), user_id=1
        )
    assert isinstance(result, CrudResponseModel)
    assert result.is_success is True
    assert '已在自选' in result.message


@pytest.mark.asyncio
async def test_market_heat_collect_skips_on_breaker() -> None:
    from utils.job_queue import _market_heat_collect

    LongbridgeBreaker.record_failure(RuntimeError('401004 access token invalid'))
    result = await _market_heat_collect({'market': 'US'})
    assert result['skipped'] is True
    assert result['reason'] == 'circuit_open'
