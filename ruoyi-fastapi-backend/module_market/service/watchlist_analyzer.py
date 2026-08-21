"""
自选股综合 AI 分析：技术指标 + 长桥资讯 + 舆情，给出可执行建议。
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

import httpx

from utils.log_util import logger

WATCHLIST_SYSTEM_PROMPT = """你是一名资深股票投研分析师。用户会提供某只自选股的技术指标快照、长桥资讯/公告、以及相关舆情。
请综合三方面信息给出合理、克制的短线建议，不要喊单式保证收益。

请严格按以下JSON格式输出（不要输出任何JSON以外的内容，不要用markdown代码块包裹）：
{
  "stance": "偏多|偏空|中性",
  "recommendation": "买入|加仓|持有|观望|减仓|卖出",
  "confidence": 0到100的整数,
  "summary": "综合研判，150字以内",
  "indicator_review": "对价格与技术指标的解读，120字以内",
  "news_review": "对长桥资讯/公告的解读，没有则填'暂无有效资讯'",
  "sentiment_review": "对舆情的解读，没有则填'暂无相关舆情'",
  "operation_advice": "具体操作建议与理由，120字以内",
  "risk_warning": "主要风险，没有则填'无'",
  "key_points": ["要点1", "要点2"]
}"""


class WatchlistAiAnalyzer:
    """自选股综合分析器。"""

    @classmethod
    def _build_user_prompt(cls, context: dict[str, Any]) -> str:
        lines = [
            f"标的：{context.get('name') or ''}（{context.get('symbol')} / {context.get('market')}）",
            f"最新价：{context.get('price')}  涨跌幅：{context.get('changePercent')}%",
            '',
            '【技术指标快照】',
            json.dumps(context.get('indicators') or {}, ensure_ascii=False, default=str)[:4000],
            '',
            '【长桥资讯 / 公告 / 讨论】',
        ]
        news_items = context.get('news') or []
        if not news_items:
            lines.append('（暂无长桥资讯缓存）')
        else:
            for i, item in enumerate(news_items[:8], 1):
                lines.append(
                    f"{i}. [{item.get('contentType') or 'news'}] {item.get('title') or ''} | "
                    f"{(item.get('summary') or '')[:180]}"
                )
        lines.append('')
        lines.append('【相关舆情】')
        sentiment_items = context.get('sentimentNews') or []
        if not sentiment_items:
            lines.append('（暂无匹配舆情）')
        else:
            for i, item in enumerate(sentiment_items[:8], 1):
                lines.append(
                    f"{i}. [{item.get('source') or ''}] {item.get('title') or ''} | "
                    f"{(item.get('content') or '')[:180]}"
                )
        market_sent = context.get('marketSentiment') or {}
        if market_sent:
            lines.append('')
            lines.append('【大盘舆情研判】')
            lines.append(json.dumps(market_sent, ensure_ascii=False, default=str)[:1500])
        lines.append('')
        lines.append('请按系统提示词要求的JSON格式输出分析结果。')
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
                {'role': 'system', 'content': WATCHLIST_SYSTEM_PROMPT},
                {'role': 'user', 'content': cls._build_user_prompt(context)},
            ],
        }
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            raw = data['choices'][0]['message']['content'] or ''
        except Exception as exc:
            logger.error(f'[自选AI分析] 调用模型失败: {exc}')
            return {'ok': False, 'result': None, 'raw': '', 'error': f'调用模型失败: {exc}'}
        try:
            result = cls.parse_response(raw)
            return {'ok': True, 'result': result, 'raw': raw, 'error': None}
        except Exception as exc:
            logger.error(f'[自选AI分析] 解析失败: {exc}, raw={raw[:400]}')
            return {'ok': False, 'result': None, 'raw': raw, 'error': f'解析模型返回失败: {exc}'}


def rule_based_analysis(context: dict[str, Any]) -> dict[str, Any]:
    """AI 不可用时的指标兜底，保证自选页仍有可读建议。"""
    indicators = context.get('indicators') or {}
    close = _to_float(indicators.get('close') or context.get('price'))
    ma = indicators.get('ma') or {}
    rsi_map = indicators.get('rsi') or {}
    macd_map = indicators.get('macd') or {}
    ma20 = _to_float(ma.get('ma20'))
    rsi = _to_float(rsi_map.get('rsi12') or rsi_map.get('rsi6') or rsi_map.get('rsi14'))
    macd = _to_float(macd_map.get('macd') or macd_map.get('hist') or macd_map.get('dif'))
    change = _to_float(context.get('changePercent'))

    stance = '中性'
    recommendation = '观望'
    confidence = 48
    reasons: list[str] = []
    if close is not None and ma20 is not None:
        if close > ma20:
            stance = '偏多'
            recommendation = '持有'
            confidence += 10
            reasons.append('价格位于 MA20 之上')
        else:
            stance = '偏空'
            recommendation = '观望'
            confidence += 6
            reasons.append('价格位于 MA20 之下')
    if macd is not None:
        if macd > 0 and stance == '偏多':
            confidence += 8
            reasons.append('MACD 柱为正')
        elif macd < 0:
            if stance != '偏多':
                stance = '偏空'
            reasons.append('MACD 柱为负')
    if rsi is not None:
        if rsi >= 70:
            recommendation = '减仓'
            confidence = min(75, confidence + 6)
            reasons.append(f'RSI {rsi:.1f} 进入超买')
        elif rsi <= 30:
            recommendation = '关注'
            stance = '中性' if stance == '偏空' else stance
            confidence = min(72, confidence + 6)
            reasons.append(f'RSI {rsi:.1f} 进入超卖')
    if change is not None and change <= -5:
        recommendation = '观望'
        reasons.append(f'当日跌幅 {change:.2f}% 较大')

    news_n = len(context.get('news') or [])
    sent_n = len(context.get('sentimentNews') or [])
    news_review = f'已纳入 {news_n} 条长桥资讯/公告' if news_n else '暂无有效资讯'
    sentiment_review = f'匹配到 {sent_n} 条相关舆情' if sent_n else '暂无相关舆情'
    market_sent = context.get('marketSentiment') or {}
    if market_sent.get('summary'):
        sentiment_review += f"；大盘综述：{str(market_sent.get('summary'))[:80]}"

    if recommendation == '关注':
        recommendation = '观望'

    summary = '；'.join(reasons) if reasons else '指标与资讯样本有限，建议继续观察'
    return {
        'stance': stance,
        'recommendation': recommendation,
        'confidence': max(30, min(80, int(confidence))),
        'summary': summary[:150],
        'indicator_review': summary[:120],
        'news_review': news_review,
        'sentiment_review': sentiment_review[:120],
        'operation_advice': f'当前建议「{recommendation}」，仓位以风控优先，等待更明确的量价与资讯共振。',
        'risk_warning': '未接入大模型，本结论仅为技术指标兜底，不构成投资建议',
        'key_points': reasons[:4] or ['数据不足'],
    }


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == '':
            return None
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result
