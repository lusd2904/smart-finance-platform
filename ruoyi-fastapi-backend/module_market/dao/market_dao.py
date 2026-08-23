from datetime import datetime
from typing import Any

from sqlalchemy import and_, delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import PageModel
from module_market.constant.instruments import (
    LISTED_CATEGORY,
    LISTED_SEARCH_LIMIT,
    build_quotes_from_ranked_bars,
    clamp_universe_page,
    featured_list_excludes_listed,
    sanitize_instrument_keyword,
)
from module_market.entity.do.market_do import (
    FinanceBriefing,
    MarketInstrument,
    MarketPriceHistoryDaily,
    MarketWatchlist,
    MarketWatchlistAnalysis,
    SymbolAiAnalysis,
    SymbolContentCache,
)
from module_market.entity.vo.market_vo import (
    MarketInstrumentQueryModel,
    MarketInstrumentUniverseQueryModel,
    MarketWatchlistPageQueryModel,
)
from utils.page_util import PageUtil


class MarketInstrumentDao:
    """行情标的元数据数据库操作层"""

    @classmethod
    async def get_instrument_list(
        cls, db: AsyncSession, query_object: MarketInstrumentQueryModel
    ) -> list[MarketInstrument]:
        """
        根据查询参数获取标的列表
        """
        keyword = sanitize_instrument_keyword(getattr(query_object, 'keyword', None))
        category = (query_object.category or '').strip() or None
        query = select(MarketInstrument).where(
            MarketInstrument.market == query_object.market if query_object.market else True,
            MarketInstrument.enabled == query_object.enabled if query_object.enabled else True,
        )
        if category:
            query = query.where(MarketInstrument.category == category)
        elif featured_list_excludes_listed(category, keyword):
            # 无关键字时不把全市场 listed 代码打到行情台/下拉框
            query = query.where(MarketInstrument.category != LISTED_CATEGORY)
        query = query.order_by(MarketInstrument.category, MarketInstrument.symbol)
        if keyword:
            like = f'%{keyword}%'
            query = query.where(or_(MarketInstrument.symbol.like(like), MarketInstrument.name.like(like)))
            query = query.limit(LISTED_SEARCH_LIMIT)
        rows = (await db.execute(query)).scalars().all()
        return list(rows)

    @classmethod
    async def get_instrument_universe(
        cls, db: AsyncSession, query_object: MarketInstrumentUniverseQueryModel
    ) -> PageModel:
        """全市场标的分页（含 listed），精选分类排在 listed 前面。"""
        page_num, page_size = clamp_universe_page(query_object.page_num, query_object.page_size)
        keyword = sanitize_instrument_keyword(query_object.keyword)
        market = (query_object.market or '').strip().upper() or None
        if market and market not in {'US', 'HK', 'CN'}:
            market = None
        query = select(MarketInstrument)
        if market:
            query = query.where(MarketInstrument.market == market)
        if query_object.enabled:
            query = query.where(MarketInstrument.enabled == query_object.enabled)
        if keyword:
            like = f'%{keyword}%'
            query = query.where(or_(MarketInstrument.symbol.like(like), MarketInstrument.name.like(like)))
        query = query.order_by(
            MarketInstrument.category == LISTED_CATEGORY,
            MarketInstrument.market,
            MarketInstrument.symbol,
        )
        return await PageUtil.paginate(db, query, page_num, page_size, is_page=True)

    @classmethod
    async def get_instrument_market_counts(cls, db: AsyncSession, enabled: str | None = '1') -> dict[str, int]:
        """各市场启用标的数量（含 listed）。"""
        query = select(MarketInstrument.market, func.count())
        if enabled:
            query = query.where(MarketInstrument.enabled == enabled)
        query = query.group_by(MarketInstrument.market)
        rows = (await db.execute(query)).all()
        counts = {'US': 0, 'HK': 0, 'CN': 0, 'total': 0}
        for market, n in rows:
            key = str(market or '').upper()
            num = int(n or 0)
            if key in counts:
                counts[key] = num
            counts['total'] += num
        return counts

    @classmethod
    async def get_latest_daily_quotes(cls, db: AsyncSession, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """当前页标的最近两根日K，用于列表最新价/涨跌幅。"""
        uniq = [s for s in dict.fromkeys(symbols) if s]
        if not uniq:
            return {}
        ranked = (
            select(
                MarketPriceHistoryDaily.symbol,
                MarketPriceHistoryDaily.trade_date,
                MarketPriceHistoryDaily.close_price,
                MarketPriceHistoryDaily.volume,
                func.row_number()
                .over(
                    partition_by=MarketPriceHistoryDaily.symbol,
                    order_by=MarketPriceHistoryDaily.trade_date.desc(),
                )
                .label('rn'),
            )
            .where(MarketPriceHistoryDaily.symbol.in_(uniq))
            .subquery()
        )
        rows = (await db.execute(select(ranked).where(ranked.c.rn <= 2))).all()
        return build_quotes_from_ranked_bars(rows)

    @classmethod
    async def get_by_symbol(cls, db: AsyncSession, symbol: str) -> MarketInstrument | None:
        """
        按symbol获取单个标的
        """
        return (
            (await db.execute(select(MarketInstrument).where(MarketInstrument.symbol == symbol))).scalars().first()
        )

    @classmethod
    async def get_all_symbols(cls, db: AsyncSession) -> set[str]:
        """
        获取已存在的symbol集合
        """
        rows = (await db.execute(select(MarketInstrument.symbol))).all()
        return {row[0] for row in rows}

    @classmethod
    async def upsert_instruments(cls, db: AsyncSession, instruments: list[dict[str, Any]]) -> int:
        """
        批量upsert目标标的（按symbol判断存在则更新name/market/category，不存在则新增）

        更新语句按 symbol 分组合并为单条批量 UPDATE（CASE WHEN），避免逐条往返。

        :return: 本次新增条数
        """
        existing = await cls.get_all_symbols(db)
        added = 0
        # 按 (name, market, category) 分组收集待更新的 symbol，同组合并为一条 UPDATE
        update_groups: dict[tuple[Any, Any, Any], list[str]] = {}
        for item in instruments:
            symbol = item['symbol']
            if symbol in existing:
                key = (item.get('name'), item.get('market'), item.get('category'))
                update_groups.setdefault(key, []).append(symbol)
            else:
                db.add(MarketInstrument(**item))
                added += 1
        for (name, market, category), symbols in update_groups.items():
            await db.execute(
                update(MarketInstrument)
                .where(MarketInstrument.symbol.in_(symbols))
                .values(name=name, market=market, category=category)
            )
        await db.flush()
        return added


class SymbolAiAnalysisDao:
    """标的 AI 研判历史 DAO"""

    @classmethod
    async def add(cls, db: AsyncSession, row: dict[str, Any]) -> SymbolAiAnalysis:
        entity = SymbolAiAnalysis(**row)
        db.add(entity)
        await db.flush()
        return entity

    @classmethod
    async def get_latest(cls, db: AsyncSession, symbol: str, market: str | None = None) -> SymbolAiAnalysis | None:
        query = select(SymbolAiAnalysis).where(SymbolAiAnalysis.symbol == symbol)
        if market:
            query = query.where(SymbolAiAnalysis.market == market.upper())
        query = query.order_by(desc(SymbolAiAnalysis.analysis_time), desc(SymbolAiAnalysis.analysis_id)).limit(1)
        return (await db.execute(query)).scalars().first()


class FinanceBriefingDao:
    """财经资讯简报 DAO"""

    @classmethod
    async def add_batch(cls, db: AsyncSession, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        db.add_all([FinanceBriefing(**r) for r in rows])
        await db.flush()
        return len(rows)

    @classmethod
    async def get_latest(
        cls, db: AsyncSession, limit: int = 20, market: str | None = None, now: datetime | None = None
    ) -> list[FinanceBriefing]:
        now = now or datetime.now()
        query = select(FinanceBriefing).where(
            or_(FinanceBriefing.expires_at.is_(None), FinanceBriefing.expires_at >= now)
        )
        if market:
            query = query.where(FinanceBriefing.market == market.upper())
        query = query.order_by(desc(FinanceBriefing.generated_at), desc(FinanceBriefing.id)).limit(limit)
        return list((await db.execute(query)).scalars().all())

    @classmethod
    async def recent_duplicate(cls, db: AsyncSession, market: str, headline: str, since: datetime) -> bool:
        row = (
            await db.execute(
                select(FinanceBriefing.id)
                .where(
                    FinanceBriefing.market == market,
                    FinanceBriefing.headline == headline,
                    FinanceBriefing.generated_at >= since,
                )
                .limit(1)
            )
        ).first()
        return bool(row)

    @classmethod
    async def filter_duplicates(
        cls, db: AsyncSession, market: str, headlines: list[str], since: datetime
    ) -> set[str]:
        """
        批量查重：一次查询返回 since 之后已存在的 headline 集合。

        :param db: 会话
        :param market: 市场
        :param headlines: 待检查的标题列表
        :param since: 时间下限
        :return: 已存在的 headline 集合
        """
        if not headlines:
            return set()
        rows = (
            await db.execute(
                select(FinanceBriefing.headline).where(
                    FinanceBriefing.market == market,
                    FinanceBriefing.headline.in_(headlines),
                    FinanceBriefing.generated_at >= since,
                )
            )
        ).all()
        return {row[0] for row in rows}

    @classmethod
    async def prune_older_than(cls, db: AsyncSession, before: datetime) -> None:

        await db.execute(delete(FinanceBriefing).where(FinanceBriefing.generated_at < before))
        await db.flush()


class SymbolContentCacheDao:
    """标的内容缓存 DAO"""

    @classmethod
    async def get_cached(
        cls,
        db: AsyncSession,
        symbol: str,
        content_type: str,
        limit: int = 20,
        now: datetime | None = None,
    ) -> list[SymbolContentCache]:
        now = now or datetime.now()
        query = (
            select(SymbolContentCache)
            .where(
                SymbolContentCache.symbol == symbol,
                SymbolContentCache.content_type == content_type,
                or_(SymbolContentCache.expires_at.is_(None), SymbolContentCache.expires_at >= now),
            )
            .order_by(desc(SymbolContentCache.published_at), desc(SymbolContentCache.id))
            .limit(limit)
        )
        return list((await db.execute(query)).scalars().all())

    _UPDATABLE_KEYS = (
        'title',
        'summary',
        'source_link',
        'published_at',
        'fetched_at',
        'expires_at',
        'payload_json',
        'market',
    )

    @classmethod
    async def upsert_items(cls, db: AsyncSession, rows: list[dict[str, Any]]) -> None:
        """
        按唯一键批量 upsert 缓存：一次查询取回全部已存在键，减少逐条往返。

        :param db: 会话
        :param rows: 待写入的缓存行
        :return: None
        """
        if not rows:
            return
        symbols = {row['symbol'] for row in rows}
        content_types = {row['content_type'] for row in rows}
        existing_rows = (
            await db.execute(
                select(SymbolContentCache).where(
                    and_(
                        SymbolContentCache.symbol.in_(symbols),
                        SymbolContentCache.content_type.in_(content_types),
                    )
                )
            )
        ).scalars().all()
        existing_map = {
            (
                item.symbol,
                item.content_type,
                item.source_name,
                item.source_item_id,
            ): item
            for item in existing_rows
        }
        for row in rows:
            key = (
                row['symbol'],
                row['content_type'],
                row['source_name'],
                row.get('source_item_id'),
            )
            existing = existing_map.get(key)
            if existing:
                for k in cls._UPDATABLE_KEYS:
                    if k in row:
                        setattr(existing, k, row[k])
            else:
                db.add(SymbolContentCache(**row))
        await db.flush()

    @classmethod
    async def upsert_item(cls, db: AsyncSession, row: dict[str, Any]) -> None:
        """按唯一键 upsert 一条缓存"""
        existing = (
            await db.execute(
                select(SymbolContentCache).where(
                    and_(
                        SymbolContentCache.symbol == row['symbol'],
                        SymbolContentCache.content_type == row['content_type'],
                        SymbolContentCache.source_name == row['source_name'],
                        SymbolContentCache.source_item_id == row.get('source_item_id'),
                    )
                )
            )
        ).scalars().first()
        if existing:
            for key in (
                'title',
                'summary',
                'source_link',
                'published_at',
                'fetched_at',
                'expires_at',
                'payload_json',
                'market',
            ):
                if key in row:
                    setattr(existing, key, row[key])
        else:
            db.add(SymbolContentCache(**row))
        await db.flush()

    @classmethod
    async def prune_expired(cls, db: AsyncSession, before: datetime) -> None:
        """物理清理过期缓存，防止news/topic条目无限堆积"""

        await db.execute(
            delete(SymbolContentCache).where(
                SymbolContentCache.expires_at.is_not(None), SymbolContentCache.expires_at < before
            )
        )
        await db.flush()


class MarketWatchlistDao:
    """行情中心自选清单 DAO"""

    @classmethod
    async def get_watchlist(
        cls, db: AsyncSession, query_object: MarketWatchlistPageQueryModel, is_page: bool = False
    ) -> PageModel | list[dict[str, Any]]:
        user_id = getattr(query_object, 'user_id', None)
        query = (
            select(MarketWatchlist)
            .where(
                MarketWatchlist.user_id == user_id if user_id is not None else True,
                MarketWatchlist.symbol.like(f'%{query_object.symbol}%') if query_object.symbol else True,
                MarketWatchlist.market == query_object.market if query_object.market else True,
                MarketWatchlist.enabled == query_object.enabled if query_object.enabled else True,
            )
            .order_by(MarketWatchlist.sort_order, desc(MarketWatchlist.create_time))
        )
        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def get_enabled(cls, db: AsyncSession, user_id: int | None = None) -> list[MarketWatchlist]:
        query = select(MarketWatchlist).where(MarketWatchlist.enabled == '1')
        if user_id is not None:
            query = query.where(MarketWatchlist.user_id == user_id)
        query = query.order_by(MarketWatchlist.sort_order, desc(MarketWatchlist.create_time))
        rows = (await db.execute(query)).scalars().all()
        return list(rows)

    @classmethod
    async def get_all_enabled(cls, db: AsyncSession) -> list[MarketWatchlist]:
        query = (
            select(MarketWatchlist)
            .where(MarketWatchlist.enabled == '1')
            .order_by(MarketWatchlist.user_id, MarketWatchlist.sort_order, desc(MarketWatchlist.create_time))
        )
        rows = (await db.execute(query)).scalars().all()
        return list(rows)

    @classmethod
    async def get_by_id(cls, db: AsyncSession, watchlist_id: int) -> MarketWatchlist | None:
        return (
            (await db.execute(select(MarketWatchlist).where(MarketWatchlist.id == watchlist_id))).scalars().first()
        )

    @classmethod
    async def get_by_symbol(
        cls, db: AsyncSession, symbol: str, market: str, user_id: int | None = None
    ) -> MarketWatchlist | None:
        query = select(MarketWatchlist).where(
            MarketWatchlist.symbol == symbol, MarketWatchlist.market == market
        )
        if user_id is not None:
            query = query.where(MarketWatchlist.user_id == user_id)
        return (await db.execute(query)).scalars().first()

    @classmethod
    async def add(cls, db: AsyncSession, item: dict[str, Any]) -> MarketWatchlist:
        row = MarketWatchlist(**item)
        db.add(row)
        await db.flush()
        return row

    @classmethod
    async def delete_by_ids(cls, db: AsyncSession, ids: list[int], user_id: int | None = None) -> None:
        if not ids:
            return
        query = delete(MarketWatchlist).where(MarketWatchlist.id.in_(ids))
        if user_id is not None:
            query = query.where(MarketWatchlist.user_id == user_id)
        await db.execute(query)


class MarketWatchlistAnalysisDao:
    """自选综合分析 DAO"""

    @classmethod
    async def add(cls, db: AsyncSession, item: dict[str, Any]) -> MarketWatchlistAnalysis:
        row = MarketWatchlistAnalysis(**item)
        db.add(row)
        await db.flush()
        return row

    @classmethod
    async def get_latest(
        cls,
        db: AsyncSession,
        symbol: str,
        market: str | None = None,
        user_id: int | None = None,
    ) -> MarketWatchlistAnalysis | None:
        query = select(MarketWatchlistAnalysis).where(MarketWatchlistAnalysis.symbol == symbol)
        if market:
            query = query.where(MarketWatchlistAnalysis.market == market.upper())
        if user_id is not None:
            query = query.where(MarketWatchlistAnalysis.user_id == user_id)
        query = query.order_by(desc(MarketWatchlistAnalysis.analysis_time), desc(MarketWatchlistAnalysis.analysis_id)).limit(1)
        return (await db.execute(query)).scalars().first()

    @classmethod
    async def list_latest_by_symbols(
        cls,
        db: AsyncSession,
        pairs: list[tuple[str, str]],
        user_id: int | None = None,
    ) -> dict[tuple[str, str], MarketWatchlistAnalysis]:
        """每个 (symbol, market) 取最新一条。"""
        result: dict[tuple[str, str], MarketWatchlistAnalysis] = {}
        if not pairs:
            return result
        symbols = list({p[0] for p in pairs})
        query = select(MarketWatchlistAnalysis).where(MarketWatchlistAnalysis.symbol.in_(symbols))
        if user_id is not None:
            query = query.where(MarketWatchlistAnalysis.user_id == user_id)
        rows = (
            (
                await db.execute(
                    query.order_by(desc(MarketWatchlistAnalysis.analysis_time), desc(MarketWatchlistAnalysis.analysis_id))
                )
            )
            .scalars()
            .all()
        )
        wanted = {(s.upper(), m.upper()) for s, m in pairs}
        for row in rows:
            key = (row.symbol.upper(), (row.market or 'US').upper())
            if key in wanted and key not in result:
                result[key] = row
        return result

    @classmethod
    async def list_history(
        cls,
        db: AsyncSession,
        symbol: str,
        market: str | None = None,
        limit: int = 12,
        user_id: int | None = None,
    ) -> list[MarketWatchlistAnalysis]:
        limit = max(1, min(int(limit or 12), 50))
        query = select(MarketWatchlistAnalysis).where(MarketWatchlistAnalysis.symbol == symbol)
        if market:
            query = query.where(MarketWatchlistAnalysis.market == market.upper())
        if user_id is not None:
            query = query.where(MarketWatchlistAnalysis.user_id == user_id)
        query = query.order_by(desc(MarketWatchlistAnalysis.analysis_time)).limit(limit)
        return list((await db.execute(query)).scalars().all())

    @classmethod
    async def list_recent_by_user(
        cls, db: AsyncSession, user_id: int, limit: int = 200
    ) -> list[MarketWatchlistAnalysis]:
        limit = max(1, min(int(limit or 200), 400))
        query = (
            select(MarketWatchlistAnalysis)
            .where(MarketWatchlistAnalysis.user_id == user_id)
            .order_by(desc(MarketWatchlistAnalysis.analysis_time))
            .limit(limit)
        )
        return list((await db.execute(query)).scalars().all())

    @classmethod
    async def prune_older_than(cls, db: AsyncSession, before: datetime) -> None:
        await db.execute(delete(MarketWatchlistAnalysis).where(MarketWatchlistAnalysis.analysis_time < before))
        await db.flush()
