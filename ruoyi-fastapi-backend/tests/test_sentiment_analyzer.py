import os
import sys
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_sentiment.entity.vo.sentiment_vo import SentimentAnalysisModel, normalize_sentiment_score
from module_sentiment.service.analyzer_service import ANALYSIS_SYSTEM_PROMPT, SentimentAiAnalyzer
from module_sentiment.service.sentiment_service import SentimentService
from utils.time_format_util import BEIJING_TZ

SAMPLE_NEWS = [
    {
        'title': '苹果CEO交接提振科技信心',
        'content': '库克交接后市场解读为平稳过渡',
        'source': 'sina',
        'pub_time': '2026-09-02 08:50',
    }
]

SAMPLE_MINUTE_SNAPS = [
    {
        'market': 'US',
        'symbol': 'SPY',
        'name': '标普500ETF',
        'last': 647.20,
        'prevClose': 646.05,
        'changePct': 0.18,
        'quoteTime': '2026-09-02 08:59',
        'session': 'overnight',
        'source': 'minute_kline',
        'path': '08:55:646.8,08:59:647.2',
        'asOf': '2026-09-02 09:00:00',
    },
    {
        'market': 'US',
        'symbol': 'QQQ',
        'name': '纳指100ETF',
        'last': 478.10,
        'prevClose': 477.50,
        'changePct': 0.13,
        'quoteTime': '2026-09-02 08:59',
        'session': 'overnight',
        'source': 'minute_kline',
        'asOf': '2026-09-02 09:00:00',
    },
    {
        'market': 'US',
        'symbol': 'DIA',
        'name': '道指ETF',
        'last': 452.40,
        'prevClose': 452.10,
        'changePct': 0.07,
        'quoteTime': '2026-09-02 08:59',
        'session': 'overnight',
        'source': 'minute_kline',
        'asOf': '2026-09-02 09:00:00',
    },
    {
        'market': 'HK',
        'symbol': 'HSI.HK',
        'name': '恒生指数',
        'last': 25100.0,
        'prevClose': 25050.0,
        'changePct': 0.20,
        'quoteTime': '2026-09-02 09:00',
        'session': 'closed',
        'source': 'minute_kline',
        'asOf': '2026-09-02 09:00:00',
    },
    {
        'market': 'CN',
        'symbol': 'sh000001',
        'name': '上证指数',
        'last': 3820.0,
        'prevClose': 3810.0,
        'changePct': 0.26,
        'quoteTime': '2026-09-02 09:00',
        'session': 'closed',
        'source': 'minute_kline',
        'asOf': '2026-09-02 09:00:00',
    },
]

# 09:00 北京 = 21:00 ET(夏令)；夜盘从 20:00 ET = 08:00 北京起
_AS_OF_0900 = datetime(2026, 9, 2, 9, 0, 0)
_AS_OF_0830 = datetime(2026, 9, 2, 8, 30, 0)
_AS_OF_1300 = datetime(2026, 9, 2, 13, 0, 0)  # 01:00 ET，夜盘跨午夜
_MINUTE_BARS = [
    {'date': '2026-09-01 04:00', 'open': 99.0, 'high': 100.0, 'low': 99.0, 'close': 100.0, 'volume': 1},
    {'date': '2026-09-02 08:00', 'open': 100.1, 'high': 100.5, 'low': 100.0, 'close': 100.2, 'volume': 1},
    {'date': '2026-09-02 08:30', 'open': 100.2, 'high': 101.0, 'low': 100.2, 'close': 100.8, 'volume': 1},
    {'date': '2026-09-02 09:00', 'open': 100.8, 'high': 101.3, 'low': 100.8, 'close': 101.2, 'volume': 1},
    {'date': '2026-09-02 09:05', 'open': 101.2, 'high': 110.0, 'low': 101.0, 'close': 110.0, 'volume': 1},
]


