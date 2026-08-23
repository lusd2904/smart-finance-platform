"""业务侧解析 AI 模型：不依赖数据库与环境变量，便于单测。"""

from collections.abc import Sequence
from typing import Any

MARKET_SCOPE = 'market'
GROK46_MODEL_CODES = ('grok-4.6', 'x-ai/grok-4.6')


def grok46_code_for_base_url(base_url: str | None) -> str:
    url = (base_url or '').lower()
    if 'openrouter' in url:
        return 'x-ai/grok-4.6'
    return 'grok-4.6'


def grok46_provider_for_base_url(base_url: str | None) -> str:
    url = (base_url or '').lower()
    if 'openrouter' in url:
        return 'OpenRouter'
    return 'xAI'


def _is_complete_model(model: Any) -> bool:
    return bool(getattr(model, 'base_url', None) and getattr(model, 'api_key', None) and getattr(model, 'model_code', None))


def _code_matches(model_code: str | None, preferred_codes: Sequence[str]) -> bool:
    code = (model_code or '').strip().lower()
    if not code:
        return False
    prefs = [(item or '').strip().lower() for item in preferred_codes if item]
    if code in prefs:
        return True
    return any(code.endswith('/' + item) or item.endswith('/' + code) for item in prefs)


def select_ai_model_row(
    models: Sequence[Any],
    preferred_scope: str = 'sentiment',
    preferred_codes: Sequence[str] | None = None,
) -> Any | None:
    """
    从已启用模型中选出业务用连接。
    顺序：preferred_scope -> preferred_codes（如 grok-4.6）-> global -> chat -> 第一条完整配置。
    调用方应已按 model_sort, model_id 排好序。
    """
    complete = [model for model in models if _is_complete_model(model)]
    if not complete:
        return None

    def first_in_scope(scope: str) -> Any | None:
        if not scope:
            return None
        return next((model for model in complete if (getattr(model, 'scope', None) or '') == scope), None)

    hit = first_in_scope(preferred_scope)
    if hit:
        return hit
    if preferred_codes:
        for model in complete:
            if _code_matches(getattr(model, 'model_code', None), preferred_codes):
                return model
    for scope in ('global', 'chat'):
        if scope == preferred_scope:
            continue
        hit = first_in_scope(scope)
        if hit:
            return hit
    return complete[0]
