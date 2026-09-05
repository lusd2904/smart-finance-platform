import hashlib
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus
from xml.etree import ElementTree

import httpx

from utils.log_util import logger

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
)

# 默认启用：东财/新浪 + 中文免费源
DEFAULT_SOURCES = ['eastmoney', 'sina', 'ths', 'wallstreetcn', 'google_news']


def _make_hash(source: str, title: str) -> str:
    """根据来源+标题生成去重hash"""
    return hashlib.md5(f'{source}:{title}'.encode()).hexdigest()


def _strip_html(text: str) -> str:
    """去除HTML标签"""
    return re.sub(r'<[^>]+>', '', text or '').strip()


def _parse_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value or '').strip()
    if not text:
        return datetime.now()
    # ISO8601 / BJT offset，如 2026-09-04T23:39:00+08:00
    try:
        iso = text.replace('Z', '+00:00')
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is not None:
            # 统一存 naive：保留墙上时间（BJT 常见）
            return dt.replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        pass
    for fmt in (
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%a, %d %b %Y %H:%M:%S %Z',
        '%a, %d %b %Y %H:%M:%S %z',
        '%Y-%m-%d',
    ):
        try:
            return datetime.strptime(text[:31], fmt)
        except (ValueError, TypeError):
            continue
    try:
        # RFC822 常见无时区尾巴
        return datetime.strptime(text[:25], '%a, %d %b %Y %H:%M:%S')
    except (ValueError, TypeError):
        return datetime.now()


def _normalize_topics(topics: Any) -> list[str]:
    if topics is None:
        return []
    if isinstance(topics, list):
        return [str(t).strip() for t in topics if str(t).strip()]
    text = str(topics).strip()
    if not text:
        return []
    parts = re.split(r'[,，|/]+', text)
    return [p.strip() for p in parts if p.strip()]


def _map_x_monitor_item(item: Any) -> dict[str, Any] | None:
    """
    将 X监测器条目映射为 sentiment_news 行。
    source 一律强制为 x_monitor；有 url 时 uniq_hash = md5(url)。
    """
    if not isinstance(item, dict):
        return None
    text = str(item.get('text') or '').strip()
    url = str(item.get('url') or '').strip() or None
    if not text and not url:
        return None

    first_line = (text.splitlines()[0] if text else '') or (url or '')
    title = first_line[:80] if first_line else (url or 'x_monitor')[:80]
    topics = _normalize_topics(item.get('topics'))
    content = text or title
    if topics:
        tag = ','.join(topics)
        content = f'{content}\n[topics:{tag}]' if content else f'[topics:{tag}]'

    author = str(item.get('author') or '').strip()
    if author and author not in content:
        content = f'@{author}: {content}'

    uniq = hashlib.md5(url.encode()).hexdigest() if url else _make_hash('x_monitor', text or title)

    return {
        'source': 'x_monitor',
        'title': title[:500],
        'content': content[:4000],
        'url': url,
        'pub_time': _parse_time(item.get('posted_at')),
        'uniq_hash': uniq,
    }


