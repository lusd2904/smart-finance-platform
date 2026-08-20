import json
import re
from typing import Any

import httpx

from utils.log_util import logger

ANALYSIS_SYSTEM_PROMPT = """你是一名资深宏观与市场策略分析师。用户会给你一批最新财经舆情快讯，请你综合分析这批舆情对全球主要股指的短期（1-3个交易日）影响。

请严格按以下JSON格式输出（不要输出任何JSON以外的内容，不要用markdown代码块包裹）：
{
  "summary": "本批舆情的整体综述，150字以内",
  "us": {"direction": "利多|利空|中性", "score": -10到10的数字, "reason": "对美股三大指数（道琼斯、纳斯达克、标普500）的影响分析，100字以内"},
  "hk": {"direction": "利多|利空|中性", "score": -10到10的数字, "reason": "对港股恒生指数的影响分析，100字以内"},
  "a": {"direction": "利多|利空|中性", "score": -10到10的数字, "reason": "对A股上证指数、深证成指的影响分析，100字以内"},
  "risk_events": "值得重点关注的风险事件或催化剂，没有则填'无'"
}

评分标准：score为影响强度，正数利多负数利空，绝对值越大影响越强；0为中性。"""


class SentimentAiAnalyzer:
    """
    舆情AI分析器：调用OpenAI兼容接口分析舆情对大盘的影响
    """

    @classmethod
    def _build_user_prompt(cls, news_list: list[dict[str, Any]]) -> str:
        """
        构建用户提示词（带正文摘要，避免只有标题）
        """
        lines = ['以下是最新采集的财经舆情快讯（含正文，请基于正文分析，不要只看标题）：\n']
        for i, news in enumerate(news_list, 1):
            pub_time = news.get('pub_time') or ''
            title = (news.get('title') or '')[:200]
            content = (news.get('content') or '').strip()
            if not content:
                content = title
            # 单条正文控制长度，避免 token 爆掉
            content = content[:600]
            lines.append(f'{i}. [{pub_time}][{news.get("source", "")}] {title}')
            if content and content != title:
                lines.append(f'   正文: {content}')
        lines.append('\n请按系统提示词要求的JSON格式输出分析结果。')
        return '\n'.join(lines)

    @classmethod
    def _parse_response(cls, text: str) -> dict[str, Any]:
        """
        解析模型返回的JSON（容忍markdown代码块与前后杂质）
        """
        cleaned = text.strip()
        # 去掉可能的markdown代码块
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
        else:
            # 截取第一个 { 到最后一个 }
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
        news_list: list[dict[str, Any]],
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """
        调用OpenAI兼容 chat/completions 接口执行分析

        :return: {'ok': bool, 'result': dict|None, 'raw': str, 'error': str|None}
        """
        url = base_url.rstrip('/')
        if not url.endswith('/chat/completions'):
            url = f'{url}/chat/completions'
        payload = {
            'model': model_name,
            'temperature': temperature,
            'messages': [
                {'role': 'system', 'content': ANALYSIS_SYSTEM_PROMPT},
                {'role': 'user', 'content': cls._build_user_prompt(news_list)},
            ],
        }
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        # 代理/慢模型可能较久：连接 30s，总超时 300s
        timeout = httpx.Timeout(300.0, connect=30.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 429:
                    retry_after = resp.headers.get('Retry-After') or '60'
                    logger.warning('[舆情AI分析] 模型限流 429，不重试')
                    return {
                        'ok': False,
                        'result': None,
                        'raw': '',
                        'error': '模型调用过于频繁，请稍后再试',
                        'code': 429,
                        'retryAfter': int(retry_after) if str(retry_after).isdigit() else 60,
                    }
                resp.raise_for_status()
                data = resp.json()
            raw = data['choices'][0]['message']['content'] or ''
        except httpx.HTTPStatusError as e:
            if e.response is not None and e.response.status_code == 429:
                retry_after = e.response.headers.get('Retry-After') or '60'
                return {
                    'ok': False,
                    'result': None,
                    'raw': '',
                    'error': '模型调用过于频繁，请稍后再试',
                    'code': 429,
                    'retryAfter': int(retry_after) if str(retry_after).isdigit() else 60,
                }
            logger.error(f'[舆情AI分析] 调用模型失败: {e}')
            return {'ok': False, 'result': None, 'raw': '', 'error': f'调用模型失败: {e}'}
        except Exception as e:
            logger.error(f'[舆情AI分析] 调用模型失败: {e}')
            return {'ok': False, 'result': None, 'raw': '', 'error': f'调用模型失败: {e}'}
        try:
            result = cls._parse_response(raw)
            return {'ok': True, 'result': result, 'raw': raw, 'error': None}
        except Exception as e:
            logger.error(f'[舆情AI分析] 解析模型返回失败: {e}, raw={raw[:500]}')
            return {'ok': False, 'result': None, 'raw': raw, 'error': f'解析模型返回失败: {e}'}
