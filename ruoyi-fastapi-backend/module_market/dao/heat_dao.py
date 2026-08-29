"""市场热度与 Top50 快照 DAO。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, desc, select

from module_market.entity.do.market_do import MarketHeatDaily, MarketTop50Snapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MarketHeatDao:
    @classmethod
    async def get_heat(cls, db: AsyncSession, market: str, trade_date: str) -> MarketHeatDaily | None:
        return (
            await db.execute(
                select(MarketHeatDaily).where(
                    MarketHeatDaily.market == market.upper(),
                    MarketHeatDaily.trade_date == trade_date,
                )
            )
        ).scalars().first()

    @classmethod
    async def get_latest_heat(cls, db: AsyncSession, market: str) -> MarketHeatDaily | None:
        return (
            await db.execute(
                select(MarketHeatDaily)
                .where(MarketHeatDaily.market == market.upper())
                .order_by(desc(MarketHeatDaily.trade_date))
                .limit(1)
            )
        ).scalars().first()

    @classmethod
    async def list_heat_trend(cls, db: AsyncSession, market: str, limit: int = 7) -> list[MarketHeatDaily]:
        rows = (
            await db.execute(
                select(MarketHeatDaily)
                .where(MarketHeatDaily.market == market.upper())
                .order_by(desc(MarketHeatDaily.trade_date))
                .limit(max(1, min(limit, 30)))
            )
        ).scalars().all()
        return list(reversed(rows))

    @classmethod
    async def upsert_heat(cls, db: AsyncSession, row: dict[str, Any]) -> MarketHeatDaily:
        market = str(row['market']).upper()
        trade_date = str(row['trade_date'])
        existing = await cls.get_heat(db, market, trade_date)
        if existing:
            for key, value in row.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            existing.update_time = datetime.now()
            await db.flush()
            return existing
        entity = MarketHeatDaily(**row)
        db.add(entity)
        await db.flush()
        return entity

    @classmethod
    async def replace_top50(cls, db: AsyncSession, market: str, trade_date: str, rows: list[dict[str, Any]]) -> int:
        await db.execute(
            delete(MarketTop50Snapshot).where(
                MarketTop50Snapshot.market == market.upper(),
                MarketTop50Snapshot.trade_date == trade_date,
            )
        )
        if not rows:
            await db.flush()
            return 0
        for item in rows:
            db.add(MarketTop50Snapshot(**item))
        await db.flush()
        return len(rows)

    @classmethod
    async def list_distinct_trade_dates(cls, db: AsyncSession, limit: int = 60) -> list[str]:
        cap = max(1, min(int(limit or 60), 120))
        rows = (
            await db.execute(
                select(MarketHeatDaily.trade_date)
                .group_by(MarketHeatDaily.trade_date)
                .order_by(desc(MarketHeatDaily.trade_date))
                .limit(cap)
            )
        ).scalars().all()
        return [str(d)[:10] for d in rows if d]

    @classmethod
    async def list_top50(cls, db: AsyncSession, market: str, trade_date: str) -> list[MarketTop50Snapshot]:
        rows = (
            await db.execute(
                select(MarketTop50Snapshot)
                .where(
                    MarketTop50Snapshot.market == market.upper(),
                    MarketTop50Snapshot.trade_date == trade_date,
                )
                .order_by(MarketTop50Snapshot.rank_no)
            )
        ).scalars().all()
        return list(rows)
