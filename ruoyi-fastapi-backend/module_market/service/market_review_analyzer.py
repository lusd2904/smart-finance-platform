"""三市场收盘复盘：指数/代表股 + 资讯 + 舆情，生成当日报告。"""

from __future__ import annotations

import json
from typing import Any

import httpx

from module_market.service.watchlist_analyzer import WatchlistAiAnalyzer
from utils.log_util import logger

MARKET_REVIEW_SYSTEM_PROMPT = """你是一名资深多市场策略分析师。用户会提供某一个市场（美股/港股/A股）收盘后的指数或代表股涨跌、涨跌家数、财经资讯和舆情。
请写一份克制、可执行的收盘复盘，不要喊单保证收益。

请严格按以下JSON格式输出（不要输出任何JSON以外的内容，不要用markdown代码块包裹）：
{
  "title": "不超过24字的当日标题",
  "stance": "偏多|偏空|中性",
  "score": 0到100的整数（50为中性，越高越偏多）,
  "summary": "当日复盘，220字以内",
  "index_review": "对指数或代表股的解读，120字以内",
  "news_review": "对资讯的解读，没有则填'暂无有效资讯'",
  "sentiment_review": "对舆情的解读，没有则填'暂无相关舆情'",
  "outlook": "次日关注点，80字以内",
  "risk_warning": "主要风险，没有则填'无'",
  "key_points": ["要点1", "要点2", "要点3"]
}"""


class MarketReviewAiAnalyzer:
    @classmethod
    def _build_user_prompt(cls, context: dict[str, Any]) -> str:
        lines = [
            f"市场：{context.get('marketLabel')}（{context.get('market')}）",
            f"交易日：{context.get('tradeDate')}",
            f"上涨家数：{context.get('upCount')}  下跌家数：{context.get('downCount')}  样本：{context.get('sampleCount')}",
            '',
            '【指数 / 代表股】',
            json.dumps(context.get('benchmarks') or [], ensure_ascii=False, default=str)[:2500],
            '',
            '【财经资讯】',
        ]
        news = context.get('news') or []
        if not news:
            lines.append('（暂无资讯）')
        else:
            for i, item in enumerate(news[:8], 1):
                lines.append(f"{i}. {item.get('headline') or item.get('title') or ''} | {(item.get('summary') or '')[:160]}")
        lines.append('')
        lines.append('【相关舆情】')
        sentiment = context.get('sentiment') or []
        if not sentiment:
            lines.append('（暂无匹配舆情）')
        else:
            for i, item in enumerate(sentiment[:8], 1):
                lines.append(f"{i}. [{item.get('source') or ''}] {item.get('title') or ''}")
        lines.append('')
        lines.append('请按系统提示词要求的JSON格式输出收盘复盘。')
        return '\n'.join(lines)

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
                {'role': 'system', 'content': MARKET_REVIEW_SYSTEM_PROMPT},
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
            logger.error(f'[市场复盘] 调用模型失败: {exc}')
            return {'ok': False, 'result': None, 'raw': '', 'error': f'调用模型失败: {exc}'}
        try:
            result = WatchlistAiAnalyzer.parse_response(raw)
            return {'ok': True, 'result': result, 'raw': raw, 'error': None}
        except Exception as exc:
            logger.error(f'[市场复盘] 解析失败: {exc}, raw={raw[:400]}')
            return {'ok': False, 'result': None, 'raw': raw, 'error': f'解析模型返回失败: {exc}'}


def rule_based_market_review(context: dict[str, Any]) -> dict[str, Any]:
    benches = context.get('benchmarks') or []
    changes = []
    for row in benches:
        try:
            changes.append(float(row.get('changeRate')))
        except (TypeError, ValueError):
            continue
    avg = sum(changes) / len(changes) if changes else 0.0
    up = int(context.get('upCount') or 0)
    down = int(context.get('downCount') or 0)
    sample = max(int(context.get('sampleCount') or 0), 1)
    breadth = (up - down) / sample
    if avg > 0.4 and breadth >= 0:
        stance = '偏多'
        score = min(82, 55 + int(avg * 8) + int(breadth * 10))
    elif avg < -0.4 and breadth <= 0:
        stance = '偏空'
        score = max(18, 45 + int(avg * 8) + int(breadth * 10))
    else:
        stance = '中性'
        score = 50 + int(avg * 6)
    score = max(0, min(100, score))
    label = context.get('marketLabel') or context.get('market')
    trade_date = context.get('tradeDate') or ''
    names = '、'.join(f"{b.get('name')} {b.get('changeText') or ''}" for b in benches[:3]) or '代表标的数据不足'
    return {
        'title': f'{label}{trade_date}收盘复盘',
        'stance': stance,
        'score': score,
        'summary': (
            f'{label} {trade_date} 收盘：代表组合均涨跌 {avg:+.2f}%，'
            f'样本上涨 {up} / 下跌 {down}。立场{stance}。资讯与舆情见下方，模型未配置时为指标兜底。'
        ),
        'index_review': names,
        'news_review': '暂无有效资讯' if not (context.get('news') or []) else f"收录 {(len(context.get('news') or []))} 条资讯",
        'sentiment_review': '暂无相关舆情'
        if not (context.get('sentiment') or [])
        else f"匹配 {(len(context.get('sentiment') or []))} 条舆情",
        'outlook': '关注量能能否持续以及隔夜外盘指引。',
        'risk_warning': '规则兜底仅供参考，不构成投资建议。',
        'key_points': [f'均涨跌{avg:+.2f}%', f'涨{up}/跌{down}', stance],
    }
