import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_sentiment.service.analyzer_service import ANALYSIS_SYSTEM_PROMPT, SentimentAiAnalyzer
from module_sentiment.service.sentiment_service import SentimentService

SAMPLE_NEWS = [
    {
        'title': '苹果CEO交接提振科技信心',
        'content': '库克交接后市场解读为平稳过渡',
        'source': 'sina',
        'pub_time': '2026-09-02 08:50',
    }
]

SAMPLE_QUOTES = [
    {
        'market': 'US',
        'symbol': 'usINX',
        'name': '标普500',
        'last': 6460.51,
        'prevClose': 6506.62,
        'changePct': -0.71,
        'quoteTime': '2026-09-01 16:00:00',
    },
    {
        'market': 'US',
        'symbol': 'usIXIC',
        'name': '纳斯达克',
        'last': 21412.0,
        'prevClose': 21635.0,
        'changePct': -1.03,
        'quoteTime': '2026-09-01 16:00:00',
    },
    {
        'market': 'US',
        'symbol': 'usDJI',
        'name': '道琼斯',
        'last': 45210.0,
        'prevClose': 45570.0,
        'changePct': -0.79,
        'quoteTime': '2026-09-01 16:00:00',
    },
    {
        'market': 'HK',
        'symbol': 'r_hkHSI',
        'name': '恒生指数',
        'last': 25100.0,
        'prevClose': 25050.0,
        'changePct': 0.20,
        'quoteTime': '2026-09-02 09:00:00',
    },
    {
        'market': 'CN',
        'symbol': 'sh000001',
        'name': '上证指数',
        'last': 3820.0,
        'prevClose': 3810.0,
        'changePct': 0.26,
        'quoteTime': '2026-09-02 09:00:00',
    },
]

OVERNIGHT_PROXIES = [
    {
        'symbol': 'SPY',
        'market': 'US',
        'name': '标普500ETF',
        'last': 6472.0,
        'prevClose': 6460.51,
        'changePct': 0.18,
        'quoteTime': '2026-09-01 21:05:00',
        'source': 'longbridge',
        'volume': 1200000,
    },
    {
        'symbol': 'QQQ',
        'market': 'US',
        'name': '纳指100ETF',
        'last': 21440.0,
        'prevClose': 21412.0,
        'changePct': 0.13,
        'quoteTime': '2026-09-01 21:05:00',
        'source': 'longbridge',
        'volume': 980000,
    },
    {
        'symbol': 'DIA',
        'market': 'US',
        'name': '道指ETF',
        'last': 45240.0,
        'prevClose': 45210.0,
        'changePct': 0.07,
        'quoteTime': '2026-09-01 21:05:00',
        'source': 'longbridge',
        'volume': 410000,
    },
]


def test_system_prompt_requires_live_session_not_stale_regular() -> None:
    assert '【实时/最近交易日指数行情】' in ANALYSIS_SYSTEM_PROMPT
    assert '不可只看新闻' in ANALYSIS_SYSTEM_PROMPT
    assert '0.5%' in ANALYSIS_SYSTEM_PROMPT
    assert '利多' in ANALYSIS_SYSTEM_PROMPT
    assert 'overnight' in ANALYSIS_SYSTEM_PROMPT
    assert 'session' in ANALYSIS_SYSTEM_PROMPT
    assert '禁止用过期的常规盘' in ANALYSIS_SYSTEM_PROMPT
    assert 'pct_chg' in ANALYSIS_SYSTEM_PROMPT


def test_build_user_prompt_labels_session_and_quote_time() -> None:
    sessions = {
        'US': {'market': 'US', 'open': False, 'session': 'overnight', 'live': True},
        'HK': {'market': 'HK', 'open': False, 'session': 'closed', 'live': False},
        'CN': {'market': 'CN', 'open': False, 'session': 'closed', 'live': False},
    }
    merged = SentimentService.merge_us_session_quotes(SAMPLE_QUOTES, OVERNIGHT_PROXIES, 'overnight')
    prompt = SentimentAiAnalyzer._build_user_prompt(SAMPLE_NEWS, index_quotes=merged, sessions=sessions)
    assert prompt.startswith('【实时/最近交易日指数行情】')
    assert '[session=overnight]' in prompt
    assert 'session=overnight quoteTime=2026-09-01 21:05:00' in prompt
    assert 'source=longbridge' in prompt
    assert 'pct_chg=+0.18%' in prompt
    assert 'regular收盘(tencent, stale)' in prompt
    assert 'pct_chg=-0.71%' in prompt
    assert '勿覆盖本会话' in prompt
    assert '苹果CEO交接提振科技信心' in prompt
    assert '未能获取' not in prompt


def test_build_user_prompt_quotes_unavailable() -> None:
    prompt = SentimentAiAnalyzer._build_user_prompt(SAMPLE_NEWS, quotes_unavailable=True)
    assert prompt.startswith('【实时/最近交易日指数行情】')
    assert '未能获取指数行情' in prompt
    assert '苹果CEO交接提振科技信心' in prompt


