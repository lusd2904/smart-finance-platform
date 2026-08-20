"""
行情AI分析器：调用OpenAI兼容 chat/completions 接口，对单个标的做趋势研判。
复用ai_models(scope='sentiment')的AI连接配置（base_url/api_key/model_code/temperature）。
参照 module_sentiment/service/analyzer_service.py 的 httpx 调用与JSON解析方式。
"""

import json
import re
from typing import Any

import httpx

from utils.log_util import logger

MARKET_ANALYSIS_SYSTEM_PROMPT = """你是一名资深的技术分析师与操盘手。用户会给你某只股票/指数近期的日K线数据与关键技术指标，请你做出专业的行情研判。

请严格按以下JSON格式输出（不要输出任何JSON以外的内容，不要用markdown代码块包裹）：
{
  "trend": "多头|空头|震荡",
  "trend_summary": "对当前趋势的整体研判，150字以内",
  "support": [支撑位价格数字, ...],
  "resistance": [压力位价格数字, ...],
  "indicator_review": "对MA/MACD/RSI/KDJ/BOLL等指标当前状态的综合解读，120字以内",
  "operation_advice": "操作建议（买入/持有/观望/减仓等）及理由，120字以内",
  "risk_warning": "风险提示，没有则填'无'"
}"""


class MarketAiAnalyzer:
    """
    行情AI分析器
    """

    @classmethod
    def _build_user_prompt(
        cls, symbol: str, name: str, klines: list[dict[str, Any]], indicator_snapshot: dict[str, Any]
    ) -> str:
        """
        构建用户提示词：标的信息 + 近N日K线 + 最新指标快照。
        """
        lines = [f'标的：{name}（{symbol}）', '', '近期日K线（date,open,high,low,close,volume）：']
        lines.extend(
            f"{k.get('date')}, {k.get('open')}, {k.get('high')}, "
            f"{k.get('low')}, {k.get('close')}, {k.get('volume')}"
            for k in klines
        )
        lines.append('')
        lines.append('最新技术指标快照：')
        lines.append(json.dumps(indicator_snapshot, ensure_ascii=False))
        lines.append('')
        lines.append('请按系统提示词要求的JSON格式输出分析结果。')
        return '\n'.join(lines)

    @classmethod
    def _parse_response(cls, text: str) -> dict[str, Any]:
        """
        解析模型返回的JSON（容忍markdown代码块与前后杂质）。
        """
        cleaned = text.strip()
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
        else:
            start, end = cleaned.find('{'), cleaned.rfind('}')
            if start != -1 and end > start:
                cleaned = cleaned[start : end + 1]
        return json.loads(cleaned)

    @classmethod
    async def analyze(
        cls,
        base_url: str,
        api_key: str,
        model_name: str,
        symbol: str,
        name: str,
        klines: list[dict[str, Any]],
        indicator_snapshot: dict[str, Any],
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """
        调用OpenAI兼容 chat/completions 接口执行行情分析。

        :return: {'ok': bool, 'result': dict|None, 'raw': str, 'error': str|None}
        """
        url = base_url.rstrip('/')
        if not url.endswith('/chat/completions'):
            url = f'{url}/chat/completions'
        payload = {
            'model': model_name,
            'temperature': temperature,
            'messages': [
                {'role': 'system', 'content': MARKET_ANALYSIS_SYSTEM_PROMPT},
                {'role': 'user', 'content': cls._build_user_prompt(symbol, name, klines, indicator_snapshot)},
            ],
        }
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            raw = data['choices'][0]['message']['content'] or ''
        except Exception as e:
            logger.error(f'[行情AI分析] 调用模型失败: {e}')
            return {'ok': False, 'result': None, 'raw': '', 'error': f'调用模型失败: {e}'}
        try:
            result = cls._parse_response(raw)
            return {'ok': True, 'result': result, 'raw': raw, 'error': None}
        except Exception as e:
            logger.error(f'[行情AI分析] 解析模型返回失败: {e}, raw={raw[:500]}')
            return {'ok': False, 'result': None, 'raw': raw, 'error': f'解析模型返回失败: {e}'}

    @classmethod
    async def analyze_stream(
        cls,
        base_url: str,
        api_key: str,
        model_name: str,
        symbol: str,
        name: str,
        klines: list[dict[str, Any]],
        indicator_snapshot: dict[str, Any],
        temperature: float = 0.2,
    ):
        """
        调用OpenAI兼容 chat/completions 接口，流式返回行情分析文本片段。
        """
        url = base_url.rstrip('/')
        if not url.endswith('/chat/completions'):
            url = f'{url}/chat/completions'
        payload = {
            'model': model_name,
            'temperature': temperature,
            'stream': True,
            'messages': [
                {'role': 'system', 'content': MARKET_ANALYSIS_SYSTEM_PROMPT},
                {'role': 'user', 'content': cls._build_user_prompt(symbol, name, klines, indicator_snapshot)},
            ],
        }
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                async with client.stream('POST', url, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if line.startswith('data: '):
                            data_str = line[6:].strip()
                            if data_str == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get('choices', [{}])[0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    yield content
                            except Exception:
                                continue
        except Exception as e:
            logger.error(f'[行情AI流式分析] 调用模型异常: {e}')
            yield f'\n[分析异常: {e}]'
