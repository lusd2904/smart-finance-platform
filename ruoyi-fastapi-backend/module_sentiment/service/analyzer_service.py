import json
import re
from typing import Any

import httpx

from utils.log_util import logger

GATEWAY_FAILOVER_CODES = frozenset({502, 503, 524})
HTTP_TOO_MANY_REQUESTS = 429

ANALYSIS_SYSTEM_PROMPT = """你是一名资深宏观与市场策略分析师。用户会给你【实时/最近交易日指数行情】以及一批最新财经舆情快讯。请综合「当前会话指数/成交涨跌」与「舆情」分析对全球主要股指的短期（1-3个交易日）影响，不可只看新闻。

请严格按以下JSON格式输出（不要输出任何JSON以外的内容，不要用markdown代码块包裹）：
{
  "summary": "本批舆情与指数行情的整体综述，150字以内",
  "us": {"direction": "利多|利空|中性", "score": -10到10的数字, "reason": "对美股三大指数（道琼斯、纳斯达克、标普500）的影响分析，100字以内"},
  "hk": {"direction": "利多|利空|中性", "score": -10到10的数字, "reason": "对港股恒生指数的影响分析，100字以内"},
  "a": {"direction": "利多|利空|中性", "score": -10到10的数字, "reason": "对A股上证指数、深证成指的影响分析，100字以内"},
  "risk_events": "值得重点关注的风险事件或催化剂，没有则填'无'"
}

评分标准：
- score 为影响强度，正数利多负数利空，绝对值越大影响越强；0为中性。
- 必须同时结合指数行情与舆情。若某市场【当前会话】主要指数（或代理ETF）平均涨跌幅偏空（例如 |avg pct_chg|≥0.5% 且为下跌），不得输出「利多」，除非舆情有明确、可验证的对冲利好；该市场 reason 必须引用当前会话 pct_chg 与 session。
- 美股会话为 overnight / pre / regular / post / closed。必须使用提示中标注的当前会话实时涨跌（session + quoteTime）。若当前为 overnight、pre 或 post，禁止用过期的常规盘（regular）pct_chg 覆盖本会话走势。
- 仅当美股 session=closed（周末等无成交）时，才把最近一次常规交易日收盘视为近24小时趋势。
- 若提示中写明指数行情不可用，则仅基于舆情分析，并在理由中注明行情暂缺。"""


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
        """构建【实时/最近交易日指数行情】前缀，供模型与舆情一并打分。"""
        lines = ['【实时/最近交易日指数行情】']
        if quotes_unavailable or not index_quotes:
            lines.append(
                '本次未能获取指数行情（数据源暂不可用），请仅基于下方舆情分析，并在理由中注明指数行情暂缺。'
            )
            return '\n'.join(lines)
        lines.append(
            '以下为最新有效报价。盘中与美股延长时段（pre/post/overnight）为当前会话实时（含成交），'
            '已标注 session 与 quoteTime。评分必须用当前会话行；'
            '若美股处于 overnight/pre/post，禁止用过期 regular 收盘 pct_chg 覆盖本会话走势。'
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
                proxy = item.get('proxy')
                if proxy:
                    symbol = f'{symbol} / {proxy}'
                last = cls._format_quote_num(item.get('last'))
                prev_close = cls._format_quote_num(item.get('prevClose'))
                pct_chg = cls._format_quote_pct(item.get('changePct'))
                quote_time = item.get('quoteTime') or '--'
                item_session = item.get('session') or session_tag or '--'
                source = item.get('source') or ''
                extra = f' session={item_session} quoteTime={quote_time}'
                if source:
                    extra += f' source={source}'
                volume = item.get('volume')
                if volume not in (None, ''):
                    extra += f' volume={volume}'
                lines.append(
                    f'- {name} ({symbol}): last={last} prevClose={prev_close} pct_chg={pct_chg}{extra}'
                )
                rth_pct = item.get('rthChangePct')
                rth_time = item.get('rthQuoteTime')
                if rth_pct is not None or rth_time:
                    rth_pct_text = cls._format_quote_pct(rth_pct)
                    rth_time_text = rth_time or '--'
                    lines.append(
                        f'  regular收盘(tencent, stale): pct_chg={rth_pct_text} quoteTime={rth_time_text} — 勿覆盖本会话'
                    )
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