def test_normalize_sentiment_score_matches_flutter() -> None:
    assert normalize_sentiment_score(-10) == 0
    assert normalize_sentiment_score(0) == 50
    assert normalize_sentiment_score(10) == 100
    assert normalize_sentiment_score(4) == 70
    assert normalize_sentiment_score(-2) == 40
    assert normalize_sentiment_score(72.5) == 72.5
    assert normalize_sentiment_score(60) == 60
    assert normalize_sentiment_score(None) is None
    dumped = SentimentAnalysisModel.model_validate({'usScore': 4, 'hkScore': -2, 'aScore': 72.5}).model_dump(
        by_alias=True
    )
    assert dumped['usScore'] == 70
    assert dumped['hkScore'] == 40
    assert dumped['aScore'] == 72.5


def test_system_prompt_uses_minute_asof_and_0_100() -> None:
    assert '0–100' in ANALYSIS_SYSTEM_PROMPT or '0到100' in ANALYSIS_SYSTEM_PROMPT
    assert '不要输出 -10' in ANALYSIS_SYSTEM_PROMPT
    assert 'SPY' in ANALYSIS_SYSTEM_PROMPT and 'QQQ' in ANALYSIS_SYSTEM_PROMPT and 'DIA' in ANALYSIS_SYSTEM_PROMPT
    assert 'minute' in ANALYSIS_SYSTEM_PROMPT.lower() or '分时' in ANALYSIS_SYSTEM_PROMPT
    assert 'asOf' in ANALYSIS_SYSTEM_PROMPT
    assert '不可只看新闻' in ANALYSIS_SYSTEM_PROMPT
    assert '0.5%' in ANALYSIS_SYSTEM_PROMPT
    assert 'overnight' in ANALYSIS_SYSTEM_PROMPT
    assert '最新 tick' in ANALYSIS_SYSTEM_PROMPT or '当前最新' in ANALYSIS_SYSTEM_PROMPT


def test_build_user_prompt_labels_minute_kline_asof() -> None:
    sessions = {
        'US': {'market': 'US', 'open': False, 'session': 'overnight', 'live': True},
        'HK': {'market': 'HK', 'open': False, 'session': 'closed', 'live': False},
        'CN': {'market': 'CN', 'open': False, 'session': 'closed', 'live': False},
    }
    prompt = SentimentAiAnalyzer._build_user_prompt(
        SAMPLE_NEWS, index_quotes=SAMPLE_MINUTE_SNAPS, sessions=sessions
    )
    assert prompt.startswith('【分时线截至分析时刻】')
    assert 'minute_kline' in prompt
    assert 'asOf=2026-09-02 09:00:00' in prompt
    assert 'SPY' in prompt and 'QQQ' in prompt and 'DIA' in prompt
    assert 'pct_chg=+0.18%' in prompt
    assert 'session=overnight quoteTime=2026-09-02 08:59' in prompt
    assert 'path: 08:55:646.8,08:59:647.2' in prompt
    assert '苹果CEO交接提振科技信心' in prompt
    assert '未能获取' not in prompt
    assert 'longbridge' not in prompt
    assert 'tencent' not in prompt.lower()


def test_build_user_prompt_quotes_unavailable() -> None:
    prompt = SentimentAiAnalyzer._build_user_prompt(SAMPLE_NEWS, quotes_unavailable=True)
    assert prompt.startswith('【分时线截至分析时刻】')
    assert '未能获取分时' in prompt or 'minute_kline 暂不可用' in prompt
    assert '苹果CEO交接提振科技信心' in prompt


def test_build_user_prompt_empty_quotes_treated_as_unavailable() -> None:
    prompt = SentimentAiAnalyzer._build_user_prompt(SAMPLE_NEWS, index_quotes=[])
    assert '未能获取分时' in prompt or 'minute_kline 暂不可用' in prompt


