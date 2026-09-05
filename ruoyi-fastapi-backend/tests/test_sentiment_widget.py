import os
import sys

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from module_sentiment.controller.sentiment_widget_controller import _widget_cors_headers
from module_sentiment.service.sentiment_service import SentimentService


def test_widget_cors_echoes_allowlisted_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        'module_sentiment.controller.sentiment_widget_controller._cors_allow_origins',
        lambda: ['https://fin.example.com'],
    )
    allowed = MagicMock()
    allowed.headers.get.return_value = 'https://fin.example.com'
    blocked = MagicMock()
    blocked.headers.get.return_value = 'https://evil.example'
    none = MagicMock()
    none.headers.get.return_value = None
    assert _widget_cors_headers(allowed)['Access-Control-Allow-Origin'] == 'https://fin.example.com'
    assert _widget_cors_headers(blocked) == {}
    assert _widget_cors_headers(none) == {}


@pytest.mark.asyncio
async def test_analysis_trend_preserves_null_scores() -> None:
    """趋势接口把缺失市场分原样返回 None，不填 0；图表靠 connectNulls 跨点连线。"""
    # DAO 按 create_time 降序；service 再 reverse 成图表用的由旧到新。
    rows = [
        type(
            'Row',
            (),
            {'analysis_id': 2, 'create_time': None, 'us_score': None, 'hk_score': 40, 'a_score': None},
        )(),
        type(
            'Row',
            (),
            {'analysis_id': 1, 'create_time': None, 'us_score': 70, 'hk_score': None, 'a_score': 20},
        )(),
    ]
    with patch(
        'module_sentiment.service.sentiment_service.SentimentAnalysisDao.get_recent_analysis',
        new=AsyncMock(return_value=rows),
    ):
        trend = await SentimentService.get_analysis_trend_services(AsyncMock(), 24)

    assert [item['usScore'] for item in trend] == [70, None]
    assert [item['hkScore'] for item in trend] == [None, 40]
    assert [item['aScore'] for item in trend] == [20, None]


def test_normalize_direction() -> None:
    assert SentimentService._normalize_direction('利多') == 'up'
    assert SentimentService._normalize_direction('bearish') == 'down'
    assert SentimentService._normalize_direction('中性') == 'flat'
    assert SentimentService._normalize_direction('') == ''


def test_parse_risk_events_json_and_plain() -> None:
    assert SentimentService._parse_risk_events('["地缘风险","流动性收紧"]') == ['地缘风险', '流动性收紧']
    assert SentimentService._parse_risk_events('事件A\n事件B；事件C') == ['事件A', '事件B', '事件C']


@pytest.mark.asyncio
async def test_widget_dashboard_aggregates_mocked_services() -> None:
    stats = {
        'total': 100,
        'today': 5,
        'unanalyzed': 3,
        'latestAnalysis': None,
    }
    latest_page = type(
        'Page',
        (),
        {
            'rows': [
                {
                    'analysisId': 9,
                    'createTime': '2026-08-24 12:00:00',
                    'summary': '市场情绪偏暖',
                    'usDirection': '利多',
                    'usScore': 72,
                    'usReason': '科技领涨',
                    'hkDirection': '中性',
                    'hkScore': 50,
                    'hkReason': '震荡',
                    'aDirection': '利空',
                    'aScore': 38,
                    'aReason': '地产承压',
                    'riskEvents': '["美联储讲话"]',
                    'modelName': 'gpt-test',
                    'status': '0',
                }
            ]
        },
    )()
    trend_row = type(
        'Row',
        (),
        {'create_time': None, 'us_score': 70, 'hk_score': 51, 'a_score': 40},
    )()
    index_items = [
        {
            'market': 'US',
            'symbol': 'usINX',
            'name': '标普500',
            'last': 5500.12,
            'prevClose': 5480.0,
            'changePct': 0.37,
            'quoteTime': '2026-08-24 10:30:00',
        }
    ]
    sessions = {
        'US': {'market': 'US', 'open': True, 'localTime': '2026-08-24 10:30:00', 'timezone': 'America/New_York'},
        'HK': {'market': 'HK', 'open': False, 'localTime': '2026-08-24 22:30:00', 'timezone': 'Asia/Hong_Kong'},
        'CN': {'market': 'CN', 'open': False, 'localTime': '2026-08-24 22:30:00', 'timezone': 'Asia/Shanghai'},
    }

    with (
        patch.object(SentimentService, 'get_stats_services', new=AsyncMock(return_value=stats)),
        patch.object(SentimentService, 'get_analysis_list_services', new=AsyncMock(return_value=latest_page)),
        patch(
            'module_sentiment.service.sentiment_service.SentimentAnalysisDao.get_recent_analysis',
            new=AsyncMock(return_value=[trend_row]),
        ),
        patch('module_sentiment.service.sentiment_service.format_beijing_datetime', return_value='2026-08-24 11:00:00'),
        patch(
            'module_sentiment.service.sentiment_service.MarketIndexService.get_in_session_quotes',
            new=AsyncMock(return_value={'items': index_items, 'asOf': '2026-08-24 10:30:00', 'cached': False}),
        ),
        patch('module_sentiment.service.sentiment_service.list_session_status', return_value=sessions),
    ):
        payload = await SentimentService.get_widget_dashboard_services(AsyncMock(), trend_limit=24)

    assert payload['stats'] == {'total': 100, 'today': 5, 'unanalyzed': 3}
    assert payload['summary'] == '市场情绪偏暖'
    assert payload['riskEvents'] == ['美联储讲话']
    assert payload['markets'][0]['directionNorm'] == 'up'
    assert payload['markets'][2]['directionNorm'] == 'down'
    assert payload['latest']['analysisId'] == 9
    assert len(payload['trend']) == 1
    assert payload['trend'][0]['usScore'] == 70
    assert payload['indexes'] == index_items
    assert payload['indexesAsOf'] == '2026-08-24 10:30:00'
    assert payload['indexesCached'] is False
    assert payload['sessions'] == sessions


