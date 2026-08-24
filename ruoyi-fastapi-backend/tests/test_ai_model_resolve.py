import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from module_ai.constant.ai_model_resolve import (
    GROK46_MODEL_CODES,
    grok46_code_for_base_url,
    grok46_provider_for_base_url,
    select_ai_model_row,
)


def _model(**kwargs):
    row = {
        'scope': 'chat',
        'model_code': 'stealth/ox-alpha',
        'base_url': 'https://openrouter.ai/api/v1',
        'api_key': 'enc',
    }
    row.update(kwargs)
    return SimpleNamespace(**row)


def test_grok46_code_follows_provider_url() -> None:
    assert grok46_code_for_base_url('https://openrouter.ai/api/v1') == 'x-ai/grok-4.6'
    assert grok46_provider_for_base_url('https://openrouter.ai/api/v1') == 'OpenRouter'
    assert grok46_code_for_base_url('https://api.x.ai/v1') == 'grok-4.6'
    assert grok46_provider_for_base_url('https://api.x.ai/v1') == 'xAI'


def test_stock_pick_prefers_market_scope_then_grok() -> None:
    ox = _model()
    grok = _model(scope='chat', model_code='x-ai/grok-4.6')
    market_gpt = _model(scope='market', model_code='gpt-4o')
    assert select_ai_model_row([ox], 'market', GROK46_MODEL_CODES) is ox
    assert select_ai_model_row([ox, grok], 'market', GROK46_MODEL_CODES) is grok
    assert select_ai_model_row([ox, grok, market_gpt], 'market', GROK46_MODEL_CODES) is market_gpt
    native = _model(scope='global', model_code='grok-4.6', base_url='https://api.x.ai/v1')
    assert select_ai_model_row([ox, native], 'market', GROK46_MODEL_CODES) is native


def test_incomplete_model_skipped() -> None:
    incomplete = _model(api_key='')
    grok = _model(model_code='grok-4.6')
    assert select_ai_model_row([incomplete, grok], 'market', GROK46_MODEL_CODES) is grok
    assert select_ai_model_row([incomplete], 'market', GROK46_MODEL_CODES) is None
