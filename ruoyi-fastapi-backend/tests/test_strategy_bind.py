import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from exceptions.exception import ServiceException
from module_quant.entity.vo.quant_vo import RunStrategyModel
from module_quant.service.quant_service import QuantService
from module_task.trade_task import _parse_scan_args, run_auto_trade_scan_job
from module_trade.dao.trade_dao import TradeDao
from module_trade.service.platform_ext_service import (
    DEFAULT_STRATEGY_PROFILE,
    PlatformExtService,
)
from utils.job_queue import JobQueue, _optional_profile, _strategy_run


def _profile_row(code='balanced', name='均衡', cfg='{"buyThreshold": 64}'):
    return SimpleNamespace(
        profile_code=code,
        profile_name=name,
        config_json=cfg,
        update_time=None,
    )


def _bind_row(user_id=101, code='aggressive'):
    return SimpleNamespace(user_id=user_id, profile_code=code, update_time=None)


def test_normalize_and_resolve_profile() -> None:
    assert PlatformExtService.normalize_strategy_profile('Aggressive') == 'aggressive'
    assert PlatformExtService.normalize_strategy_profile('nope') == DEFAULT_STRATEGY_PROFILE
    assert PlatformExtService.normalize_strategy_profile(None) == DEFAULT_STRATEGY_PROFILE

    async def _run() -> None:
        db = MagicMock()
        with patch.object(TradeDao, 'get_user_strategy_bind', AsyncMock(return_value=_bind_row())):
            assert await PlatformExtService.get_bound_profile(db, 101) == 'aggressive'
            assert await PlatformExtService.resolve_profile(db, 101, None) == 'aggressive'
            assert await PlatformExtService.resolve_profile(db, 101, 'conservative') == 'conservative'
        with patch.object(TradeDao, 'get_user_strategy_bind', AsyncMock(return_value=None)):
            assert await PlatformExtService.get_bound_profile(db, 202) == 'balanced'
            assert await PlatformExtService.resolve_profile(db, 202, '') == 'balanced'
        assert await PlatformExtService.get_bound_profile(db, None) == 'balanced'

    asyncio.run(_run())


def test_bind_rejects_invalid_and_writes_account() -> None:
    async def _run() -> None:
        db = MagicMock()
        db.commit = AsyncMock()
        with patch.object(TradeDao, 'upsert_user_strategy_bind', AsyncMock()) as upsert:
            code = await PlatformExtService.bind_user_strategy(db, 7, 'aggressive')
        assert code == 'aggressive'
        upsert.assert_awaited_once()
        db.commit.assert_awaited_once()

        try:
            await PlatformExtService.bind_user_strategy(db, 7, 'moon')
        except ServiceException as exc:
            assert '无效' in exc.message
            return
        raise AssertionError('expected ServiceException')

    asyncio.run(_run())


def test_list_marks_active_per_account() -> None:
    async def _run() -> None:
        defaults = [
            _profile_row('aggressive', '进取', '{"buyThreshold": 56}'),
            _profile_row('balanced', '均衡', '{"buyThreshold": 64}'),
        ]
        with (
            patch.object(PlatformExtService, 'ensure_seed_data', AsyncMock()),
            patch.object(TradeDao, 'list_strategy_profiles', AsyncMock(return_value=defaults)),
            patch.object(TradeDao, 'list_user_strategy_profiles', AsyncMock(return_value=[])),
            patch.object(
                TradeDao, 'get_user_strategy_bind', AsyncMock(return_value=_bind_row(code='aggressive'))
            ),
        ):
            rows = await PlatformExtService.list_strategy_profiles(MagicMock(), user_id=101)
        by_code = {r['profileCode']: r for r in rows}
        assert by_code['aggressive']['active'] is True
        assert by_code['balanced']['active'] is False

        with (
            patch.object(PlatformExtService, 'ensure_seed_data', AsyncMock()),
            patch.object(TradeDao, 'list_strategy_profiles', AsyncMock(return_value=defaults)),
            patch.object(TradeDao, 'list_user_strategy_profiles', AsyncMock(return_value=[])),
            patch.object(TradeDao, 'get_user_strategy_bind', AsyncMock(return_value=_bind_row(202, 'conservative'))),
        ):
            other = await PlatformExtService.list_strategy_profiles(MagicMock(), user_id=202)
        assert all(r['active'] is False for r in other if r['profileCode'] != 'conservative')

    asyncio.run(_run())


