import os
import sys

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import AsyncMock, patch

import pytest

from exceptions.exception import ServiceException
from module_sentiment.controller.sentiment_widget_controller import _check_widget_token
from module_sentiment.service.sentiment_service import SentimentService


def test_widget_token_disabled() -> None:
    with patch('module_sentiment.controller.sentiment_widget_controller.AppConfig') as cfg:
        cfg.sentiment_widget_token = ''
        with pytest.raises(ServiceException) as err:
            _check_widget_token('anything')
        assert 'SENTIMENT_WIDGET_TOKEN' in err.value.message


def test_widget_token_invalid() -> None:
    with patch('module_sentiment.controller.sentiment_widget_controller.AppConfig') as cfg:
        cfg.sentiment_widget_token = 'secret-token'
        with pytest.raises(ServiceException) as err:
            _check_widget_token('wrong')
        assert err.value.message == 'Widget 令牌无效'


def test_widget_token_ok() -> None:
    with patch('module_sentiment.controller.sentiment_widget_controller.AppConfig') as cfg:
        cfg.sentiment_widget_token = 'secret-token'
        _check_widget_token('secret-token')


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

    with (
        patch.object(SentimentService, 'get_stats_services', new=AsyncMock(return_value=stats)),
        patch.object(SentimentService, 'get_analysis_list_services', new=AsyncMock(return_value=latest_page)),
        patch(
            'module_sentiment.service.sentiment_service.SentimentAnalysisDao.get_recent_analysis',
            new=AsyncMock(return_value=[trend_row]),
        ),
        patch('module_sentiment.service.sentiment_service.format_beijing_datetime', return_value='2026-08-24 11:00:00'),
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
