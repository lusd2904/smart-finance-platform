"""收盘后次日策略清单、勾选模拟开仓、加入量化后持续自动交易。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from exceptions.exception import ServiceException
from module_market.dao.market_dao import MarketWatchlistDao
from module_quant.dao.quant_dao import QuantDailyListDao
from module_quant.service.longbridge_service import LongbridgeService
from module_quant.service.quant_service import QuantService
from module_quant.service.strategy_service import StrategyService
from utils.log_util import logger
from utils.trading_calendar import is_cn_trading_day, is_market_session_open, next_cn_trading_day, today_cn

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

MAX_SCAN_SYMBOLS = 80
MAX_POSITION_RATIO = 0.15
MAX_NAME_NOTIONAL = 8000.0
LOT = {'US': 1, 'HK': 100, 'CN': 100}


def serialize_list(row: Any, items: list[Any] | None = None) -> dict[str, Any]:
    data = {
        'listId': row.list_id,
        'userId': row.user_id,
        'scanDate': row.scan_date.isoformat() if row.scan_date else None,
        'tradeDate': row.trade_date.isoformat() if row.trade_date else None,
        'profile': row.profile,
        'status': row.status,
        'autoEnabled': row.auto_enabled == '1',
        'itemCount': row.item_count,
        'message': row.message,
        'items': [],
    }
    if items is not None:
        data['items'] = [serialize_item(it) for it in items]
        data['itemCount'] = len(data['items'])
    return data


def serialize_item(row: Any) -> dict[str, Any]:
    return {
        'itemId': row.item_id,
        'listId': row.list_id,
        'symbol': row.symbol,
        'market': row.market,
        'name': row.name,
        'signal': row.signal,
        'score': row.score,
        'confidence': row.confidence,
        'reason': row.reason,
        'selected': row.selected == '1',
        'autoTrade': row.auto_trade == '1',
        'status': row.status,
        'side': row.side,
        'quantity': row.quantity,
        'price': row.price,
        'orderId': row.order_id,
        'error': row.error,
    }


class DailyListService:
    @classmethod
    async def get_latest(cls, db: AsyncSession, user_id: int) -> dict[str, Any]:
        row = await QuantDailyListDao.latest_for_user(db, user_id)
        if not row:
            return {'list': None, 'items': [], 'message': '暂无次日策略清单，等待收盘扫描或手动扫描'}
        items = await QuantDailyListDao.list_items(db, row.list_id)
        return {'list': serialize_list(row, items), 'message': row.message}

    @classmethod
    async def scan_user(cls, db: AsyncSession, user_id: int, profile: str = 'balanced') -> dict[str, Any]:
        scan_date = today_cn()
        if not is_cn_trading_day(scan_date):
            trade_date = next_cn_trading_day(scan_date)
            row = await QuantDailyListDao.upsert_list(
                db,
                {
                    'user_id': user_id,
                    'scan_date': scan_date,
                    'trade_date': trade_date,
                    'profile': profile,
                    'status': 'skipped',
                    'item_count': 0,
                    'message': '非交易日，不生成可交易清单',
                },
            )
            await QuantDailyListDao.replace_items(db, row.list_id, [])
            await db.commit()
            return serialize_list(row, [])

        trade_date = next_cn_trading_day(scan_date)
        watch = await MarketWatchlistDao.get_enabled(db, user_id=user_id)
        targets = [{'symbol': w.symbol, 'market': (w.market or 'US').upper(), 'name': w.name} for w in watch][
            :MAX_SCAN_SYMBOLS
        ]
        if not targets:
            row = await QuantDailyListDao.upsert_list(
                db,
                {
                    'user_id': user_id,
                    'scan_date': scan_date,
                    'trade_date': trade_date,
                    'profile': profile,
                    'status': 'empty',
                    'item_count': 0,
                    'message': '自选为空，未生成清单',
                },
            )
            await QuantDailyListDao.replace_items(db, row.list_id, [])
            await db.commit()
            return serialize_list(row, [])

        profile_cfg = await QuantService.load_profile_config(db, profile, user_id=user_id)
        cycle = await StrategyService.run_strategy_cycle_async(targets, profile, 'US', profile_cfg)
        name_map = {(t['symbol'], t['market']): t.get('name') for t in targets}
        buy_rows = [s for s in (cycle.get('signals') or []) if str(s.get('signal') or '').upper() == 'BUY']
        if not buy_rows:
            row = await QuantDailyListDao.upsert_list(
                db,
                {
                    'user_id': user_id,
                    'scan_date': scan_date,
                    'trade_date': trade_date,
                    'profile': profile,
                    'status': 'empty',
                    'item_count': 0,
                    'message': '策略无买入标的，静默不生成可交易清单',
                },
            )
            await QuantDailyListDao.replace_items(db, row.list_id, [])
            await db.commit()
            return serialize_list(row, [])

        now = datetime.now()
        row = await QuantDailyListDao.upsert_list(
            db,
            {
                'user_id': user_id,
                'scan_date': scan_date,
                'trade_date': trade_date,
                'profile': profile,
                'status': 'open',
                'item_count': len(buy_rows),
                'message': f'已生成 {len(buy_rows)} 只次日标的',
            },
        )
        payload = []
        for signal in buy_rows:
            symbol = str(signal.get('symbol') or '').upper()
            market = str(signal.get('market') or 'US').upper()
            payload.append(
                {
                    'list_id': row.list_id,
                    'user_id': user_id,
                    'trade_date': trade_date,
                    'symbol': symbol,
                    'market': market,
                    'name': name_map.get((symbol, market)),
                    'signal': 'BUY',
                    'score': signal.get('score'),
                    'confidence': signal.get('confidence'),
                    'reason': (signal.get('reason') or '')[:500],
                    'selected': '0',
                    'auto_trade': '0',
                    'status': 'listed',
                    'side': 'BUY',
                    'create_time': now,
                    'update_time': now,
                }
            )
        items = await QuantDailyListDao.replace_items(db, row.list_id, payload)
        await db.commit()
        return serialize_list(row, items)

    @classmethod
    async def scan_all_users(cls, db: AsyncSession, profile: str | None = None) -> dict[str, Any]:
        if not is_cn_trading_day():
            return {'skipped': True, 'reason': 'non_trading_day', 'message': '非交易日跳过'}
        users = await QuantDailyListDao.distinct_watchlist_users(db)
        from module_trade.service.platform_ext_service import PlatformExtService

        async def _scan_one(uid: int) -> dict[str, Any]:
            try:
                code = await PlatformExtService.resolve_profile(db, uid, profile)
                return await cls.scan_user(db, uid, code)
            except Exception as exc:
                logger.warning(f'[次日清单] user={uid} 扫描失败: {exc}')
                return {'userId': uid, 'error': str(exc)}

        results = [await _scan_one(uid) for uid in users]
        return {'skipped': False, 'userCount': len(users), 'results': results}

    @classmethod
    async def _account_trade_ready(cls, db: AsyncSession, user_id: int) -> tuple[bool, str]:
        """真实下单必须：本账户已配长桥 Key，且策略配置里的自动交易已打开。"""
        from module_quant.dao.quant_dao import QuantLongbridgeConfigDao
        from module_trade.service.auto_trade_service import AutoTradeService

        settings = await AutoTradeService.load_user_trade_settings(db, user_id)
        if settings.get('auto_trade_enabled'):
            await LongbridgeService.ensure_credentials_from_db(db, user_id)
            return True, ''
        row = await QuantLongbridgeConfigDao.get_config(db, int(user_id))
        has_keys = bool(row and str(getattr(row, 'app_key', '') or '') and str(getattr(row, 'access_token', '') or ''))
        if not has_keys:
            return False, '未配置长桥账户 Key，无法打开自动交易'
        return False, '请先在「量化交易 / 策略配置」打开本账户自动交易'

    @classmethod
    async def open_selected(
        cls, db: AsyncSession, user_id: int, item_ids: list[int], auto_join: bool = False
    ) -> dict[str, Any]:
        if not item_ids:
            raise ServiceException(message='请先勾选标的，禁止整表默认全开')
        latest = await QuantDailyListDao.latest_for_user(db, user_id)
        if not latest or latest.status != 'open':
            raise ServiceException(message='没有可交易的次日清单')
        ready, reason = await cls._account_trade_ready(db, user_id)
        if not ready:
            raise ServiceException(message=reason)
        await LongbridgeService.ensure_credentials_from_db(db, user_id)
        outcomes = []
        for item_id in item_ids:
            row = await QuantDailyListDao.get_item(db, int(item_id), user_id)
            if not row or row.list_id != latest.list_id:
                outcomes.append({'itemId': item_id, 'ok': False, 'message': '条目不属于当前清单'})
                continue
            row.selected = '1'
            if auto_join:
                row.auto_trade = '1'
                await cls._join_quant(db, row.symbol, row.market, user_id)
            result = await cls._place_or_queue(db, row, user_id)
            outcomes.append(result)
        if auto_join:
            latest.auto_enabled = '1'
        await db.commit()
        items = await QuantDailyListDao.list_items(db, latest.list_id)
        return {'list': serialize_list(latest, items), 'outcomes': outcomes}

    @classmethod
    async def set_auto(cls, db: AsyncSession, user_id: int, enabled: bool, item_ids: list[int] | None = None) -> dict[str, Any]:
        latest = await QuantDailyListDao.latest_for_user(db, user_id)
        if not latest:
            raise ServiceException(message='暂无清单')
        if enabled:
            ready, reason = await cls._account_trade_ready(db, user_id)
            if not ready:
                raise ServiceException(message=reason)
        latest.auto_enabled = '1' if enabled else '0'
        items = await QuantDailyListDao.list_items(db, latest.list_id)
        target_ids = {int(i) for i in (item_ids or [])}
        for row in items:
            if target_ids and row.item_id not in target_ids:
                continue
            row.auto_trade = '1' if enabled else '0'
            if enabled:
                await cls._join_quant(db, row.symbol, row.market, user_id)
        await db.commit()
        items = await QuantDailyListDao.list_items(db, latest.list_id)
        return serialize_list(latest, items)

    @classmethod
    async def execute_queued(cls, db: AsyncSession) -> dict[str, Any]:
        rows = await QuantDailyListDao.list_queued(db)
        done = []
        allowed: dict[int, bool] = {}
        skipped_users: list[int] = []
        for row in rows:
            if not is_market_session_open(row.market):
                continue
            uid = int(row.user_id)
            if uid not in allowed:
                ready, _reason = await cls._account_trade_ready(db, uid)
                allowed[uid] = ready
                if not ready:
                    skipped_users.append(uid)
            if not allowed[uid]:
                continue
            await LongbridgeService.ensure_credentials_from_db(db, uid)
            done.append(await cls._place_or_queue(db, row, uid, force_submit=True))
        await db.commit()
        return {'count': len(done), 'outcomes': done, 'skippedUsers': skipped_users}

    @classmethod
    async def rebalance_auto(cls, db: AsyncSession, user_id: int) -> dict[str, Any]:
        """
        自动调仓（护栏版）：
        - 只卖出「该用户历史上通过次日清单自动买入」且已不在本期自动清单的持仓；
        - 手动买入、清单外、其他账户来源的持仓一律不碰；
        - 本期自动清单里未持有的标的照常买入。
        """
        latest = await QuantDailyListDao.latest_for_user(db, user_id)
        if not latest or latest.auto_enabled != '1':
            return {'skipped': True, 'reason': 'auto_disabled'}
        ready, reason = await cls._account_trade_ready(db, user_id)
        if not ready:
            return {'skipped': True, 'reason': 'account_auto_disabled', 'message': reason}
        from module_trade.service.order_guard import halt_block_reason

        halt_msg = await halt_block_reason()
        if halt_msg:
            return {'skipped': True, 'reason': 'halted', 'message': halt_msg}
        await LongbridgeService.ensure_credentials_from_db(db, user_id)
        items = [it for it in await QuantDailyListDao.list_items(db, latest.list_id) if it.auto_trade == '1']
        wanted = {(it.symbol.upper(), (it.market or 'US').upper()) for it in items}
        # 卖出白名单：只有本系统自动买入过的标的才允许被自动卖出
        sellable = await QuantDailyListDao.auto_bought_symbols(db, user_id)
        positions = (await LongbridgeService.get_positions_async()).get('positions') or []
        held = {}
        for pos in positions:
            raw = str(pos.get('symbol') or '')
            qty = float(pos.get('quantity') or 0)
            if qty <= 0:
                continue
            symbol, market = _split_lb_symbol(raw)
            held[(symbol, market)] = pos
        outcomes = []
        skipped_guard = []
        for key, pos in held.items():
            if key in wanted or key not in sellable:
                if key not in sellable and key not in wanted:
                    skipped_guard.append({'symbol': key[0], 'market': key[1], 'reason': '非自动买入持仓，卖出护栏跳过'})
                continue
            symbol, market = key
            qty = float(pos.get('quantity') or 0)
            res = await LongbridgeService.submit_order_async(
                symbol, 'sell', qty, order_type='MO', market=market
            )
            outcomes.append({'symbol': symbol, 'side': 'SELL', **res})
        for item in items:
            key = (item.symbol.upper(), (item.market or 'US').upper())
            if key in held:
                continue
            outcomes.append(await cls._place_or_queue(db, item, user_id))
        await db.commit()
        return {'outcomes': outcomes, 'guardSkipped': skipped_guard}

    @classmethod
    async def _join_quant(cls, db: AsyncSession, symbol: str, market: str, user_id: int | None = None) -> None:
        if not user_id:
            return
        from module_market.entity.vo.market_vo import AddMarketWatchlistModel
        from module_market.service.watchlist_service import MarketWatchlistService

        await MarketWatchlistService.add_services(
            db,
            AddMarketWatchlistModel(symbol=symbol, market=market, note='次日清单自动交易'),
            user_id,
        )

    @classmethod
    async def _place_or_queue(
        cls, db: AsyncSession, row: Any, user_id: int, force_submit: bool = False
    ) -> dict[str, Any]:
        if row.status in {'submitted', 'filled'} and row.order_id:
            return {'itemId': row.item_id, 'ok': True, 'idempotent': True, 'message': '当日已下单', 'orderId': row.order_id}
        if row.status == 'skipped':
            return {'itemId': row.item_id, 'ok': False, 'message': row.error or '已跳过'}
        if not is_cn_trading_day(today_cn()) and (row.market or '').upper() == 'CN':
            row.status = 'skipped'
            row.error = '非交易日禁止开仓'
            return {'itemId': row.item_id, 'ok': False, 'message': row.error}
        if not force_submit and not is_market_session_open(row.market):
            row.status = 'queued'
            row.error = None
            return {'itemId': row.item_id, 'ok': True, 'queued': True, 'message': '已排队至下一交易日开盘'}

        qty = await cls._size_order(row)
        if qty <= 0:
            row.status = 'skipped'
            row.error = '仓位不足或无法计算数量'
            return {'itemId': row.item_id, 'ok': False, 'message': row.error}
        from module_trade.service.order_guard import halt_block_reason

        halt_msg = await halt_block_reason()
        if halt_msg:
            row.status = 'skipped'
            row.error = halt_msg
            return {'itemId': row.item_id, 'ok': False, 'message': halt_msg}
        result = await LongbridgeService.submit_order_async(
            row.symbol, 'buy', qty, order_type='MO', market=row.market
        )
        row.quantity = qty
        if result.get('ok'):
            row.status = 'submitted'
            row.order_id = str(result.get('orderId') or '')
            row.error = None
        else:
            row.status = 'rejected'
            row.error = str(result.get('message') or '下单失败')[:500]
        row.update_time = datetime.now()
        return {'itemId': row.item_id, 'ok': bool(result.get('ok')), 'message': result.get('message'), 'orderId': row.order_id}

    @classmethod
    async def _size_order(cls, row: Any) -> int:
        account = await LongbridgeService.get_account_balance_async()
        net = 0.0
        for bal in account.get('balances') or []:
            net = max(net, float(bal.get('netAssets') or bal.get('availableCash') or 0))
        if net <= 0:
            return LOT.get((row.market or 'US').upper(), 1)
        notional = min(net * MAX_POSITION_RATIO, MAX_NAME_NOTIONAL)
        price = float(row.price or 0)
        if price <= 0:
            quotes = LongbridgeService.get_realtime_quote(
                [LongbridgeService.to_longbridge_symbol(row.symbol, row.market)]
            )
            qrows = quotes.get('quotes') or []
            if qrows:
                price = float(qrows[0].get('lastDone') or qrows[0].get('last') or 0)
        if price <= 0:
            return LOT.get((row.market or 'US').upper(), 1)
        lot = LOT.get((row.market or 'US').upper(), 1)
        qty = int(notional / price)
        qty = max(lot, qty - (qty % lot))
        return qty


def _split_lb_symbol(raw: str) -> tuple[str, str]:
    text = str(raw or '').upper()
    if '.' in text:
        code, suffix = text.rsplit('.', 1)
        market = 'CN' if suffix in {'SH', 'SZ'} else suffix
        return code, market
    return text, 'US'
