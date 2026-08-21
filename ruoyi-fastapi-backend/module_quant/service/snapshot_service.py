"""
Phase 2 定时扫描与读模型快照：
- DailyMarketScan：全市场日频因子入库
- PositionMonitor：持仓止损/异动
- IndicatorRefresh：行情看板与指标快照
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from module_market.constant.instruments import TARGET_INSTRUMENTS
from module_quant.dao.quant_dao import QuantSnapshotDao
from module_quant.service.alpha_engine import attach_cross_section_alphas
from module_quant.service.factor_service import FactorService
from module_quant.service.readmodel_service import (
    BOARD_TTL,
    FACTOR_TTL,
    OVERVIEW_TTL,
    ReadModelService,
)
from utils.influx_util import InfluxUtil
from utils.log_util import logger

STOP_LOSS_PCT = -8.0


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


class SnapshotService:
    @classmethod
    def _scan_universe(cls) -> list[tuple[str, str, str]]:
        rows = []
        for symbol, name, market, category in TARGET_INSTRUMENTS:
            if category == 'index' or str(symbol).startswith('^'):
                continue
            rows.append((symbol, name, market))
        return rows

    @classmethod
    def compute_symbol_snapshot(
        cls,
        symbol: str,
        market: str,
        profile: str = 'balanced',
        weights: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = FactorService.compute_symbol(symbol, market, profile, weights=weights)
        if not result.get('ok'):
            return {
                'ok': False,
                'symbol': symbol,
                'market': market,
                'reason': result.get('reason') or '计算失败',
            }
        score = result.get('score') or {}
        metrics = result.get('metrics') or {}
        alpha = metrics.get('alphaFactors') or {}
        return {
            'ok': True,
            'symbol': symbol,
            'market': market,
            'asOf': metrics.get('tradeDate'),
            'latestClose': metrics.get('latestClose'),
            'score': score,
            'alpha101Count': metrics.get('alpha101Count') or alpha.get('alpha101Count') or 0,
            'alpha158Count': metrics.get('alpha158Count') or alpha.get('alpha158Count') or 0,
            'alpha101': metrics.get('alpha101') or alpha.get('alpha101') or {},
            'alpha158Top': _top_alpha(metrics.get('alpha158') or alpha.get('alpha158') or {}),
            'return20': metrics.get('return20'),
            'rsi14': metrics.get('rsi14'),
            'volumeRatio20': metrics.get('volumeRatio20'),
            'distanceHigh20': metrics.get('distanceHigh20'),
            'alpha006': (metrics.get('alpha101') or alpha.get('alpha101') or {}).get('alpha006')
            or alpha.get('alpha006'),
        }

    @classmethod
    async def run_daily_factor_scan(
        cls, db: AsyncSession, profile: str = 'balanced'
    ) -> dict[str, Any]:
        from module_quant.service.quant_service import QuantService

        universe = cls._scan_universe()
        ok_items: list[dict[str, Any]] = []
        failed: list[dict[str, str]] = []
        snaps: list[dict[str, Any]] = []
        profile_cfg = await QuantService.load_profile_config(db, profile)
        for symbol, _name, market in universe:
            try:
                snap = await _to_thread(cls.compute_symbol_snapshot, symbol, market, profile, profile_cfg)
            except Exception as exc:
                failed.append({'symbol': symbol, 'reason': str(exc)})
                continue
            if not snap.get('ok'):
                failed.append({'symbol': symbol, 'reason': snap.get('reason') or '失败'})
                continue
            snap['name'] = _name
            snaps.append(snap)
        attach_cross_section_alphas(snaps)
        for snap in snaps:
            score = snap.get('score') or {}
            symbol = snap.get('symbol')
            market = snap.get('market')
            await QuantSnapshotDao.upsert_factor_snapshot(
                db,
                {
                    'symbol': symbol,
                    'market': market,
                    'as_of': str(snap.get('asOf') or '')[:16] or None,
                    'score_total': score.get('total'),
                    'risk_level': score.get('riskLevel'),
                    'trend_direction': score.get('trendDirection'),
                    'alpha101_count': int(snap.get('alpha101Count') or 0),
                    'alpha158_count': int(snap.get('alpha158Count') or 0),
                    'score_json': _json(score),
                    'alpha_json': _json(
                        {
                            'alpha101': snap.get('alpha101') or {},
                            'alpha158Top': snap.get('alpha158Top') or {},
                            'alphaCs': snap.get('alphaCs') or {},
                        }
                    ),
                },
            )
            ok_items.append(
                {
                    'symbol': symbol,
                    'market': market,
                    'name': snap.get('name'),
                    'total': score.get('total'),
                    'riskLevel': score.get('riskLevel'),
                    'trendDirection': score.get('trendDirection'),
                    'alpha101Count': snap.get('alpha101Count'),
                    'alpha158Count': snap.get('alpha158Count'),
                    'alphaCsCount': snap.get('alphaCsCount') or 0,
                }
            )
        ok_items.sort(key=lambda x: float(x.get('total') or 0), reverse=True)
        payload = {
            'asOf': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'profile': profile,
            'symbolCount': len(ok_items),
            'failedCount': len(failed),
            'top': ok_items[:12],
            'failed': failed[:20],
            'readModelVersion': 'v2.3',
        }
        await QuantSnapshotDao.add_readmodel_snapshot(db, 'factors', _json(payload))
        await db.commit()
        await ReadModelService.put_scheduled('factors', payload, FACTOR_TTL)
        overview = await cls.build_overview_payload(db)
        await QuantSnapshotDao.add_readmodel_snapshot(db, 'overview', _json(overview))
        await db.commit()
        await ReadModelService.put_scheduled('overview', overview, OVERVIEW_TTL)
        logger.info(f'[因子日扫] 成功 {len(ok_items)} / 失败 {len(failed)}')
        return payload

    @classmethod
    async def run_indicator_refresh(cls, db: AsyncSession) -> dict[str, Any]:
        board: list[dict[str, Any]] = []
        by_market: dict[str, list[str]] = {}
        names: dict[tuple[str, str], str] = {}
        for symbol, name, market, category in TARGET_INSTRUMENTS:
            by_market.setdefault(market, []).append(symbol)
            names[(symbol, market)] = name
        for market, symbols in by_market.items():
            grouped = await _to_thread(InfluxUtil.query_latest_klines, market, symbols, 2, '-90d')
            for symbol in symbols:
                bars = grouped.get(symbol) or []
                last = bars[-1] if bars else None
                prev = bars[-2] if len(bars) >= 2 else None
                last_close = _to_float(last.get('close') if last else None)
                prev_close = _to_float(prev.get('close') if prev else None)
                change = None
                change_rate = None
                if last_close is not None and prev_close:
                    change = round(last_close - prev_close, 4)
                    change_rate = round((last_close - prev_close) / prev_close * 100, 4)
                board.append(
                    {
                        'symbol': symbol,
                        'name': names.get((symbol, market), symbol),
                        'market': market,
                        'close': last_close,
                        'change': change,
                        'changeRate': change_rate,
                        'volume': _to_float(last.get('volume') if last else None),
                        'asOf': last.get('date') if last else None,
                    }
                )
        payload = {
            'asOf': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'count': len(board),
            'items': board,
            'readModelVersion': 'v2.3',
        }
        await QuantSnapshotDao.add_readmodel_snapshot(db, 'board', _json(payload))
        await db.commit()
        await ReadModelService.put_scheduled('board', payload, BOARD_TTL)
        try:
            from module_market.service.market_service import MarketService

            quotes = await MarketService.refresh_board_quotes_cache(db)
            payload['quotesCache'] = quotes
        except Exception as exc:
            logger.warning(f'[指标快照] 写入看板报价缓存失败: {exc}')
        return {'count': len(board), 'asOf': payload['asOf']}

    @classmethod
    async def run_position_monitor(cls, db: AsyncSession) -> dict[str, Any]:
        from module_quant.service.longbridge_service import LongbridgeService
        from module_trade.dao.trade_dao import TradeDao

        await LongbridgeService.ensure_credentials_from_db(db)
        pos_res = await LongbridgeService.get_positions_async()
        if not pos_res.get('configured'):
            payload = {
                'configured': False,
                'message': pos_res.get('message') or '长桥凭据未配置，跳过持仓监控',
                'alerts': [],
                'asOf': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            await ReadModelService.put_scheduled('positions', payload, BOARD_TTL)
            return payload

        positions = pos_res.get('positions') or []
        alerts: list[dict[str, Any]] = []
        for pos in positions:
            symbol = str(pos.get('symbol') or '').strip()
            if not symbol:
                continue
            qty = _to_float(pos.get('quantity')) or 0
            cost = _to_float(pos.get('costPrice'))
            last = _to_float(pos.get('lastPrice') or pos.get('price') or pos.get('currentPrice'))
            market = str(pos.get('market') or 'US').upper()
            if last is None:
                bars = await _to_thread(InfluxUtil.query_latest_klines, market, [symbol], 1, '-30d')
                last_bar = (bars.get(symbol) or [None])[-1]
                last = _to_float(last_bar.get('close') if last_bar else None)
            pnl_pct = None
            if cost and last:
                pnl_pct = round((last - cost) / cost * 100, 4)
            alert = None
            if pnl_pct is not None and pnl_pct <= STOP_LOSS_PCT:
                alert = {
                    'symbol': symbol,
                    'market': market,
                    'quantity': qty,
                    'costPrice': cost,
                    'lastPrice': last,
                    'pnlPct': pnl_pct,
                    'level': 'danger',
                    'title': f'持仓止损预警 · {symbol}',
                    'content': f'{symbol} 现价 {last} 相对成本 {cost} 浮亏 {pnl_pct}%，触发 {STOP_LOSS_PCT}% 止损线',
                }
            if alert:
                alerts.append(alert)
                recent = await TradeDao.list_risk_events(db, limit=80)
                duplicate = any(
                    (row.symbol or '') == symbol
                    and (row.title or '') == alert['title']
                    and str(getattr(row, 'review_status', '') or 'pending_review')
                    in {'pending_review', 'need_review', 'overdue'}
                    for row in recent
                )
                if not duplicate:
                    await TradeDao.add_risk_event(
                        db,
                        {
                            'rule_id': None,
                            'event_level': 'danger',
                            'title': alert['title'],
                            'content': alert['content'],
                            'symbol': symbol,
                            'review_status': 'pending_review',
                            'handled': '0',
                        },
                    )
        if alerts:
            await db.commit()
        payload = {
            'configured': True,
            'count': len(positions),
            'alertCount': len(alerts),
            'alerts': alerts,
            'positions': positions,
            'asOf': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        await QuantSnapshotDao.add_readmodel_snapshot(db, 'positions', _json(payload))
        await db.commit()
        await ReadModelService.put_scheduled('positions', payload, BOARD_TTL)
        return {'configured': True, 'count': len(positions), 'alertCount': len(alerts)}

    @classmethod
    async def build_overview_payload(cls, db: AsyncSession) -> dict[str, Any]:
        from module_quant.service.readmodel_service import ReadModelService as RMS

        asset = await RMS.get_account_asset_snapshot(use_scheduled=False)
        pos = await RMS.get_position_snapshot(use_scheduled=False)
        factors = await QuantSnapshotDao.get_latest_readmodel(db, 'factors')
        board = await QuantSnapshotDao.get_latest_readmodel(db, 'board')
        factor_payload = _loads(factors.payload_json) if factors else {}
        board_payload = _loads(board.payload_json) if board else {}
        return {
            'configured': bool(asset.get('configured')),
            'message': asset.get('message'),
            'asset': asset,
            'position': pos,
            'factorScan': factor_payload,
            'board': {'count': board_payload.get('count'), 'asOf': board_payload.get('asOf'), 'items': (board_payload.get('items') or [])[:16]},
            'refreshTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'readModelVersion': 'v2.3',
            'source': 'scheduled',
        }

    @classmethod
    async def list_factor_snapshots(cls, db: AsyncSession, limit: int = 80) -> list[dict[str, Any]]:
        rows = await QuantSnapshotDao.list_latest_factor_snapshots(db, limit=limit)
        items = []
        for r in rows:
            alpha = _loads(r.alpha_json) if getattr(r, 'alpha_json', None) else {}
            alpha_cs = (alpha or {}).get('alphaCs') or {}
            items.append(
                {
                    'symbol': r.symbol,
                    'market': r.market,
                    'asOf': r.as_of,
                    'total': r.score_total,
                    'riskLevel': r.risk_level,
                    'trendDirection': r.trend_direction,
                    'alpha101Count': r.alpha101_count,
                    'alpha158Count': r.alpha158_count,
                    'alphaCsCount': len(alpha_cs),
                    'alphaCs': alpha_cs,
                    'createTime': r.create_time.strftime('%Y-%m-%d %H:%M:%S') if r.create_time else None,
                }
            )
        return items

    @classmethod
    async def export_factor_snapshots_csv(cls, db: AsyncSession) -> tuple[str, bytes]:
        items = await cls.list_factor_snapshots(db, limit=200)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                'symbol',
                'market',
                'asOf',
                'total',
                'riskLevel',
                'trendDirection',
                'alpha101Count',
                'alpha158Count',
                'alphaCsCount',
                'createTime',
            ]
        )
        for it in items:
            writer.writerow(
                [
                    it.get('symbol'),
                    it.get('market'),
                    it.get('asOf'),
                    it.get('total'),
                    it.get('riskLevel'),
                    it.get('trendDirection'),
                    it.get('alpha101Count'),
                    it.get('alpha158Count'),
                    it.get('alphaCsCount'),
                    it.get('createTime'),
                ]
            )
        filename = f'factor_snapshots_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        return filename, ('\ufeff' + buf.getvalue()).encode('utf-8')


def _top_alpha(values: dict[str, Any], limit: int = 12) -> dict[str, float]:
    ranked = []
    for key, raw in (values or {}).items():
        val = _to_float(raw)
        if val is None:
            continue
        ranked.append((abs(val), key, val))
    ranked.sort(reverse=True)
    return {k: round(v, 6) for _abs, k, v in ranked[:limit]}


def _loads(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _to_float(value: Any) -> float | None:
    if value is None or value == '':
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in (float('inf'), float('-inf')):
        return None
    return result


async def _to_thread(func, *args):
    import asyncio

    return await asyncio.get_running_loop().run_in_executor(None, func, *args)
