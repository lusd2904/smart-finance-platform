from datetime import datetime, time
from typing import Any

from sqlalchemy import delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import PageModel
from module_quant.entity.do.quant_do import (
    QuantFactorSnapshot,
    QuantLongbridgeConfig,
    QuantReadmodelSnapshot,
    QuantStrategyRun,
    QuantStrategySignal,
    QuantWatchlist,
)
from module_quant.entity.vo.quant_vo import (
    QuantStrategyRunPageQueryModel,
    QuantWatchlistPageQueryModel,
)
from utils.page_util import PageUtil


class QuantWatchlistDao:
    """
    量化自选池数据库操作层
    """

    @classmethod
    async def get_watchlist(
        cls, db: AsyncSession, query_object: QuantWatchlistPageQueryModel, is_page: bool = False
    ) -> PageModel | list[dict[str, Any]]:
        """根据查询参数获取自选池列表"""
        query = (
            select(QuantWatchlist)
            .where(
                QuantWatchlist.symbol.like(f'%{query_object.symbol}%') if query_object.symbol else True,
                QuantWatchlist.market == query_object.market if query_object.market else True,
                QuantWatchlist.enabled == query_object.enabled if query_object.enabled else True,
            )
            .order_by(desc(QuantWatchlist.create_time))
        )
        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def get_enabled_symbols(cls, db: AsyncSession) -> list[QuantWatchlist]:
        """获取所有启用的自选标的"""
        rows = (
            (await db.execute(select(QuantWatchlist).where(QuantWatchlist.enabled == '1')))
            .scalars()
            .all()
        )
        return list(rows)

    @classmethod
    async def get_by_symbol(cls, db: AsyncSession, symbol: str, market: str) -> QuantWatchlist | None:
        """按代码+市场查重"""
        return (
            (
                await db.execute(
                    select(QuantWatchlist).where(
                        QuantWatchlist.symbol == symbol, QuantWatchlist.market == market
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def add_watchlist(cls, db: AsyncSession, item: dict) -> QuantWatchlist:
        """新增自选标的"""
        db_item = QuantWatchlist(**item)
        db.add(db_item)
        await db.flush()
        return db_item

    @classmethod
    async def delete_watchlist(cls, db: AsyncSession, ids: list[int]) -> None:
        """删除自选标的"""
        await db.execute(delete(QuantWatchlist).where(QuantWatchlist.id.in_(ids)))


class QuantStrategyDao:
    """
    量化策略运行/信号数据库操作层
    """

    @classmethod
    async def add_run(cls, db: AsyncSession, run: dict) -> QuantStrategyRun:
        """新增策略运行记录"""
        db_run = QuantStrategyRun(**run)
        db.add(db_run)
        await db.flush()
        return db_run

    @classmethod
    async def add_signals(cls, db: AsyncSession, signals: list[dict]) -> list[QuantStrategySignal]:
        """批量新增信号"""
        db_signals = [QuantStrategySignal(**s) for s in signals]
        db.add_all(db_signals)
        await db.flush()
        return db_signals

    @classmethod
    async def get_run_list(
        cls, db: AsyncSession, query_object: QuantStrategyRunPageQueryModel, is_page: bool = False
    ) -> PageModel | list[dict[str, Any]]:
        """获取策略运行记录分页列表"""
        query = (
            select(QuantStrategyRun)
            .where(
                QuantStrategyRun.strategy_profile == query_object.strategy_profile
                if query_object.strategy_profile
                else True,
                QuantStrategyRun.create_time.between(
                    datetime.combine(datetime.strptime(query_object.begin_time, '%Y-%m-%d'), time(0, 0, 0)),
                    datetime.combine(datetime.strptime(query_object.end_time, '%Y-%m-%d'), time(23, 59, 59)),
                )
                if query_object.begin_time and query_object.end_time
                else True,
            )
            .order_by(desc(QuantStrategyRun.create_time))
        )
        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def get_signals_by_run(cls, db: AsyncSession, run_id: int) -> list[QuantStrategySignal]:
        """获取某次运行的信号列表"""
        rows = (
            (
                await db.execute(
                    select(QuantStrategySignal)
                    .where(QuantStrategySignal.run_id == run_id)
                    .order_by(desc(QuantStrategySignal.score))
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    @classmethod
    async def get_run_by_id(cls, db: AsyncSession, run_id: int) -> QuantStrategyRun | None:
        """按主键获取策略运行记录"""
        return (
            (await db.execute(select(QuantStrategyRun).where(QuantStrategyRun.run_id == run_id)))
            .scalars()
            .first()
        )

    @classmethod
    async def get_run_by_cycle_id(cls, db: AsyncSession, cycle_id: str) -> QuantStrategyRun | None:
        """按 cycle_id 获取策略运行记录"""
        return (
            (
                await db.execute(
                    select(QuantStrategyRun)
                    .where(QuantStrategyRun.cycle_id == cycle_id)
                    .order_by(desc(QuantStrategyRun.create_time))
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_latest_signal_for_symbol(
        cls, db: AsyncSession, symbol: str
    ) -> QuantStrategySignal | None:
        """获取某标的最近一次策略信号"""
        return (
            (
                await db.execute(
                    select(QuantStrategySignal)
                    .where(QuantStrategySignal.symbol == symbol)
                    .order_by(desc(QuantStrategySignal.create_time), desc(QuantStrategySignal.signal_id))
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_scan_runs(
        cls, db: AsyncSession, limit: int = 20
    ) -> list[QuantStrategyRun]:
        """扫描运行台账列表（最近 N 条）"""
        limit = max(1, min(int(limit or 20), 100))
        rows = (
            (
                await db.execute(
                    select(QuantStrategyRun)
                    .order_by(desc(QuantStrategyRun.create_time))
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)


class QuantLongbridgeConfigDao:
    """
    长桥凭据配置数据库操作层
    """

    @classmethod
    async def get_config(cls, db: AsyncSession) -> QuantLongbridgeConfig | None:
        """获取长桥凭据（单行）"""
        return (
            (await db.execute(select(QuantLongbridgeConfig).order_by(QuantLongbridgeConfig.id).limit(1)))
            .scalars()
            .first()
        )

    @classmethod
    async def save_config(cls, db: AsyncSession, config: dict) -> QuantLongbridgeConfig:
        """保存长桥凭据（存在则更新，不存在则新增）"""
        existing = await cls.get_config(db)
        if existing:
            config['id'] = existing.id
            await db.execute(update(QuantLongbridgeConfig), [config])
            await db.flush()
            return existing
        db_config = QuantLongbridgeConfig(**{k: v for k, v in config.items() if k != 'id'})
        db.add(db_config)
        await db.flush()
        return db_config


class QuantSnapshotDao:
    """因子快照与读模型聚合快照。"""

    @classmethod
    async def upsert_factor_snapshot(cls, db: AsyncSession, item: dict[str, Any]) -> QuantFactorSnapshot:
        existing = (
            (
                await db.execute(
                    select(QuantFactorSnapshot).where(
                        QuantFactorSnapshot.symbol == item['symbol'],
                        QuantFactorSnapshot.market == item['market'],
                    )
                )
            )
            .scalars()
            .first()
        )
        now = datetime.now()
        if existing:
            existing.as_of = item.get('as_of')
            existing.score_total = item.get('score_total')
            existing.risk_level = item.get('risk_level')
            existing.trend_direction = item.get('trend_direction')
            existing.alpha101_count = item.get('alpha101_count') or 0
            existing.alpha158_count = item.get('alpha158_count') or 0
            existing.score_json = item.get('score_json')
            existing.alpha_json = item.get('alpha_json')
            existing.create_time = now
            await db.flush()
            return existing
        row = QuantFactorSnapshot(create_time=now, **item)
        db.add(row)
        await db.flush()
        return row

    @classmethod
    async def list_latest_factor_snapshots(
        cls, db: AsyncSession, limit: int = 80
    ) -> list[QuantFactorSnapshot]:
        limit = max(1, min(int(limit or 80), 200))
        rows = (
            (
                await db.execute(
                    select(QuantFactorSnapshot)
                    .order_by(desc(QuantFactorSnapshot.score_total), desc(QuantFactorSnapshot.create_time))
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    @classmethod
    async def add_readmodel_snapshot(
        cls, db: AsyncSession, snapshot_type: str, payload_json: str
    ) -> QuantReadmodelSnapshot:
        row = QuantReadmodelSnapshot(
            snapshot_type=snapshot_type,
            payload_json=payload_json,
            create_time=datetime.now(),
        )
        db.add(row)
        await db.flush()
        return row

    @classmethod
    async def get_latest_readmodel(
        cls, db: AsyncSession, snapshot_type: str
    ) -> QuantReadmodelSnapshot | None:
        return (
            (
                await db.execute(
                    select(QuantReadmodelSnapshot)
                    .where(QuantReadmodelSnapshot.snapshot_type == snapshot_type)
                    .order_by(desc(QuantReadmodelSnapshot.create_time))
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