@pytest.mark.asyncio
async def test_widget_dashboard_indexes_empty_when_no_session() -> None:
    sessions = {
        'US': {'market': 'US', 'open': False, 'localTime': '2026-08-24 02:00:00', 'timezone': 'America/New_York'},
        'HK': {'market': 'HK', 'open': False, 'localTime': '2026-08-24 14:00:00', 'timezone': 'Asia/Hong_Kong'},
        'CN': {'market': 'CN', 'open': False, 'localTime': '2026-08-24 14:00:00', 'timezone': 'Asia/Shanghai'},
    }

    with (
        patch.object(SentimentService, 'get_stats_services', new=AsyncMock(return_value={'total': 0, 'today': 0, 'unanalyzed': 0})),
        patch.object(
            SentimentService,
            'get_analysis_list_services',
            new=AsyncMock(return_value=type('Page', (), {'rows': []})()),
        ),
        patch(
            'module_sentiment.service.sentiment_service.SentimentAnalysisDao.get_recent_analysis',
            new=AsyncMock(return_value=[]),
        ),
        patch('module_sentiment.service.sentiment_service.format_beijing_datetime', return_value='2026-08-24 11:00:00'),
        patch(
            'module_sentiment.service.sentiment_service.MarketIndexService.get_in_session_quotes',
            new=AsyncMock(return_value={'items': [], 'asOf': '2026-08-24 11:00:00', 'cached': True}),
        ),
        patch('module_sentiment.service.sentiment_service.list_session_status', return_value=sessions),
    ):
        payload = await SentimentService.get_widget_dashboard_services(AsyncMock(), trend_limit=24)

    assert payload['indexes'] == []
    assert payload['indexesCached'] is True
    assert payload['sessions'] == sessions


@pytest.mark.asyncio
async def test_widget_dashboard_indexes_degrade_on_fetch_failure() -> None:
    sessions = {
        'US': {'market': 'US', 'open': True, 'localTime': '2026-08-24 10:30:00', 'timezone': 'America/New_York'},
        'HK': {'market': 'HK', 'open': False, 'localTime': '2026-08-24 22:30:00', 'timezone': 'Asia/Hong_Kong'},
        'CN': {'market': 'CN', 'open': False, 'localTime': '2026-08-24 22:30:00', 'timezone': 'Asia/Shanghai'},
    }

    with (
        patch.object(SentimentService, 'get_stats_services', new=AsyncMock(return_value={'total': 0, 'today': 0, 'unanalyzed': 0})),
        patch.object(
            SentimentService,
            'get_analysis_list_services',
            new=AsyncMock(return_value=type('Page', (), {'rows': []})()),
        ),
        patch(
            'module_sentiment.service.sentiment_service.SentimentAnalysisDao.get_recent_analysis',
            new=AsyncMock(return_value=[]),
        ),
        patch('module_sentiment.service.sentiment_service.format_beijing_datetime', return_value='2026-08-24 11:00:00'),
        patch(
            'module_sentiment.service.sentiment_service.MarketIndexService.get_in_session_quotes',
            new=AsyncMock(side_effect=RuntimeError('upstream timeout')),
        ),
        patch('module_sentiment.service.sentiment_service.list_session_status', return_value=sessions),
    ):
        payload = await SentimentService.get_widget_dashboard_services(AsyncMock(), trend_limit=24)

    assert payload['indexes'] == []
    assert payload['indexesCached'] is False
    assert payload['sessions'] == sessions
