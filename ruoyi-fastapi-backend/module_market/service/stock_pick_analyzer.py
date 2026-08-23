"""选股短名单 AI：指标 + 开盘指数（若有）+ 三市场舆情。"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from utils.log_util import logger

SYSTEM_PROMPT = """你是二级市场选股助手。综合技术指标、当前舆情、以及仅在开盘时提供的大盘指数，给出克制的短线建议。
休市时没有实时指数，不要编造盘口，只根据指标和舆情判断。

严格输出 JSON（不要 markdown）：
{
  "stance": "偏多|偏空|中性",
  "recommendation": "买入|关注|观望|回避",
  "confidence": 0到100的整数,
  "summary": "综合研判，120字以内",
  "indicator_review": "指标解读，80字以内",
  "sentiment_review": "舆情解读，80字以内",
  "operation_advice": "操作建议，80字以内",
  "risk_warning": "主要风险，没有则填无"
}"""


class StockPickAnalyzer:
    @classmethod
    def _user_prompt(cls, item: dict[str, Any], context: dict[str, Any]) -> str:
        lines = [
            f"标的：{item.get('name') or ''}（{item.get('symbol')} / {item.get('market')}）",
            f"最新价：{item.get('price')}  涨跌：{item.get('changePct')}%  因子分：{item.get('factorScore')}  选股分：{item.get('pickScore')}",
            f"规则信号：{item.get('signal')}  {item.get('reason') or ''}",
            '',
            '【技术指标摘要】',
            json.dumps(item.get('metrics') or {}, ensure_ascii=False, default=str)[:1800],
            '',
            '【市场环境】',
            json.dumps(context.get('markets') or {}, ensure_ascii=False, default=str)[:1800],
            '',
            '【舆情综述】',
            str((context.get('sentiment') or {}).get('summary') or '暂无'),
            '',
            '未开盘的市场已去掉实时指数。请按 JSON 输出。',
        ]
        return '\n'.join(lines)

    @classmethod
    def parse_response(cls, text: str) -> dict[str, Any]:
        cleaned = (text or '').strip()
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
        item: dict[str, Any],
        context: dict[str, Any],
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        url = base_url.rstrip('/')
        if not url.endswith('/chat/completions'):
            url = f'{url}/chat/completions'
        payload = {
            'model': model_name,
            'temperature': temperature,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': cls._user_prompt(item, context)},
            ],
        }
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        last_error = ''
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code == 429:
                        last_error = '429 Too Many Requests'
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                raw = data['choices'][0]['message']['content'] or ''
                break
            except Exception as exc:
                last_error = str(exc)
                logger.warning(f"[选股AI] {item.get('symbol')} 调用失败: {exc}")
                if attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                return {'ok': False, 'error': last_error}
        else:
            return {'ok': False, 'error': last_error}
        try:
            parsed = cls.parse_response(raw)
        except Exception as exc:
            logger.warning(f"[选股AI] {item.get('symbol')} 解析失败: {exc}")
            return {'ok': False, 'error': f'parse: {exc}', 'raw': raw[:500]}
        return {'ok': True, 'result': parsed, 'raw': raw}
