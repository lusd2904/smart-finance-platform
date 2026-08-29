import math
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import and_, delete, desc, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from common.vo import PageModel
from module_quant.entity.do.quant_do import (
    QuantAlpha101Value,
    QuantAlpha158Value,
    QuantDailyList,
    QuantDailyListItem,
    QuantFactorQc,
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

ADMIN_LONGBRIDGE_USER_ID = 1


class QuantWatchlistDao:
    """
    量化自选池数据库操作层
    """

    @classmethod
    async def get_watchlist(
        cls,
        db: AsyncSession,
        query_object: QuantWatchlistPageQueryModel,
        is_page: bool = False,
        user_id: int | None = None,
    ) -> PageModel | list[dict[str, Any]]:
        """根据查询参数获取自选池列表（user_id 非空时按账号隔离）"""
        query = (
            select(QuantWatchlist)
            .where(
                QuantWatchlist.user_id == user_id if user_id is not None else True,
                QuantWatchlist.symbol.like(f'%{query_object.symbol}%') if query_object.symbol else True,
                QuantWatchlist.market == query_object.market if query_object.market else True,
                QuantWatchlist.enabled == query_object.enabled if query_object.enabled else True,
            )
            .order_by(desc(QuantWatchlist.create_time))
        )
        return await PageUtil.paginate(db, query, query_object.page_num, query_object.page_size, is_page)

    @classmethod
    async def get_enabled_symbols(cls, db: AsyncSession, user_id: int | None = None) -> list[Any]:
        """启用自选：以行情自选为真源。"""
        from module_market.dao.market_dao import MarketWatchlistDao

        return await MarketWatchlistDao.get_enabled(db, user_id=user_id)

    @classmethod
    async def distinct_users(cls, db: AsyncSession) -> list[int]:
        """有启用自选的账号ID列表（定时任务逐用户跑策略用）"""
        from module_market.dao.market_dao import MarketWatchlistDao

        return await MarketWatchlistDao.distinct_users(db)

    @classmethod
    async def get_by_symbol(
        cls, db: AsyncSession, symbol: str, market: str, user_id: int | None = None
    ) -> QuantWatchlist | None:
        """按代码+市场查重（user_id 非空时限定在该账号内）"""
        query = select(QuantWatchlist).where(QuantWatchlist.symbol == symbol, QuantWatchlist.market == market)
        if user_id is not None:
            query = query.where(QuantWatchlist.user_id == user_id)
        return (await db.execute(query)).scalars().first()

    @classmethod
    async def add_watchlist(cls, db: AsyncSession, item: dict) -> QuantWatchlist:
        """新增自选标的"""
        db_item = QuantWatchlist(**item)
        db.add(db_item)
        await db.flush()
        return db_item

    @classmethod
    async def delete_watchlist(cls, db: AsyncSession, ids: list[int], user_id: int | None = None) -> None:
        """删除自选标的（user_id 非空时只能删自己的）"""
        query = delete(QuantWatchlist).where(QuantWatchlist.id.in_(ids))
        if user_id is not None:
            query = query.where(QuantWatchlist.user_id == user_id)
        await db.execute(query)


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
        cls,
        db: AsyncSession,
        query_object: QuantStrategyRunPageQueryModel,
        is_page: bool = False,
        user_id: int | None = None,
    ) -> PageModel | list[dict[str, Any]]:
        """获取策略运行记录分页列表"""
        conds = []
        if query_object.strategy_profile:
            conds.append(QuantStrategyRun.strategy_profile == query_object.strategy_profile)
        if query_object.begin_time and query_object.end_time:
            conds.append(
                QuantStrategyRun.create_time.between(
                    datetime.combine(datetime.strptime(query_object.begin_time, '%Y-%m-%d'), time(0, 0, 0)),
                    datetime.combine(datetime.strptime(query_object.end_time, '%Y-%m-%d'), time(23, 59, 59)),
                )
            )
        if user_id:
            conds.append(QuantStrategyRun.user_id == int(user_id))
        query = select(QuantStrategyRun).where(*conds).order_by(desc(QuantStrategyRun.create_time))
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
    async def get_signals_by_runs(
        cls, db: AsyncSession, run_ids: list[int]
    ) -> dict[int, list[QuantStrategySignal]]:
        """批量获取多次运行的信号，按 run_id 分组（消除列表页 1+N 查询）"""
        if not run_ids:
            return {}
        rows = (
            (
                await db.execute(
                    select(QuantStrategySignal)
                    .where(QuantStrategySignal.run_id.in_([int(r) for r in run_ids]))
                    .order_by(desc(QuantStrategySignal.score))
                )
            )
            .scalars()
            .all()
        )
        grouped: dict[int, list[QuantStrategySignal]] = {}
        for row in rows:
            grouped.setdefault(int(row.run_id), []).append(row)
        return grouped

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
        cls, db: AsyncSession, symbol: str, user_id: int | None = None
    ) -> QuantStrategySignal | None:
        """获取某标的最近一次策略信号（user_id 非空时只看该账号自己的信号）"""
        query = select(QuantStrategySignal).where(QuantStrategySignal.symbol == symbol)
        if user_id is not None:
            query = query.where(QuantStrategySignal.user_id == int(user_id))
        return (
            (
                await db.execute(
                    query.order_by(desc(QuantStrategySignal.create_time), desc(QuantStrategySignal.signal_id)).limit(1)
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_scan_runs(
        cls, db: AsyncSession, limit: int = 20, user_id: int | None = None
    ) -> list[QuantStrategyRun]:
        """扫描运行台账列表（最近 N 条，按账户隔离）"""
        limit = max(1, min(int(limit or 20), 100))
        stmt = select(QuantStrategyRun)
        if user_id:
            stmt = stmt.where(QuantStrategyRun.user_id == int(user_id))
        rows = (
            (await db.execute(stmt.order_by(desc(QuantStrategyRun.create_time)).limit(limit)))
            .scalars()
            .all()
        )
        return list(rows)


ADMIN_LONGBRIDGE_USER_ID = 1


class QuantLongbridgeConfigDao:
    """
    长桥凭据配置数据库操作层（按 user_id 一行）
    """

    @classmethod
    def _resolve_user_id(cls, user_id: int | None, config: dict | None = None) -> int | None:
        if user_id is not None:
            return int(user_id)
        if config and config.get('user_id') is not None:
            return int(config['user_id'])
        return None

    @classmethod
    async def get_config(cls, db: AsyncSession, user_id: int | None = None) -> QuantLongbridgeConfig | None:
        """获取指定用户的长桥凭据。user_id 为空则不回退管理员。"""
        target_id = cls._resolve_user_id(user_id)
        if target_id is None:
            return None
        return (
            (
                await db.execute(
                    select(QuantLongbridgeConfig)
                    .where(QuantLongbridgeConfig.user_id == target_id)
                    .order_by(QuantLongbridgeConfig.id)
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def save_config(cls, db: AsyncSession, config: dict, user_id: int | None = None) -> QuantLongbridgeConfig:
        """按 user_id 保存长桥凭据（存在则更新，不存在则新增）。"""
        target_id = cls._resolve_user_id(user_id, config)
        if target_id is None:
            raise ValueError('长桥凭据必须指定 user_id')
        config = {**config, 'user_id': target_id}
        existing = await cls.get_config(db, target_id)
        if existing:
            config['id'] = existing.id
            await db.execute(update(QuantLongbridgeConfig), [config])
            await db.flush()
            return existing
        db_config = QuantLongbridgeConfig(**{k: v for k, v in config.items() if k != 'id'})
        db.add(db_config)
        await db.flush()
        return db_config

    @classmethod
    async def list_configured_user_ids(cls, db: AsyncSession) -> list[int]:
        """已填写长桥 Key/Token 的账号。"""
        rows = (
            (
                await db.execute(
                    select(QuantLongbridgeConfig.user_id).where(
                        QuantLongbridgeConfig.app_key.is_not(None),
                        QuantLongbridgeConfig.app_key != '',
                        QuantLongbridgeConfig.access_token.is_not(None),
                        QuantLongbridgeConfig.access_token != '',
                    )
                )
            )
            .scalars()
            .all()
        )
        return [int(u) for u in rows if u]

    @classmethod
    async def save_trade_settings(
        cls,
        db: AsyncSession,
        user_id: int,
        *,
        auto_trade_enabled: bool,
        daily_buy_ratio: float,
        max_symbol_position_pct: float = 0.10,
    ) -> QuantLongbridgeConfig:
        """只改当前用户的交易开关与仓位比例，不动凭据。"""
        target_id = int(user_id)
        ratio = max(0.05, min(0.50, float(daily_buy_ratio or 0.20)))
        try:
            symbol_pct = float(max_symbol_position_pct if max_symbol_position_pct is not None else 0.10)
        except (TypeError, ValueError):
            symbol_pct = 0.10
        symbol_pct = max(0.05, min(0.30, symbol_pct))
        flag = '1' if auto_trade_enabled else '0'
        existing = await cls.get_config(db, target_id)
        now = datetime.now()
        if existing:
            existing.auto_trade_enabled = flag
            existing.daily_buy_ratio = ratio
            existing.max_symbol_position_pct = symbol_pct
            existing.update_time = now
            await db.flush()
            return existing
        row = QuantLongbridgeConfig(
            user_id=target_id,
            app_key='',
            app_secret='',
            access_token='',
            region='cn',
            auto_trade_enabled=flag,
            daily_buy_ratio=ratio,
            max_symbol_position_pct=symbol_pct,
            update_time=now,
        )
        db.add(row)
        await db.flush()
        return row


def _apply_factor_snapshot_fields(row: QuantFactorSnapshot, item: dict[str, Any], now: datetime) -> None:
    row.as_of = item.get('as_of')
    row.score_total = item.get('score_total')
    row.risk_level = item.get('risk_level')
    row.trend_direction = item.get('trend_direction')
    row.alpha101_count = item.get('alpha101_count') or 0
    row.alpha158_count = item.get('alpha158_count') or 0
    row.score_json = item.get('score_json')
    row.alpha_json = item.get('alpha_json')
    row.create_time = now


def _symbol_market_clause(model: Any, pairs: list[tuple[str, str]]) -> Any:
    by_market: dict[str, list[str]] = {}
    for symbol, market in pairs:
        by_market.setdefault(market or 'US', []).append(symbol)
    return or_(
        *[
            and_(model.market == market, model.symbol.in_(list(dict.fromkeys(symbols))))
            for market, symbols in by_market.items()
        ]
    )


def _alpha_value_rows(
    model: Any,
    symbol: str,
    market: str,
    as_of_key: str,
    payload: dict[str, Any] | None,
    now: datetime,
) -> list[Any]:
    rows = []
    for key, raw in (payload or {}).items():
        if isinstance(raw, dict):
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isnan(value):
            continue
        rows.append(
            model(
                symbol=symbol,
                market=market or 'US',
                as_of=as_of_key,
                factor_key=str(key)[:32],
                factor_value=value,
                create_time=now,
            )
        )
    return rows


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
            _apply_factor_snapshot_fields(existing, item, now)
            await db.flush()
            return existing
        row = QuantFactorSnapshot(create_time=now, **item)
        db.add(row)
        await db.flush()
        return row

    @classmethod
    async def upsert_factor_snapshots_bulk(
        cls, db: AsyncSession, items: list[dict[str, Any]]
    ) -> list[QuantFactorSnapshot]:
        if not items:
            return []
        keyed: dict[tuple[str, str], dict[str, Any]] = {}
        for item in items:
            keyed[(item['symbol'], item['market'])] = item
        uniq = list(keyed.values())
        existing_rows = (
            (
                await db.execute(
                    select(QuantFactorSnapshot).where(
                        _symbol_market_clause(QuantFactorSnapshot, list(keyed.keys()))
                    )
                )
            )
            .scalars()
            .all()
        )
        existing_map = {(row.symbol, row.market): row for row in existing_rows}
        now = datetime.now()
        result: list[QuantFactorSnapshot] = []
        new_rows: list[QuantFactorSnapshot] = []
        for item in uniq:
            existing = existing_map.get((item['symbol'], item['market']))
            if existing:
                _apply_factor_snapshot_fields(existing, item, now)
                result.append(existing)
                continue
            row = QuantFactorSnapshot(create_time=now, **item)
            new_rows.append(row)
            result.append(row)
        if new_rows:
            db.add_all(new_rows)
        await db.flush()
        return result

    @classmethod
    async def get_factor_snapshot(
        cls, db: AsyncSession, symbol: str, market: str = 'US'
    ) -> QuantFactorSnapshot | None:
        return (
            (
                await db.execute(
                    select(QuantFactorSnapshot).where(
                        QuantFactorSnapshot.symbol == symbol,
                        QuantFactorSnapshot.market == market,
                    )
                )
            )
            .scalars()
            .first()
        )

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
    async def replace_alpha_values(
        cls,
        db: AsyncSession,
        symbol: str,
        market: str,
        as_of: str,
        alpha101: dict[str, Any] | None,
        alpha158: dict[str, Any] | None,
    ) -> None:
        """按标的覆盖写入 Alpha101/158 明细行，不再把整包 JSON 塞进 TEXT。"""
        as_of_key = (as_of or datetime.now().strftime('%Y-%m-%d'))[:16]
        now = datetime.now()
        for model, payload in (
            (QuantAlpha101Value, alpha101),
            (QuantAlpha158Value, alpha158),
        ):
            await db.execute(delete(model).where(model.symbol == symbol, model.market == market))
            rows = _alpha_value_rows(model, symbol, market, as_of_key, payload, now)
            if rows:
                db.add_all(rows)
        await db.flush()

    @classmethod
    async def replace_alpha_values_bulk(cls, db: AsyncSession, snaps: list[dict[str, Any]]) -> None:
        if not snaps:
            return
        keyed: dict[tuple[str, str], dict[str, Any]] = {}
        for snap in snaps:
            keyed[(snap['symbol'], snap.get('market') or 'US')] = snap
        pairs = list(keyed.keys())
        now = datetime.now()
        for model in (QuantAlpha101Value, QuantAlpha158Value):
            await db.execute(delete(model).where(_symbol_market_clause(model, pairs)))
        rows: list[Any] = []
        for (symbol, market), snap in keyed.items():
            as_of_key = (snap.get('asOf') or datetime.now().strftime('%Y-%m-%d'))[:16]
            rows.extend(_alpha_value_rows(QuantAlpha101Value, symbol, market, as_of_key, snap.get('alpha101'), now))
            rows.extend(_alpha_value_rows(QuantAlpha158Value, symbol, market, as_of_key, snap.get('alpha158'), now))
        if rows:
            db.add_all(rows)
        await db.flush()

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


class QuantFactorQcDao:
    """Alphalens 风格因子质检结果。"""

    @classmethod
    async def upsert(cls, db: AsyncSession, item: dict[str, Any]) -> QuantFactorQc:
        existing = (
            (
                await db.execute(
                    select(QuantFactorQc).where(
                        QuantFactorQc.factor_key == item['factor_key'],
                        QuantFactorQc.market == item['market'],
                        QuantFactorQc.horizon == item['horizon'],
                    )
                )
            )
            .scalars()
            .first()
        )
        now = datetime.now()
        if existing:
            existing.factor_label = item.get('factor_label')
            existing.ic_mean = item.get('ic_mean')
            existing.ic_std = item.get('ic_std')
            existing.ir = item.get('ir')
            existing.spread = item.get('spread')
            existing.sample_dates = item.get('sample_dates') or 0
            existing.symbol_count = item.get('symbol_count') or 0
            existing.as_of = item.get('as_of')
            existing.quantile_json = item.get('quantile_json')
            existing.payload_json = item.get('payload_json')
            existing.create_time = now
            await db.flush()
            return existing
        row = QuantFactorQc(create_time=now, **item)
        db.add(row)
        await db.flush()
        return row

    @classmethod
    async def list_latest(cls, db: AsyncSession, market: str = 'US') -> list[QuantFactorQc]:
        rows = (
            (
                await db.execute(
                    select(QuantFactorQc)
                    .where(QuantFactorQc.market == (market or 'US').upper())
                    .order_by(QuantFactorQc.factor_key, QuantFactorQc.horizon)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)


class QuantDailyListDao:
    @classmethod
    async def get_by_trade_date(cls, db: AsyncSession, user_id: int, trade_date: date) -> QuantDailyList | None:
        return (
            (
                await db.execute(
                    select(QuantDailyList).where(
                        QuantDailyList.user_id == int(user_id), QuantDailyList.trade_date == trade_date
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def latest_for_user(cls, db: AsyncSession, user_id: int) -> QuantDailyList | None:
        return (
            (
                await db.execute(
                    select(QuantDailyList)
                    .where(QuantDailyList.user_id == int(user_id))
                    .order_by(desc(QuantDailyList.trade_date), desc(QuantDailyList.list_id))
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def upsert_list(cls, db: AsyncSession, values: dict[str, Any]) -> QuantDailyList:
        existing = await cls.get_by_trade_date(db, values['user_id'], values['trade_date'])
        now = datetime.now()
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            existing.update_time = now
            await db.flush()
            return existing
        row = QuantDailyList(create_time=now, update_time=now, **values)
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    @classmethod
    async def list_items(cls, db: AsyncSession, list_id: int) -> list[QuantDailyListItem]:
        rows = (
            (
                await db.execute(
                    select(QuantDailyListItem)
                    .where(QuantDailyListItem.list_id == int(list_id))
                    .order_by(desc(QuantDailyListItem.confidence), QuantDailyListItem.item_id)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    @classmethod
    async def get_item(cls, db: AsyncSession, item_id: int, user_id: int) -> QuantDailyListItem | None:
        return (
            (
                await db.execute(
                    select(QuantDailyListItem).where(
                        QuantDailyListItem.item_id == int(item_id),
                        QuantDailyListItem.user_id == int(user_id),
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def replace_items(cls, db: AsyncSession, list_id: int, items: list[dict[str, Any]]) -> list[QuantDailyListItem]:
        await db.execute(delete(QuantDailyListItem).where(QuantDailyListItem.list_id == int(list_id)))
        rows = [QuantDailyListItem(**item) for item in items]
        db.add_all(rows)
        await db.flush()
        return rows

    @classmethod
    async def list_queued(cls, db: AsyncSession) -> list[QuantDailyListItem]:
        rows = (
            (await db.execute(select(QuantDailyListItem).where(QuantDailyListItem.status == 'queued')))
            .scalars()
            .all()
        )
        return list(rows)

    @classmethod
    async def auto_bought_symbols(
        cls, db: AsyncSession, user_id: int, statuses: tuple[str, ...] = ('submitted', 'filled', 'queued')
    ) -> set[tuple[str, str]]:
        """
        该用户历史上通过次日清单自动买入过的 (symbol, market) 集合。
        rebalance 卖出只允许清这些标的——清单外/手动买的持仓一律不碰。
        """
        rows = (
            (
                await db.execute(
                    select(QuantDailyListItem.symbol, QuantDailyListItem.market).where(
                        QuantDailyListItem.user_id == int(user_id),
                        QuantDailyListItem.side == 'BUY',
                        QuantDailyListItem.status.in_(statuses),
                        QuantDailyListItem.order_id.isnot(None),
                        QuantDailyListItem.order_id != '',
                    )
                )
            )
            .all()
        )
        return {(str(s).upper(), str(m or 'US').upper()) for s, m in rows}

    @classmethod
    async def distinct_watchlist_users(cls, db: AsyncSession) -> list[int]:
        from module_market.entity.do.market_do import MarketWatchlist

        rows = (
            await db.execute(select(MarketWatchlist.user_id).where(MarketWatchlist.enabled == '1').distinct())
        ).all()
        return [int(r[0]) for r in rows if r[0]]