def test_build_user_prompt_empty_quotes_treated_as_unavailable() -> None:
    prompt = SentimentAiAnalyzer._build_user_prompt(SAMPLE_NEWS, index_quotes=[])
    assert '未能获取指数行情' in prompt


def test_merge_us_session_quotes_prefers_overnight_proxy_over_stale_rth() -> None:
    merged = SentimentService.merge_us_session_quotes(SAMPLE_QUOTES, OVERNIGHT_PROXIES, 'overnight')
    spy = next(item for item in merged if item['symbol'] == 'usINX')
    assert spy['changePct'] == 0.18
    assert spy['session'] == 'overnight'
    assert spy['source'] == 'longbridge'
    assert spy['proxy'] == 'SPY.US'
    assert spy['rthChangePct'] == -0.71
    assert spy['rthQuoteTime'] == '2026-09-01 16:00:00'
    hsi = next(item for item in merged if item['symbol'] == 'r_hkHSI')
    assert hsi['changePct'] == 0.20


def test_merge_us_session_quotes_keeps_tencent_when_us_closed() -> None:
    merged = SentimentService.merge_us_session_quotes(SAMPLE_QUOTES, OVERNIGHT_PROXIES, 'closed')
    spy = next(item for item in merged if item['symbol'] == 'usINX')
    assert spy['changePct'] == -0.71
    assert spy.get('proxy') is None


@pytest.mark.asyncio
async def test_load_analysis_index_context_overlays_live_session_proxies() -> None:
    sessions = {
        'US': {'market': 'US', 'open': False, 'session': 'overnight', 'live': True},
        'HK': {'market': 'HK', 'open': False, 'session': 'closed', 'live': False},
        'CN': {'market': 'CN', 'open': False, 'session': 'closed', 'live': False},
    }
    with (
        patch.object(SentimentService, '_analysis_session_status', return_value=sessions),
        patch(
            'module_sentiment.service.sentiment_service.MarketIndexService.get_in_session_quotes',
            new=AsyncMock(return_value={'items': SAMPLE_QUOTES, 'asOf': '2026-09-02 09:00:00'}),
        ),
        patch.object(
            SentimentService,
            '_fetch_us_session_proxies',
            new=AsyncMock(return_value=OVERNIGHT_PROXIES),
        ),
    ):
        items, unavailable, sess = await SentimentService._load_analysis_index_context(AsyncMock())
    assert unavailable is False
    assert sess['US']['session'] == 'overnight'
    spy = next(item for item in items if item['symbol'] == 'usINX')
    assert spy['changePct'] == 0.18
    assert spy['source'] == 'longbridge'


@pytest.mark.asyncio
async def test_load_analysis_index_context_degrades_on_fetch_failure() -> None:
    sessions = {'US': {'open': False, 'session': 'overnight', 'live': True}}
    with (
        patch.object(SentimentService, '_analysis_session_status', return_value=sessions),
        patch(
            'module_sentiment.service.sentiment_service.MarketIndexService.get_in_session_quotes',
            new=AsyncMock(side_effect=RuntimeError('upstream timeout')),
        ),
    ):
        items, unavailable, sess = await SentimentService._load_analysis_index_context()
    assert items == []
    assert unavailable is True
    assert sess == sessions


@pytest.mark.asyncio
async def test_fetch_us_session_proxies_falls_back_to_lewen_when_admin_tokens_stale() -> None:
    calls: list[int | None] = []

    async def fake_ensure(_db, user_id=None, *, allow_admin_fallback=False):
        calls.append(user_id)

    async def fake_quotes(_pairs):
        if calls and calls[-1] == 100:
            return {'items': OVERNIGHT_PROXIES}
        return {'items': [{'symbol': 'SPY', 'last': 1, 'source': 'tencent', 'changePct': -0.71}]}

    with (
        patch(
            'module_quant.service.longbridge_service.LongbridgeService.ensure_credentials_from_db',
            new=fake_ensure,
        ),
        patch(
            'module_market.service.live_quotes_service.LiveQuotesService.get_quotes',
            new=fake_quotes,
        ),
    ):
        items = await SentimentService._fetch_us_session_proxies(AsyncMock())
    assert 1 in calls or None in calls
    assert 101 in calls
    assert 100 in calls
    assert items[0]['source'] == 'longbridge'
    assert items[0]['changePct'] == 0.18


@pytest.mark.asyncio
async def test_ensure_quote_read_credentials_uses_lewen_when_admin_and_lustone_missing() -> None:
    seen: list[int | None] = []

    async def tracking_ensure(_db, user_id=None, *, allow_admin_fallback=False):
        seen.append(1 if (user_id is None and allow_admin_fallback) else user_id)

    def is_configured() -> bool:
        return seen[-1] == 100 if seen else False

    with (
        patch(
            'module_quant.service.longbridge_service.LongbridgeService.ensure_credentials_from_db',
            new=tracking_ensure,
        ),
        patch(
            'module_quant.service.longbridge_service.LongbridgeService.is_configured',
            side_effect=is_configured,
        ),
        patch(
            'module_quant.dao.quant_dao.QuantLongbridgeConfigDao.list_configured_user_ids',
            new=AsyncMock(return_value=[]),
        ),
    ):
        await SentimentService._ensure_quote_read_credentials(AsyncMock())
    assert seen[-1] == 100
    assert 1 in seen
    assert 101 in seen