class SentimentCollector:
    """
    舆情采集器：免费公开接口采集财经快讯（中文优先）
    """

    @classmethod
    async def fetch_eastmoney(cls, client: httpx.AsyncClient, page_size: int = 50) -> list[dict[str, Any]]:
        """东方财富 7x24 全球财经快讯"""
        req_trace = int(datetime.now().timestamp() * 1000)
        url = (
            'https://np-listapi.eastmoney.com/comm/web/getFastNewsList'
            f'?client=web&biz=web_724&fastColumn=102&sortEnd=&pageSize={page_size}&req_trace={req_trace}'
        )
        resp = await client.get(url, headers={'User-Agent': USER_AGENT, 'Referer': 'https://kuaixun.eastmoney.com/'})
        resp.raise_for_status()
        data = resp.json()
        items = (data.get('data') or {}).get('fastNewsList') or []
        result = []
        for item in items:
            title = _strip_html(item.get('title') or item.get('summary') or '')
            if not title:
                continue
            show_time = item.get('showTime') or ''
            try:
                pub_time = datetime.strptime(show_time, '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                pub_time = datetime.now()
            code = item.get('code') or ''
            content = _strip_html(item.get('summary') or item.get('content') or title)
            result.append(
                {
                    'source': 'eastmoney',
                    'title': title[:500],
                    'content': content[:4000],
                    'url': f'https://finance.eastmoney.com/a/{code}.html' if code else None,
                    'pub_time': pub_time,
                    'uniq_hash': _make_hash('eastmoney', title),
                }
            )
        return result

    @classmethod
    async def fetch_sina(cls, client: httpx.AsyncClient, page_size: int = 50) -> list[dict[str, Any]]:
        """新浪财经 7x24 直播快讯"""
        url = (
            'https://zhibo.sina.com.cn/api/zhibo/feed'
            f'?page=1&page_size={page_size}&zhibo_id=152&tag_id=0&dire=f&dpc=1'
        )
        resp = await client.get(url, headers={'User-Agent': USER_AGENT, 'Referer': 'https://finance.sina.com.cn/7x24/'})
        resp.raise_for_status()
        data = resp.json()
        feed = (((data.get('result') or {}).get('data') or {}).get('feed') or {}).get('list') or []
        result = []
        for item in feed:
            title = _strip_html(item.get('rich_text') or '')
            if not title:
                continue
            try:
                pub_time = datetime.strptime(item.get('create_time') or '', '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                pub_time = datetime.now()
            docurl = None
            try:
                import json as _json

                ext = _json.loads(item.get('ext') or '{}')
                docurl = ext.get('docurl') or None
            except (ValueError, TypeError):
                docurl = None
            result.append(
                {
                    'source': 'sina',
                    'title': title[:500],
                    'content': title[:4000],
                    'url': docurl,
                    'pub_time': pub_time,
                    'uniq_hash': _make_hash('sina', title),
                }
            )
        return result

    @classmethod
    async def fetch_ths(cls, client: httpx.AsyncClient, page_size: int = 40) -> list[dict[str, Any]]:
        """
        同花顺财经快讯（公开接口，中文，含正文摘要）
        """
        url = 'https://news.10jqka.com.cn/tapp/news/push/stock/'
        resp = await client.get(
            url,
            params={'page': '1', 'tag': '', 'track': 'website', 'pagesize': str(page_size)},
            headers={'User-Agent': USER_AGENT, 'Referer': 'https://news.10jqka.com.cn/'},
        )
        resp.raise_for_status()
        data = resp.json()
        items = (data.get('data') or {}).get('list') or []
        result = []
        for item in items:
            title = _strip_html(item.get('title') or '')
            content = _strip_html(item.get('digest') or item.get('content') or title)
            if not title:
                continue
            ctime = item.get('ctime') or item.get('rtime') or item.get('time')
            if isinstance(ctime, (int, float)) or (isinstance(ctime, str) and str(ctime).isdigit()):
                ts = float(ctime)
                pub_time = datetime.fromtimestamp(ts if ts < 1e12 else ts / 1000)
            else:
                pub_time = _parse_time(ctime)
            link = item.get('url') or item.get('shareUrl')
            if link and str(link).startswith('https:/') and not str(link).startswith('https://'):
                # 接口偶发返回 https:/ 缺斜杠
                link = str(link).replace('https:/', 'https://', 1)
            result.append(
                {
                    'source': 'ths',
                    'title': title[:500],
                    'content': content[:4000],
                    'url': link,
                    'pub_time': pub_time,
                    'uniq_hash': _make_hash('ths', str(item.get('id') or title)),
                }
            )
        return result

    @classmethod
    async def fetch_cls(cls, client: httpx.AsyncClient, page_size: int = 40) -> list[dict[str, Any]]:
        """
        财联社电报兼容入口：官方接口常需签名，失败时回退同花顺。
        """
        # 优先用同花顺（稳定、中文正文摘要），避免签名接口 404/10012
        return await cls.fetch_ths(client, page_size=page_size)

    @classmethod
    async def fetch_wallstreetcn(cls, client: httpx.AsyncClient, page_size: int = 40) -> list[dict[str, Any]]:
        """
        华尔街见闻实时快讯（公开 API，中文）
        """
        url = 'https://api-one-wscn.awtmt.com/apiv1/content/lives'
        resp = await client.get(
            url,
            params={'channel': 'global-channel', 'limit': str(page_size), 'client': 'pc'},
            headers={'User-Agent': USER_AGENT, 'Referer': 'https://wallstreetcn.com/live/global'},
        )
        resp.raise_for_status()
        data = resp.json()
        items = ((data.get('data') or {}).get('items')) or []
        result = []
        for item in items:
            content_obj = item.get('content_text') or item.get('content') or item.get('title') or ''
            if isinstance(content_obj, dict):
                content = _strip_html(content_obj.get('text') or content_obj.get('content') or '')
            else:
                content = _strip_html(str(content_obj))
            title = _strip_html(item.get('title') or content[:80])
            if not title and not content:
                continue
            if not title:
                title = content[:80]
            ts = item.get('display_time') or item.get('created_at') or item.get('score')
            if isinstance(ts, (int, float)):
                pub_time = datetime.fromtimestamp(ts if ts < 1e12 else ts / 1000)
            else:
                pub_time = _parse_time(ts)
            uri = item.get('uri') or item.get('url')
            if uri and not str(uri).startswith('http'):
                uri = f'https://wallstreetcn.com{uri}'
            result.append(
                {
                    'source': 'wallstreetcn',
                    'title': title[:500],
                    'content': (content or title)[:4000],
                    'url': uri,
                    'pub_time': pub_time,
                    'uniq_hash': _make_hash('wallstreetcn', str(item.get('id') or title)),
                }
            )
        return result

    @classmethod
    async def fetch_google_news(cls, client: httpx.AsyncClient, page_size: int = 30) -> list[dict[str, Any]]:
        """
        Google News RSS（中文财经关键词，免费）
        """
        queries = [
            '美股 OR 纳斯达克 OR 美联储',
            'A股 OR 上证 OR 港股',
            '原油 OR 黄金 OR 通胀',
        ]
        result: list[dict[str, Any]] = []
        for q in queries:
            url = (
                'https://news.google.com/rss/search'
                f'?q={quote_plus(q)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans'
            )
            try:
                resp = await client.get(url, headers={'User-Agent': USER_AGENT})
                resp.raise_for_status()
                root = ElementTree.fromstring(resp.text)
            except Exception as e:
                logger.warning(f'[舆情采集] google_news 查询失败 q={q}: {e}')
                continue
            for item in root.findall('.//channel/item')[: max(5, page_size // len(queries))]:
                title = _strip_html(item.findtext('title') or '')
                if not title:
                    continue
                summary = _strip_html(item.findtext('description') or '') or title
                link = (item.findtext('link') or '').strip() or None
                pub = _parse_time(item.findtext('pubDate'))
                result.append(
                    {
                        'source': 'google_news',
                        'title': title[:500],
                        'content': summary[:4000],
                        'url': link,
                        'pub_time': pub,
                        'uniq_hash': _make_hash('google_news', title),
                    }
                )
        return result

    @classmethod
    async def fetch_jin10(cls, client: httpx.AsyncClient, page_size: int = 40) -> list[dict[str, Any]]:
        """
        金十数据快讯（公开接口，中文；失败时静默跳过）
        """
        url = 'https://flash-api.jin10.com/get_flash_list'
        resp = await client.get(
            url,
            params={'channel': '-8200', 'vip': '1', 'max_time': ''},
            headers={
                'User-Agent': USER_AGENT,
                'Referer': 'https://www.jin10.com/',
                'x-app-id': 'bVBF4FyRTn5NJF5n',
                'x-version': '1.0.0',
            },
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get('data') or []
        result = []
        for item in items[:page_size]:
            # data 可能是 {type, data: {content, title, ...}}
            payload = item.get('data') if isinstance(item.get('data'), dict) else item
            if not isinstance(payload, dict):
                continue
            content = _strip_html(payload.get('content') or payload.get('title') or '')
            title = _strip_html(payload.get('title') or content[:80])
            if not title and not content:
                continue
            if not title:
                title = content[:80]
            ts = item.get('time') or payload.get('time')
            pub_time = _parse_time(ts)
            result.append(
                {
                    'source': 'jin10',
                    'title': title[:500],
                    'content': (content or title)[:4000],
                    'url': 'https://www.jin10.com/',
                    'pub_time': pub_time,
                    'uniq_hash': _make_hash('jin10', str(item.get('id') or title)),
                }
            )
        return result

    @classmethod
    async def collect(cls, enabled_sources: list[str] | None = None) -> list[dict[str, Any]]:
        """
        从所有启用的数据源采集快讯

        :param enabled_sources: 启用的数据源列表，None 表示默认免费源集合
        :return: 采集到的资讯列表（已按 hash 准备好，未与库去重）
        """
        sources = enabled_sources or list(DEFAULT_SOURCES)
        fetchers = {
            'eastmoney': cls.fetch_eastmoney,
            'sina': cls.fetch_sina,
            'ths': cls.fetch_ths,
            'cls': cls.fetch_cls,  # 兼容旧配置，内部回退 ths
            'wallstreetcn': cls.fetch_wallstreetcn,
            'google_news': cls.fetch_google_news,
            'jin10': cls.fetch_jin10,
        }
        all_news: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=25, follow_redirects=True, trust_env=False) as client:
            for name in sources:
                key = (name or '').strip().lower()
                if not key:
                    continue
                fetcher = fetchers.get(key)
                if not fetcher:
                    logger.warning(f'[舆情采集] 未知数据源: {key}')
                    continue
                try:
                    news = await fetcher(client)
                    logger.info(f'[舆情采集] {key} 获取 {len(news)} 条')
                    all_news.extend(news)
                except Exception as e:
                    logger.warning(f'[舆情采集] {key} 采集失败: {e}')
        seen: set[str] = set()
        deduped = []
        for news in all_news:
            h = news.get('uniq_hash')
            if not h or h in seen:
                continue
            seen.add(h)
            deduped.append(news)
        return deduped
