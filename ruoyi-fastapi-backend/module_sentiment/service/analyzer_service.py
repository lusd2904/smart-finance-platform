import json
import re
from typing import Any

import httpx

from utils.log_util import logger

GATEWAY_FAILOVER_CODES = frozenset({502, 503, 524})
HTTP_TOO_MANY_REQUESTS = 429

ANALYSIS_SYSTEM_PROMPT = """你是一名资深宏观与市场策略分析师。用户会给你【分时线截至分析时刻】快照以及一批财经舆情快讯。请综合「截至 asOf 的分时涨跌」与「舆情」分析对全球主要股指的短期（1-3个交易日）影响，不可只看新闻，也不可用当前最新 tick。

请严格按以下JSON格式输出（不要输出任何JSON以外的内容，不要用markdown代码块包裹）：
{
  "summary": "本批舆情与分时快照的整体综述，150字以内",
  "us": {"direction": "利多|利空|中性", "score": 0到100的数字, "reason": "对美股三大指数（道琼斯、纳斯达克、标普500 / SPY QQQ DIA）的影响分析，100字以内"},
  "hk": {"direction": "利多|利空|中性", "score": 0到100的数字, "reason": "对港股恒生指数的影响分析，100字以内"},
  "a": {"direction": "利多|利空|中性", "score": 0到100的数字, "reason": "对A股上证指数、深证成指的影响分析，100字以内"},
  "risk_events": "值得重点关注的风险事件或催化剂，没有则填'无'"
}

评分标准：
- score 为 0–100 百分制：0 极空、50 中性、100 极多。不要输出 -10..+10。
- 必须同时结合分时快照与舆情。若某市场截至 asOf 的会话 pct_chg 偏空（例如 |avg pct_chg|≥0.5% 且为下跌），不得输出「利多」，除非舆情有明确、可验证的对冲利好；reason 必须引用该 pct_chg、session 与 quoteTime。
- 美股用 SPY/QQQ/DIA 分时，不是现金指数最新价。会话为 overnight / pre / regular / post / closed。只用提示中 asOf 之前的分钟K，禁止用分析时刻之后或“现在”的最新成交。
- 回放历史分析时同样按该条 create_time/asOf 重放当时的分时，而不是今天的最新 tick。
- 若提示中写明分时不可用，则仅基于舆情分析，并在理由中注明行情暂缺。"""


_MARKET_PROMPT_LABELS = {
    'US': '美股三大指数',
    'HK': '港股指数',
    'CN': 'A股指数',
}
_MARKET_PROMPT_ORDER = ('US', 'HK', 'CN')


