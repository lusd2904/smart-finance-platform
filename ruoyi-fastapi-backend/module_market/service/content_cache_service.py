"""
标的公告/资讯/讨论内容缓存：对接长桥 filings/news/topics，优先中文，尽量落正文。
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from module_market.dao.market_dao import SymbolContentCacheDao
from module_quant.service.longbridge_service import LongbridgeService
from utils.log_util import logger

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
)


class SymbolContentService:
    """标的内容缓存服务"""

    TTL_MINUTES = {
        'announcement': 240,
        'news': 60,
        'topic': 30,
    }

    TYPE_ALIASES = {
        'announcement': 'announcement',
        'announcements': 'announcement',
        'filings': 'announcement',
        'news': 'news',
        'topic': 'topic',
        'topics': 'topic',
    }

    # summary 字段存「可展示正文」，加长避免只剩链接
    BODY_MAX_LEN = 12000

    @classmethod
    def normalize_type(cls, content_type: str) -> str:
        key = str(content_type or 'news').strip().lower()
        return cls.TYPE_ALIASES.get(key, 'news')

    @classmethod
    async def get_content(
        cls,
        query_db: AsyncSession,
        symbol: str,
        market: str = 'US',
        content_type: str = 'news',
        limit: int = 20,
        refresh: bool = False,
    ) -> dict[str, Any]:
        symbol = (symbol or '').strip().upper()
        market = (market or 'US').strip().upper()
        content_type = cls.normalize_type(content_type)
        limit = max(1, min(int(limit or 20), 50))

        cached = await SymbolContentCacheDao.get_cached(query_db, symbol, content_type, limit=limit)
        if refresh or not cached:
            await cls.refresh_symbol(query_db, symbol, market, content_types=[content_type])
            cached = await SymbolContentCacheDao.get_cached(query_db, symbol, content_type, limit=limit)

        items = []
        for r in cached:
            body = r.summary or ''
            items.append(
                {
                    'id': r.id,
                    'symbol': r.symbol,
                    'market': r.market,
                    'contentType': r.content_type,
                    'sourceName': r.source_name,
                    'sourceItemId': r.source_item_id,
                    'title': r.title,
                    'summary': body[:500] if body else '',
                    'content': body,
                    'sourceLink': r.source_link,
                    'publishedAt': r.published_at.strftime('%Y-%m-%d %H:%M:%S') if r.published_at else None,
                    'fetchedAt': r.fetched_at.strftime('%Y-%m-%d %H:%M:%S') if r.fetched_at else None,
                }
            )
        return {
            'symbol': symbol,
            'market': market,
            'contentType': content_type,
            'items': items,
            'count': len(items),
            'source': 'cache' if items else 'empty',
        }

    @classmethod
    async def refresh_symbol(
        cls,
        query_db: AsyncSession,
        symbol: str,
        market: str = 'US',
        content_types: list[str] | None = None,
    ) -> int:
        """从长桥刷新内容并写入缓存；正文不足时尝试抓取链接页面。凭据缺失返回 0。"""
        types = [cls.normalize_type(t) for t in (content_types or ['announcement', 'news', 'topic'])]
        await LongbridgeService.ensure_credentials_from_db(query_db)
        if not LongbridgeService.is_configured():
            logger.info(f'[内容缓存] 长桥未配置，跳过 {symbol}')
            return 0

        lb_symbol = LongbridgeService.to_longbridge_symbol(symbol, market)
        # 长桥SDK为同步网络调用，放线程池避免阻塞事件循环
        raw_bundle = await asyncio.get_running_loop().run_in_executor(
            None, LongbridgeService.fetch_symbol_content, lb_symbol, types
        )
        now = datetime.now()
        saved = 0
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, trust_env=False) as client:
            for ctype, items in raw_bundle.items():
                ctype = cls.normalize_type(ctype)
                ttl = cls.TTL_MINUTES.get(ctype, 60)
                expires = now + timedelta(minutes=ttl)
                for raw in items or []:
                    normalized = cls._normalize_item(symbol, market, ctype, raw, now, expires)
                    if not normalized:
                        continue
                    # 正文过短时尝试抓取链接
                    body = normalized.get('summary') or ''
                    link = normalized.get('source_link')
                    if link and len(body) < 80:
                        fetched = await cls._fetch_page_text(client, link)
                        if fetched and len(fetched) > len(body):
                            normalized['summary'] = fetched[: cls.BODY_MAX_LEN]
                    await SymbolContentCacheDao.upsert_item(query_db, normalized)
                    saved += 1
        # 清理过期超过3天的缓存，防止无限堆积
        await SymbolContentCacheDao.prune_expired(query_db, now - timedelta(days=3))
        await query_db.commit()
        logger.info(f'[内容缓存] {symbol} 写入{saved}条 types={types}')
        return saved

    @classmethod
    def _normalize_item(
        cls,
        symbol: str,
        market: str,
        content_type: str,
        item: Any,
        fetched_at: datetime,
        expires_at: datetime,
    ) -> dict[str, Any] | None:
        if item is None:
            return None
        if not isinstance(item, dict):
            item = cls._to_dict(item)

        # 长桥多语言字段：优先中文
        title = cls._pick_text(
            item,
            (
                'title',
                'title_cn',
                'title_zh',
                'headline',
                'headline_cn',
                'subject',
                'name',
                'name_cn',
            ),
        )
        if not title:
            return None

        body = cls._pick_text(
            item,
            (
                'content',
                'content_cn',
                'body',
                'body_cn',
                'text',
                'summary',
                'summary_cn',
                'abstract',
                'description',
                'desc',
            ),
        )
        body = cls._strip_html(body)

        source_link = (
            item.get('url')
            or item.get('link')
            or item.get('source_link')
            or item.get('uri')
            or item.get('news_url')
            or item.get('file_url')
        )
        source_item_id = str(
            item.get('id')
            or item.get('news_id')
            or item.get('topic_id')
            or item.get('filing_id')
            or item.get('uri')
            or title
        )[:128]
        published_at = cls._parse_time(
            item.get('published_at')
            or item.get('publish_time')
            or item.get('time')
            or item.get('timestamp')
            or item.get('release_time')
        )
        return {
            'symbol': symbol,
            'market': market,
            'content_type': content_type,
            'source_name': 'longbridge',
            'source_item_id': source_item_id,
            'title': title[:255],
            'summary': body[: cls.BODY_MAX_LEN],
            'source_link': str(source_link)[:1000] if source_link else None,
            'published_at': published_at,
            'fetched_at': fetched_at,
            'expires_at': expires_at,
            'payload_json': json.dumps(item, ensure_ascii=False, default=str)[:60000],
        }

    @classmethod
    def _pick_text(cls, item: dict[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            val = item.get(key)
            if val is None:
                continue
            # 可能是多语言对象 {zh_cn:..., en:...}
            if isinstance(val, dict):
                for lk in ('zh_cn', 'zh-CN', 'zh', 'cn', 'ZH_CN', 'title', 'text', 'content'):
                    if val.get(lk):
                        text = str(val.get(lk)).strip()
                        if text:
                            return text
                # 取第一个非空字符串
                for v in val.values():
                    if v and str(v).strip():
                        return str(v).strip()
                continue
            text = str(val).strip()
            if text:
                return text
        return ''

    @classmethod
    async def _fetch_page_text(cls, client: httpx.AsyncClient, url: str) -> str:
        """抓取链接页可见文本（尽力而为，失败返回空）。"""
        try:
            resp = await client.get(url, headers={'User-Agent': USER_AGENT})
            if resp.status_code >= 400:
                return ''
            ctype = (resp.headers.get('content-type') or '').lower()
            if 'html' not in ctype and 'text' not in ctype and 'json' not in ctype:
                return ''
            text = resp.text or ''
            # 去 script/style
            text = re.sub(r'(?is)<script[^>]*>.*?</script>', ' ', text)
            text = re.sub(r'(?is)<style[^>]*>.*?</style>', ' ', text)
            text = cls._strip_html(text)
            text = re.sub(r'\s+', ' ', text).strip()
            # 过短或像导航页则丢弃
            if len(text) < 80:
                return ''
            return text[: cls.BODY_MAX_LEN]
        except Exception as exc:
            logger.debug(f'[内容缓存] 抓取正文失败 url={url}: {exc}')
            return ''

    @staticmethod
    def _strip_html(text: str) -> str:
        return re.sub(r'<[^>]+>', ' ', text or '').strip()

    @staticmethod
    def _to_dict(obj: Any) -> dict[str, Any]:
        if isinstance(obj, dict):
            return obj
        result: dict[str, Any] = {}
        for key in dir(obj):
            if key.startswith('_'):
                continue
            try:
                val = getattr(obj, key)
            except Exception:
                continue
            if callable(val):
                continue
            result[key] = val
        return result

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        if not text:
            return None
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
            try:
                cleaned = text[:19].replace('T', ' ') if 'T' in text else text[:19]
                return datetime.strptime(cleaned, '%Y-%m-%d %H:%M:%S' if ' ' in cleaned else '%Y-%m-%d')
            except ValueError:
                continue
        try:
            ts = float(text)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts)
        except (TypeError, ValueError, OSError):
            return None