def test_two_accounts_keep_separate_binds() -> None:
    store = {
        11: _bind_row(11, 'aggressive'),
        22: _bind_row(22, 'conservative'),
    }

    async def fake_get(_db, user_id):
        return store.get(int(user_id))

    async def _run() -> None:
        with patch.object(TradeDao, 'get_user_strategy_bind', fake_get):
            a = await PlatformExtService.get_bound_profile(MagicMock(), 11)
            b = await PlatformExtService.get_bound_profile(MagicMock(), 22)
            missing = await PlatformExtService.get_bound_profile(MagicMock(), 99)
        assert a == 'aggressive'
        assert b == 'conservative'
        assert missing == 'balanced'

    asyncio.run(_run())


def test_run_strategy_skips_without_user_and_uses_bound() -> None:
    async def _run() -> None:
        empty = await QuantService.run_strategy_services(MagicMock(), RunStrategyModel(), user_id=None)
        assert empty['message'] == '未指定用户，跳过'

        captured = {}

        async def fake_load(db, profile, user_id=None):
            captured['profile'] = profile
            captured['user_id'] = user_id
            return {'buyThreshold': 50}

        with (
            patch.object(TradeDao, 'get_user_strategy_bind', AsyncMock(return_value=_bind_row(5, 'conservative'))),
            patch.object(QuantService, 'load_profile_config', fake_load),
            patch(
                'module_market.dao.market_dao.MarketWatchlistDao.get_enabled',
                AsyncMock(return_value=[]),
            ),
        ):
            result = await QuantService.run_strategy_services(
                MagicMock(), RunStrategyModel(), user_id=5
            )
        assert captured['profile'] == 'conservative'
        assert captured['user_id'] == 5
        assert result['message'] == '无可用标的'

    asyncio.run(_run())


def test_optional_profile_and_auto_trade_job_payload() -> None:
    assert _optional_profile({}) is None
    assert _optional_profile({'profile': 'balanced'}) == 'balanced'
    assert _parse_scan_args() == (None, None)
    assert _parse_scan_args('aggressive', userId=7) == ('aggressive', 7)


def test_auto_trade_job_omits_profile_when_unspecified(monkeypatch) -> None:
    captured: dict = {}

    async def fake_enqueue(job_type, payload=None):
        captured['type'] = job_type
        captured['payload'] = payload
        return True

    monkeypatch.setattr(JobQueue, 'enqueue', fake_enqueue)

    async def _run() -> None:
        await run_auto_trade_scan_job()

    asyncio.run(_run())
    assert captured['type'] == 'auto_trade_scan'
    assert captured['payload'] == {}


def test_strategy_run_job_uses_each_user_bind() -> None:
    async def _run() -> None:
        calls = []

        async def fake_distinct(_db):
            return [3, 8]

        async def fake_run(db, run_model, user_id=None):
            calls.append((user_id, run_model.profile))
            return {'userId': user_id, 'profile': run_model.profile}

        async def fake_resolve(_db, user_id, override=None):
            if override:
                return override
            return {3: 'aggressive', 8: 'conservative'}[int(user_id)]

        class FakeSession:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, *args):
                return False

        with (
            patch('module_market.dao.market_dao.MarketWatchlistDao.distinct_users', fake_distinct),
            patch.object(QuantService, 'run_strategy_services', fake_run),
            patch(
                'module_trade.service.platform_ext_service.PlatformExtService.resolve_profile',
                fake_resolve,
            ),
            patch('config.database.AsyncSessionLocal', FakeSession),
        ):
            out = await _strategy_run({})
        assert out['userCount'] == 2
        assert calls == [(3, 'aggressive'), (8, 'conservative')]

    asyncio.run(_run())


def test_scan_one_user_uses_bound_profile() -> None:
    from module_task.trade_task import _scan_one_user
    from module_trade.service.auto_trade_service import AutoTradeService

    async def _run() -> None:
        captured = {}

        async def fake_cycle(db, **kwargs):
            captured.update(kwargs)
            return {'message': 'ok'}

        with (
            patch.object(
                AutoTradeService,
                'load_user_trade_settings',
                AsyncMock(return_value={'auto_trade_enabled': False}),
            ),
            patch.object(
                PlatformExtService,
                'resolve_profile',
                AsyncMock(return_value='aggressive'),
            ),
            patch.object(AutoTradeService, 'run_watchlist_strategy_cycle', fake_cycle),
        ):
            await _scan_one_user(MagicMock(), 44, None)
        assert captured['strategy_profile'] == 'aggressive'
        assert captured['user_id'] == 44
        assert captured['execute'] is False

    asyncio.run(_run())