@pytest.mark.asyncio
async def test_run_analysis_passes_index_quotes_into_analyzer() -> None:
    news_row = SimpleNamespace(
        news_id=1, source='sina', title='Apple CEO', content='transition', pub_time=None
    )
    analyze_mock = AsyncMock(
        return_value={
            'ok': True,
            'result': {
                'summary': '美股夜盘回暖',
                'us': {'direction': '中性', 'score': 1, 'reason': 'overnight SPY +0.18%'},
                'hk': {'direction': '中性', 'score': 0, 'reason': '震荡'},
                'a': {'direction': '中性', 'score': 0, 'reason': '平开'},
                'risk_events': '无',
            },
            'raw': '{}',
            'error': None,
        }
    )
    db = AsyncMock()
    analysis = SimpleNamespace(analysis_id=99)
    sessions = {'US': {'open': False, 'session': 'overnight'}}
    with (
        patch.object(
            SentimentService,
            'get_ai_config_services',
            new=AsyncMock(return_value=SimpleNamespace(max_news_per_round=20, model_name='demo')),
        ),
        patch.object(SentimentService, '_list_sentiment_ai_candidates', new=AsyncMock(return_value=[SimpleNamespace()])),
        patch.object(
            SentimentService,
            '_model_runtime_config',
            return_value={'baseUrl': 'https://x', 'apiKey': 'k', 'modelName': 'demo', 'temperature': 0.2},
        ),
        patch(
            'module_sentiment.service.sentiment_service.SentimentNewsDao.get_unanalyzed_news',
            new=AsyncMock(return_value=[news_row]),
        ),
        patch.object(
            SentimentService,
            '_load_analysis_index_context',
            new=AsyncMock(return_value=(SAMPLE_QUOTES, False, sessions)),
        ),
        patch('module_sentiment.service.sentiment_service.SentimentAiAnalyzer.analyze', analyze_mock),
        patch(
            'module_sentiment.service.sentiment_service.SentimentAnalysisDao.add_analysis',
            new=AsyncMock(return_value=analysis),
        ),
        patch('module_sentiment.service.sentiment_service.SentimentNewsDao.mark_analyzed', new=AsyncMock()),
    ):
        result = await SentimentService.run_analysis_services(db)

    assert result['analyzed'] == 1
    assert result['analysisId'] == 99
    kwargs = analyze_mock.await_args.kwargs
    assert kwargs['index_quotes'] == SAMPLE_QUOTES
    assert kwargs['quotes_unavailable'] is False
    assert kwargs['sessions'] == sessions


@pytest.mark.asyncio
async def test_run_analysis_continues_when_quotes_fail() -> None:
    news_row = SimpleNamespace(
        news_id=2, source='eastmoney', title='UBS看多A股', content='盈利上修', pub_time=None
    )
    analyze_mock = AsyncMock(
        return_value={
            'ok': True,
            'result': {
                'summary': '行情暂缺',
                'us': {'direction': '中性', 'score': 0, 'reason': '指数行情暂缺'},
                'hk': {'direction': '中性', 'score': 0, 'reason': '指数行情暂缺'},
                'a': {'direction': '利多', 'score': 3, 'reason': '券商上修'},
                'risk_events': '无',
            },
            'raw': '{}',
            'error': None,
        }
    )
    db = AsyncMock()
    analysis = SimpleNamespace(analysis_id=7)
    with (
        patch.object(
            SentimentService,
            'get_ai_config_services',
            new=AsyncMock(return_value=SimpleNamespace(max_news_per_round=20, model_name='demo')),
        ),
        patch.object(SentimentService, '_list_sentiment_ai_candidates', new=AsyncMock(return_value=[SimpleNamespace()])),
        patch.object(
            SentimentService,
            '_model_runtime_config',
            return_value={'baseUrl': 'https://x', 'apiKey': 'k', 'modelName': 'demo', 'temperature': 0.2},
        ),
        patch(
            'module_sentiment.service.sentiment_service.SentimentNewsDao.get_unanalyzed_news',
            new=AsyncMock(return_value=[news_row]),
        ),
        patch.object(
            SentimentService,
            '_load_analysis_index_context',
            new=AsyncMock(return_value=([], True, {'US': {'open': False, 'session': 'overnight'}})),
        ),
        patch('module_sentiment.service.sentiment_service.SentimentAiAnalyzer.analyze', analyze_mock),
        patch(
            'module_sentiment.service.sentiment_service.SentimentAnalysisDao.add_analysis',
            new=AsyncMock(return_value=analysis),
        ),
        patch('module_sentiment.service.sentiment_service.SentimentNewsDao.mark_analyzed', new=AsyncMock()),
    ):
        result = await SentimentService.run_analysis_services(db)

    assert result['analyzed'] == 1
    kwargs = analyze_mock.await_args.kwargs
    assert kwargs['index_quotes'] == []
    assert kwargs['quotes_unavailable'] is True
