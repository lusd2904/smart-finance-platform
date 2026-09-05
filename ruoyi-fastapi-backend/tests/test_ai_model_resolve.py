import os
import random
import sys
from types import SimpleNamespace
from unittest.mock import patch

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


def test_stock_pick_scope_pool_wins_before_preferred_codes() -> None:
    ox = _model()
    grok = _model(scope='chat', model_code='x-ai/grok-4.6')
    market_gpt = _model(scope='market', model_code='gpt-4o')
    # No market-scope row: fall through to preferred_codes / chat / all-complete.
    assert select_ai_model_row([ox], 'market', GROK46_MODEL_CODES) is ox
    assert select_ai_model_row([ox, grok], 'market', GROK46_MODEL_CODES) is grok
    # Scope pool wins first; preferred_codes only apply when that pool is empty.
    assert select_ai_model_row([ox, grok, market_gpt], 'market', GROK46_MODEL_CODES) is market_gpt
    native = _model(scope='global', model_code='grok-4.6', base_url='https://api.x.ai/v1')
    assert select_ai_model_row([ox, native], 'market', GROK46_MODEL_CODES) is native


def test_preferred_scope_random_among_scope_pool() -> None:
    kimi = _model(scope='market', model_code='kimi-k3')
    gpt = _model(scope='market', model_code='gpt-4o')
    opus = _model(scope='sentiment', model_code='claude-opus-5')
    expected_pool = [kimi, gpt]
    random.seed(0)
    picked = select_ai_model_row([opus, kimi, gpt], 'market', GROK46_MODEL_CODES)
    assert picked in expected_pool
    for seed in range(16):
        random.seed(seed)
        assert select_ai_model_row([opus, kimi, gpt], 'market', GROK46_MODEL_CODES) in expected_pool


def test_preferred_scope_passes_scope_pool_to_random_choice() -> None:
    kimi = _model(scope='market', model_code='kimi-k3')
    gpt = _model(scope='market', model_code='gpt-4o')
    chat = _model(scope='chat', model_code='x-ai/grok-4.6')
    captured: list[list] = []

    def fake_choice(seq):
        captured.append(list(seq))
        return seq[0]

    with patch('module_ai.constant.ai_model_resolve.random.choice', side_effect=fake_choice):
        result = select_ai_model_row([chat, kimi, gpt], 'market', GROK46_MODEL_CODES)

    assert result is kimi
    assert captured == [[kimi, gpt]]


def test_preferred_codes_random_when_scope_pool_empty() -> None:
    ox = _model()
    grok_or = _model(scope='chat', model_code='x-ai/grok-4.6')
    grok_native = _model(scope='global', model_code='grok-4.6', base_url='https://api.x.ai/v1')
    expected_pool = [grok_or, grok_native]
    random.seed(1)
    picked = select_ai_model_row([ox, grok_or, grok_native], 'market', GROK46_MODEL_CODES)
    assert picked in expected_pool


def test_falls_back_random_global_then_chat() -> None:
    g1 = _model(scope='global', model_code='gpt-4o')
    g2 = _model(scope='global', model_code='kimi-k3')
    chat = _model(scope='chat', model_code='x-ai/grok-4.6')
    expected_pool = [g1, g2]
    random.seed(2)
    picked = select_ai_model_row([chat, g1, g2], 'sentiment')
    assert picked in expected_pool


def test_falls_back_random_among_all_complete() -> None:
    quant = _model(scope='quant', model_code='qwen')
    other = _model(scope='other', model_code='glm')
    expected_pool = [quant, other]
    random.seed(3)
    picked = select_ai_model_row([quant, other], 'sentiment')
    assert picked in expected_pool


def test_incomplete_model_skipped() -> None:
    incomplete = _model(api_key='')
    grok = _model(model_code='grok-4.6')
    assert select_ai_model_row([incomplete, grok], 'market', GROK46_MODEL_CODES) is grok
    assert select_ai_model_row([incomplete], 'market', GROK46_MODEL_CODES) is None
