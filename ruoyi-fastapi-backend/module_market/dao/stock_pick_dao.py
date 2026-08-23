"""全市场智能选股单 DAO。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from module_market.entity.do.market_do import MarketPriceHistoryDaily, MarketStockPick, MarketStockPickItem


class StockPickDao:
    @classmethod
    async def get_by_date(cls, db: AsyncSession, trade_date: str) -> MarketStockPick | None:
        return (
            (await db.execute(select(MarketStockPick).where(MarketStockPick.trade_date == trade_date)))
            .scalars()
            .first()
        )

    @classmethod
    async def get_latest(cls, db: AsyncSession) -> MarketStockPick | None:
        return (
            (
                await db.execute(
                    select(MarketStockPick)
                    .order_by(desc(MarketStockPick.trade_date), desc(MarketStockPick.pick_id))
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def list_items(cls, db: AsyncSession, pick_id: int, market: str | None = None) -> list[MarketStockPickItem]:
        query = select(MarketStockPickItem).where(MarketStockPickItem.pick_id == pick_id)
        if market:
            query = query.where(MarketStockPickItem.market == market.upper())
        query = query.order_by(MarketStockPickItem.market, MarketStockPickItem.rank_no)
        return list((await db.execute(query)).scalars().all())

    @classmethod
    async def upsert_run(cls, db: AsyncSession, row: dict[str, Any]) -> MarketStockPick:
        trade_date = str(row['trade_date'])
        existing = await cls.get_by_date(db, trade_date)
        now = datetime.now()
        if existing:
            for key, value in row.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            existing.update_time = now
            await db.flush()
            return existing
        entity = MarketStockPick(**row)
        entity.create_time = now
        entity.update_time = now
        db.add(entity)
        await db.flush()
        return entity

    @classmethod
    async def replace_items(cls, db: AsyncSession, pick_id: int, rows: list[dict[str, Any]]) -> int:
        await db.execute(delete(MarketStockPickItem).where(MarketStockPickItem.pick_id == pick_id))
        now = datetime.now()
        for item in rows:
            payload = dict(item)
            payload['pick_id'] = pick_id
            payload.setdefault('create_time', now)
            db.add(MarketStockPickItem(**payload))
        await db.flush()
        return len(rows)

    @classmethod
    async def load_recent_daily_klines(
        cls, db: AsyncSession, symbols: list[str], cutoff: str
    ) -> dict[str, list[dict[str, Any]]]:
        uniq = [s for s in dict.fromkeys(symbols) if s]
        if not uniq:
            return {}
        rows = (
            (
                await db.execute(
                    select(MarketPriceHistoryDaily)
                    .where(
                        MarketPriceHistoryDaily.symbol.in_(uniq),
                        MarketPriceHistoryDaily.trade_date >= cutoff,
                    )
                    .order_by(MarketPriceHistoryDaily.symbol, MarketPriceHistoryDaily.trade_date)
                )
            )
            .scalars()
            .all()
        )
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row.symbol, []).append(
                {
                    'date': row.trade_date,
                    'open': row.open_price,
                    'high': row.high_price,
                    'low': row.low_price,
                    'close': row.close_price,
                    'volume': row.volume,
                }
            )
        return grouped