def test_snapshot_from_minute_bars_cuts_off_after_as_of() -> None:
    snap = SentimentService.snapshot_from_minute_bars(
        _MINUTE_BARS,
        as_of=_AS_OF_0900,
        session='overnight',
        market='US',
        symbol='SPY',
        name='标普500ETF',
    )
    assert snap is not None
    assert snap['last'] == 101.2
    assert snap['changePct'] == 1.2
    assert snap['quoteTime'] == '2026-09-02 09:00'
    assert snap['source'] == 'minute_kline'
    assert snap['symbol'] == 'SPY'
    assert '09:05' not in (snap.get('path') or '')
    assert snap['asOf'].startswith('2026-09-02 09:00')


def test_snapshot_replays_historical_as_of_not_later_bars() -> None:
    earlier = SentimentService.snapshot_from_minute_bars(
        _MINUTE_BARS,
        as_of=_AS_OF_0830,
        session='overnight',
        market='US',
        symbol='SPY',
        name='标普500ETF',
    )
    later = SentimentService.snapshot_from_minute_bars(
        _MINUTE_BARS,
        as_of=_AS_OF_0900,
        session='overnight',
        market='US',
        symbol='SPY',
        name='标普500ETF',
    )
    assert earlier is not None and later is not None
    assert earlier['last'] == 100.8
    assert earlier['changePct'] == 0.8
    assert later['last'] == 101.2
    assert later['changePct'] == 1.2


def test_overnight_session_start_crosses_et_midnight() -> None:
    # 13:00 北京 = 01:00 ET，夜盘起点仍是前一晚 20:00 ET = 08:00 北京
    start = SentimentService._session_start_beijing(_AS_OF_1300, 'US', 'overnight')
    assert start == '2026-09-02 08:00'


def test_query_minute_bars_as_of_uses_exclusive_utc_stop() -> None:
    as_of = datetime(2026, 9, 2, 9, 0, tzinfo=BEIJING_TZ)
    with patch(
        'module_sentiment.service.sentiment_service.InfluxUtil.query_minute_klines',
        return_value=_MINUTE_BARS,
    ) as mocked:
        rows = SentimentService._query_minute_bars_as_of('US', 'SPY', as_of)
    assert rows == _MINUTE_BARS
    _market, symbol, start, stop = mocked.call_args.args
    assert symbol == 'SPY'
    assert start == '2026-08-28T01:00:00Z'
    assert stop == '2026-09-02T01:01:00Z'


@pytest.mark.asyncio
async def test_load_analysis_index_context_uses_spy_qqq_dia_minutes() -> None:
    sessions = {
        'US': {'market': 'US', 'open': False, 'session': 'overnight', 'live': True},
        'HK': {'market': 'HK', 'open': False, 'session': 'closed', 'live': False},
        'CN': {'market': 'CN', 'open': False, 'session': 'closed', 'live': False},
    }

    def fake_query(market: str, symbol: str, _as_of: datetime):
        if market == 'US' and symbol in {'SPY', 'QQQ', 'DIA'}:
            return _MINUTE_BARS
        return []

    with (
        patch.object(SentimentService, '_analysis_session_status', return_value=sessions),
        patch.object(SentimentService, '_query_minute_bars_as_of', side_effect=fake_query),
    ):
        items, unavailable, sess = await SentimentService._load_analysis_index_context(as_of=_AS_OF_0900)
    assert unavailable is False
    assert sess['US']['session'] == 'overnight'
    symbols = {item['symbol'] for item in items}
    assert symbols == {'SPY', 'QQQ', 'DIA'}
    assert all(item['source'] == 'minute_kline' for item in items)
    assert all(item['last'] == 101.2 for item in items)


@pytest.mark.asyncio
async def test_load_analysis_index_context_degrades_when_influx_empty() -> None:
    sessions = {'US': {'open': False, 'session': 'overnight', 'live': True}}
    with (
        patch.object(SentimentService, '_analysis_session_status', return_value=sessions),
        patch.object(SentimentService, '_query_minute_bars_as_of', return_value=[]),
    ):
        items, unavailable, sess = await SentimentService._load_analysis_index_context(as_of=_AS_OF_0900)
    assert items == []
    assert unavailable is True
    assert sess == sessions


