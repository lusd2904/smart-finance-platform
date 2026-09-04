import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from module_sentiment.dao.sentiment_dao import SentimentAnalysisDao, SentimentNewsDao
from module_sentiment.entity.vo.sentiment_vo import SentimentAiConfigModel
from module_sentiment.service.analyzer_service import SentimentAiAnalyzer
from module_sentiment.service.sentiment_service import SentimentService

_OK_AI_RESULT = {
    'ok': True,
    'result': {
        'summary': 'ok',
        'us': {'direction': '中性', 'score': 0, 'reason': 'r'},
        'hk': {'direction': '中性', 'score': 0, 'reason': 'r'},
        'a': {'direction': '中性', 'score': 0, 'reason': 'r'},
        'risk_events': '无',
    },
    'raw': '{}',
    'error': None,
}
_LIMITED_AI_RESULT = {
    'ok': False,
    'result': None,
    'raw': '',
    'error': '模型调用过于频繁，请稍后再试',
    'code': 429,
    'retryAfter': 30,
}


def _complete_model(
    model_id: int,
    scope: str,
    model_code: str,
    *,
    api_key: str = 'enc',
    base_url: str = 'https://example.test/v1',
) -> SimpleNamespace:
    return SimpleNamespace(
        model_id=model_id,
        scope=scope,
        model_code=model_code,
        api_key=api_key,
        base_url=base_url,
        temperature=0.2,
    )


def _runtime(model: SimpleNamespace) -> dict:
    return {
        'baseUrl': model.base_url or '',
        'apiKey': 'plain-key',
        'modelName': model.model_code or '',
        'temperature': 0.2,
    }


def test_order_candidates_uses_shuffled_scope_pools() -> None:
    models = [
        _complete_model(1, 'sentiment', 'opus-5'),
        _complete_model(2, 'sentiment', 'gpt-4o'),
        _complete_model(3, 'global', 'grok-4.6'),
        _complete_model(4, 'global', 'gemini'),
        _complete_model(5, 'chat', 'llama'),
        _complete_model(6, 'market', 'market-only'),
        _complete_model(7, 'sentiment', '', api_key='', base_url=''),
    ]
    first_codes: set[str] = set()
    for _ in range(40):
        ordered = SentimentService._order_sentiment_ai_candidates(models)
        codes = [model.model_code for model in ordered]
        assert set(codes[:2]) == {'opus-5', 'gpt-4o'}
        assert set(codes[2:4]) == {'grok-4.6', 'gemini'}
        assert codes[4] == 'llama'
        assert codes[5] == 'market-only'
        assert '' not in codes
        first_codes.add(codes[0])
    assert first_codes == {'opus-5', 'gpt-4o'}


@pytest.mark.asyncio
async def test_run_analysis_failsover_429_to_next_model() -> None:
    first = _complete_model(1, 'sentiment', 'nvidia-limited')
    second = _complete_model(2, 'global', 'backup-ok')
    news = SimpleNamespace(news_id=11, source='eastmoney', title='t', content='c', pub_time=None)
    config = SentimentAiConfigModel(maxNewsPerRound=10, modelName='fallback-name')
    analyze = AsyncMock(side_effect=[_LIMITED_AI_RESULT, _OK_AI_RESULT])
    add_analysis = AsyncMock(return_value=SimpleNamespace(analysis_id=99))
    db = AsyncMock()

    with (
        patch.object(SentimentService, 'get_ai_config_services', AsyncMock(return_value=config)),
        patch.object(SentimentService, '_list_sentiment_ai_candidates', AsyncMock(return_value=[first, second])),
        patch.object(SentimentService, '_model_runtime_config', side_effect=_runtime),
        patch.object(SentimentNewsDao, 'get_unanalyzed_news', AsyncMock(return_value=[news])),
        patch.object(SentimentAiAnalyzer, 'analyze', analyze),
        patch.object(SentimentAnalysisDao, 'add_analysis', add_analysis),
        patch.object(SentimentNewsDao, 'mark_analyzed', AsyncMock()),
    ):
        result = await SentimentService.run_analysis_services(db)

    assert result['analyzed'] == 1
    assert result['analysisId'] == 99
    assert result.get('rateLimited') is None
    assert analyze.await_count == 2
    assert analyze.await_args_list[0].kwargs['model_name'] == 'nvidia-limited'
    assert analyze.await_args_list[1].kwargs['model_name'] == 'backup-ok'
    assert add_analysis.await_args.args[1]['model_name'] == 'backup-ok'


@pytest.mark.asyncio
async def test_run_analysis_all_429_sets_rate_limited() -> None:
    first = _complete_model(1, 'sentiment', 'model-a')
    second = _complete_model(2, 'global', 'model-b')
    news = SimpleNamespace(news_id=11, source='eastmoney', title='t', content='c', pub_time=None)
    config = SentimentAiConfigModel(maxNewsPerRound=10, modelName='fallback-name')
    analyze = AsyncMock(side_effect=[_LIMITED_AI_RESULT, dict(_LIMITED_AI_RESULT, retryAfter=45)])
    add_analysis = AsyncMock()
    db = AsyncMock()

    with (
        patch.object(SentimentService, 'get_ai_config_services', AsyncMock(return_value=config)),
        patch.object(SentimentService, '_list_sentiment_ai_candidates', AsyncMock(return_value=[first, second])),
        patch.object(SentimentService, '_model_runtime_config', side_effect=_runtime),
        patch.object(SentimentNewsDao, 'get_unanalyzed_news', AsyncMock(return_value=[news])),
        patch.object(SentimentAiAnalyzer, 'analyze', analyze),
        patch.object(SentimentAnalysisDao, 'add_analysis', add_analysis),
    ):
        result = await SentimentService.run_analysis_services(db)

    assert result['rateLimited'] is True
    assert result['analyzed'] == 0
    assert result['analysisId'] is None
    assert result['retryAfter'] == 45
    assert analyze.await_count == 2
    add_analysis.assert_not_awaited()
