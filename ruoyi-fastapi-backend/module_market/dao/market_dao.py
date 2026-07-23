from datetime import datetime
from typing import Any

from sqlalchemy import and_, desc, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from module_market.entity.do.market_do import (
    FinanceBriefing,
    MarketInstrument,
    SymbolAiAnalysis,
    SymbolContentCache,
)
from module_market.entity.vo.market_vo import MarketInstrumentQueryModel


class MarketInstrumentDao:
    """
    行情标的元数据数据库操作层
    """

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