@pytest.mark.asyncio
async def test_run_analysis_persists_0_100_and_passes_minute_snaps() -> None:
    news_row = SimpleNamespace(
        news_id=1, source='sina', title='Apple CEO', content='transition', pub_time=None
    )
    analyze_mock = AsyncMock(
        return_value={
            'ok': True,
            'result': {
                'summary': '美股夜盘回暖',
                'us': {'direction': '中性', 'score': 4, 'reason': 'overnight SPY +0.18%'},
                'hk': {'direction': '中性', 'score': -2, 'reason': '震荡'},
                'a': {'direction': '中性', 'score': 72.5, 'reason': '已是百分制'},
                'risk_events': '无',
            },
            'raw': '{}',
            'error': None,
        }
    )
    db = AsyncMock()
    analysis = SimpleNamespace(analysis_id=99)
    sessions = {'US': {'open': False, 'session': 'overnight'}}
    saved: dict = {}

    async def capture_add(_db, record):
        saved.update(record)
        return analysis

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
            new=AsyncMock(return_value=(SAMPLE_MINUTE_SNAPS, False, sessions)),
        ) as load_ctx,
        patch('module_sentiment.service.sentiment_service.SentimentAiAnalyzer.analyze', analyze_mock),
        patch(
            'module_sentiment.service.sentiment_service.SentimentAnalysisDao.add_analysis',
            new=capture_add,
        ),
        patch('module_sentiment.service.sentiment_service.SentimentNewsDao.mark_analyzed', new=AsyncMock()),
    ):
        result = await SentimentService.run_analysis_services(db)

    assert result['analyzed'] == 1
    assert result['analysisId'] == 99
    kwargs = analyze_mock.await_args.kwargs
    assert kwargs['index_quotes'] == SAMPLE_MINUTE_SNAPS
    assert kwargs['quotes_unavailable'] is False
    assert kwargs['sessions'] == sessions
    assert saved['us_score'] == 70
    assert saved['hk_score'] == 40
    assert saved['a_score'] == 72.5
    assert load_ctx.await_args.kwargs.get('as_of') is not None or (
        len(load_ctx.await_args.args) >= 2 and load_ctx.await_args.args[1] is not None
    )


@pytest.mark.asyncio
async def test_run_analysis_continues_when_minutes_missing() -> None:
    news_row = SimpleNamespace(
        news_id=2, source='eastmoney', title='UBS看多A股', content='盈利上修', pub_time=None
    )
    analyze_mock = AsyncMock(
        return_value={
            'ok': True,
            'result': {
                'summary': '行情暂缺',
                'us': {'direction': '中性', 'score': 50, 'reason': '分时行情暂缺'},
                'hk': {'direction': '中性', 'score': 50, 'reason': '分时行情暂缺'},
                'a': {'direction': '利多', 'score': 65, 'reason': '券商上修'},
                'risk_events': '无',
            },
            'raw': '{}',
            'error': None,
        }
    )
    db = AsyncMock()
    analysis = SimpleNamespace(analysis_id=7)
    saved: dict = {}

    async def capture_add(_db, record):
        saved.update(record)
        return analysis

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
            new=capture_add,
        ),
        patch('module_sentiment.service.sentiment_service.SentimentNewsDao.mark_analyzed', new=AsyncMock()),
    ):
        result = await SentimentService.run_analysis_services(db)

    assert result['analyzed'] == 1
    kwargs = analyze_mock.await_args.kwargs
    assert kwargs['index_quotes'] == []
    assert kwargs['quotes_unavailable'] is True
    assert saved['us_score'] == 50
    assert saved['a_score'] == 65
