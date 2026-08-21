from datetime import datetime
from typing import Any

from sqlalchemy import and_, delete, desc, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import PageModel
from module_market.entity.do.market_do import (
    FinanceBriefing,
    MarketDailyReview,
    MarketInstrument,
    MarketWatchlist,
    MarketWatchlistAnalysis,
    SymbolAiAnalysis,
    SymbolContentCache,
)
from module_market.entity.vo.market_vo import MarketInstrumentQueryModel, MarketWatchlistPageQueryModel
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
        query = (
            select(MarketInstrument)
            .where(
                MarketInstrument.category == query_object.category if query_object.category else True,
                MarketInstrument.market == query_object.market if query_object.market else True,
                MarketInstrument.enabled == query_object.enabled if query_object.enabled else True,
            )
            .order_by(MarketInstrument.category, MarketInstrument.symbol)
        )
        keyword = (getattr(query_object, 'keyword', None) or '').strip().replace('%', '').replace('_', '')[:32]
        if keyword:
            like = f'%{keyword}%'
            query = query.where(or_(MarketInstrument.symbol.like(like), MarketInstrument.name.like(like)))
        rows = (await db.execute(query)).scalars().all()
        return list(rows)

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

        :return: 本次新增条数
        """
        existing = await cls.get_all_symbols(db)
        added = 0
        for item in instruments:
            symbol = item['symbol']
            if symbol in existing:
                await db.execute(
                    update(MarketInstrument)
                    .where(MarketInstrument.symbol == symbol)
                    .values(name=item.get('name'), market=item.get('market'), category=item.get('category'))
                )
            else:
                db.add(MarketInstrument(**item))
                added += 1
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
    async def prune_older_than(cls, db: AsyncSession, before: datetime) -> None:
        from sqlalchemy import delete

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
        from sqlalchemy import delete

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


class MarketDailyReviewDao:
    """三市场收盘日报 DAO"""

    @classmethod
    async def upsert(cls, db: AsyncSession, item: dict[str, Any]) -> MarketDailyReview:
        existing = (
            (
                await db.execute(
                    select(MarketDailyReview).where(
                        MarketDailyReview.market == item['market'],
                        MarketDailyReview.trade_date == item['trade_date'],
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing:
            for key, value in item.items():
                setattr(existing, key, value)
            await db.flush()
            return existing
        row = MarketDailyReview(**item)
        db.add(row)
        await db.flush()
        return row

    @classmethod
    async def get_latest_by_market(cls, db: AsyncSession, market: str) -> MarketDailyReview | None:
        return (
            (
                await db.execute(
                    select(MarketDailyReview)
                    .where(MarketDailyReview.market == market.upper())
                    .order_by(desc(MarketDailyReview.trade_date), desc(MarketDailyReview.review_id))
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def list_latest(cls, db: AsyncSession) -> list[MarketDailyReview]:
        rows = []
        for market in ('US', 'HK', 'CN'):
            row = await cls.get_latest_by_market(db, market)
            if row:
                rows.append(row)
        return rows

    @classmethod
    async def list_history(
        cls, db: AsyncSession, market: str | None = None, limit: int = 60
    ) -> list[MarketDailyReview]:
        limit = max(1, min(int(limit or 60), 180))
        query = select(MarketDailyReview)
        if market:
            query = query.where(MarketDailyReview.market == market.upper())
        query = query.order_by(desc(MarketDailyReview.trade_date), desc(MarketDailyReview.review_id)).limit(limit)
        return list((await db.execute(query)).scalars().all())