class SentimentAiAnalyzer:
    """
    舆情AI分析器：调用OpenAI兼容接口分析舆情对大盘的影响
    """

    @staticmethod
    def _format_quote_num(value: Any) -> str:
        if value is None or value == '':
            return '--'
        return str(value)

    @staticmethod
    def _format_quote_pct(value: Any) -> str:
        if value is None or value == '':
            return '--'
        try:
            return f'{float(value):+.2f}%'
        except (TypeError, ValueError):
            return str(value)

    @classmethod
    def _format_index_quotes_block(
        cls,
        index_quotes: list[dict[str, Any]] | None,
        quotes_unavailable: bool = False,
        sessions: dict[str, dict[str, Any]] | None = None,
    ) -> str:
        """构建【分时线截至分析时刻】前缀，供模型与舆情一并打分。"""
        lines = ['【分时线截至分析时刻】']
        if quotes_unavailable or not index_quotes:
            lines.append(
                '本次未能获取分时K（Influx minute_kline 暂不可用），请仅基于下方舆情分析，并在理由中注明分时行情暂缺。'
            )
            return '\n'.join(lines)
        lines.append(
            '以下为 Influx minute_kline 截至 asOf 的会话快照（不是腾讯/长桥当前最新价）。'
            '美股为 SPY/QQQ/DIA 分时。评分必须用 asOf 之前最后一根分时的 pct_chg；'
            '回放历史行时按该 asOf 重放，禁止用今天的最新 tick。'
        )
        grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in _MARKET_PROMPT_ORDER}
        for item in index_quotes:
            market = str(item.get('market') or '').upper()
            if market in grouped:
                grouped[market].append(item)
        session_map = sessions or {}
        for market in _MARKET_PROMPT_ORDER:
            items = grouped[market]
            if not items:
                continue
            sess = session_map.get(market) or {}
            session_tag = str(sess.get('session') or items[0].get('session') or '').strip()
            header = f'{_MARKET_PROMPT_LABELS[market]}（{market}）'
            if session_tag:
                header = f'{header} [session={session_tag}]'
            lines.append(header)
            for item in items:
                name = item.get('name') or item.get('symbol') or ''
                symbol = item.get('symbol') or ''
                last = cls._format_quote_num(item.get('last'))
                prev_close = cls._format_quote_num(item.get('prevClose'))
                pct_chg = cls._format_quote_pct(item.get('changePct'))
                quote_time = item.get('quoteTime') or '--'
                item_session = item.get('session') or session_tag or '--'
                source = item.get('source') or 'minute_kline'
                as_of = item.get('asOf') or ''
                extra = f' session={item_session} quoteTime={quote_time} source={source}'
                if as_of:
                    extra += f' asOf={as_of}'
                lines.append(
                    f'- {name} ({symbol}): last={last} prevClose={prev_close} pct_chg={pct_chg}{extra}'
                )
                path = item.get('path')
                if path:
                    lines.append(f'  path: {path}')
        return '\n'.join(lines)

    @classmethod
    def _build_user_prompt(
        cls,
        news_list: list[dict[str, Any]],
        index_quotes: list[dict[str, Any]] | None = None,
        quotes_unavailable: bool = False,
        sessions: dict[str, dict[str, Any]] | None = None,
    ) -> str:
        """
        构建用户提示词（先指数行情，再正文摘要，避免只有标题）
        """
        lines = [
            cls._format_index_quotes_block(
                index_quotes, quotes_unavailable=quotes_unavailable, sessions=sessions
            ),
            '',
            '以下是最新采集的财经舆情快讯（含正文，请基于正文分析，不要只看标题）：',
            '',
        ]
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
        index_quotes: list[dict[str, Any]] | None = None,
        quotes_unavailable: bool = False,
        sessions: dict[str, dict[str, Any]] | None = None,
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
                {
                    'role': 'user',
                    'content': cls._build_user_prompt(
                        news_list,
                        index_quotes=index_quotes,
                        quotes_unavailable=quotes_unavailable,
                        sessions=sessions,
                    ),
                },
            ],
        }
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        # 代理/慢模型可能较久：连接 30s，总超时 300s
        timeout = httpx.Timeout(300.0, connect=30.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == HTTP_TOO_MANY_REQUESTS:
                    retry_after = resp.headers.get('Retry-After') or '60'
                    logger.warning('[舆情AI分析] 模型限流 429，不重试')
                    return {
                        'ok': False,
                        'result': None,
                        'raw': '',
                        'error': '模型调用过于频繁，请稍后再试',
                        'code': HTTP_TOO_MANY_REQUESTS,
                        'retryAfter': int(retry_after) if str(retry_after).isdigit() else 60,
                    }
                if resp.status_code in GATEWAY_FAILOVER_CODES:
                    logger.warning(f'[舆情AI分析] 网关错误 {resp.status_code}，可切换模型重试')
                    return {
                        'ok': False,
                        'result': None,
                        'raw': (resp.text or '')[:2000],
                        'error': f'网关错误 {resp.status_code}',
                        'code': resp.status_code,
                    }
                resp.raise_for_status()
                data = resp.json()
            raw = data['choices'][0]['message']['content'] or ''
        except httpx.HTTPStatusError as e:
            if e.response is not None and e.response.status_code == HTTP_TOO_MANY_REQUESTS:
                retry_after = e.response.headers.get('Retry-After') or '60'
                return {
                    'ok': False,
                    'result': None,
                    'raw': '',
                    'error': '模型调用过于频繁，请稍后再试',
                    'code': HTTP_TOO_MANY_REQUESTS,
                    'retryAfter': int(retry_after) if str(retry_after).isdigit() else 60,
                }
            status = e.response.status_code if e.response is not None else None
            logger.error(f'[舆情AI分析] 调用模型失败: {e}')
            return {
                'ok': False,
                'result': None,
                'raw': '',
                'error': f'调用模型失败: {e}',
                'code': status,
            }
        except Exception as e:
            logger.error(f'[舆情AI分析] 调用模型失败: {e}')
            return {'ok': False, 'result': None, 'raw': '', 'error': f'调用模型失败: {e}', 'code': None}
        try:
            result = cls._parse_response(raw)
            return {'ok': True, 'result': result, 'raw': raw, 'error': None}
        except Exception as e:
            logger.error(f'[舆情AI分析] 解析模型返回失败: {e}, raw={raw[:500]}')
            return {'ok': False, 'result': None, 'raw': raw, 'error': f'解析模型返回失败: {e}'}
