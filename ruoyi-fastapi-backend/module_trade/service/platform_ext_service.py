"""
平台能力加深：风控规则/事件、行情覆盖、策略配置、批量AI、通知落库。
全面使用 SQLAlchemy Declarative ORM 与 TradeDao，兼容 MySQL 和 PostgreSQL。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.exception import ServiceException
from module_market.constant.instruments import TARGET_INSTRUMENTS
from module_market.entity.vo.market_vo import MarketAiAnalyzeModel
from module_market.service.market_service import MarketService
from module_trade.dao.trade_dao import TradeDao
from module_trade.service.risk_event_workflow import (
    STATUS_LABELS,
    apply_status_change,
    effective_status,
    handled_flag,
    normalize_status,
)
from utils.influx_util import InfluxUtil
from utils.log_util import logger

_SEEDS_DONE = False

DEFAULT_STRATEGY_PROFILES = {
    'conservative': {
        'name': '保守',
        'buyThreshold': 65,
        'sellThreshold': 40,
        'weights': {'trend': 0.25, 'momentum': 0.15, 'volatility': 0.2, 'volume': 0.1, 'value': 0.15, 'quality': 0.15},
    },
    'balanced': {
        'name': '均衡',
        'buyThreshold': 58,
        'sellThreshold': 42,
        'weights': {'trend': 0.3, 'momentum': 0.2, 'volatility': 0.15, 'volume': 0.15, 'value': 0.1, 'quality': 0.1},
    },
    'aggressive': {
        'name': '进取',
        'buyThreshold': 52,
        'sellThreshold': 45,
        'weights': {'trend': 0.35, 'momentum': 0.3, 'volatility': 0.1, 'volume': 0.15, 'value': 0.05, 'quality': 0.05},
    },
}


class PlatformExtService:
    @classmethod
    async def ensure_seed_data(cls, db: AsyncSession) -> None:
        """初始化默认策略配置与风控规则（仅在表为空时填充种子）"""
        global _SEEDS_DONE
        if _SEEDS_DONE:
            return

        try:
            await TradeDao.ensure_risk_event_schema(db)
            # 策略配置种子
            profiles = await TradeDao.list_strategy_profiles(db)
            existing_codes = {p.profile_code for p in profiles}
            for code, cfg in DEFAULT_STRATEGY_PROFILES.items():
                if code not in existing_codes:
                    await TradeDao.upsert_strategy_profile(
                        db, code=code, name=cfg['name'], config_json=json.dumps(cfg, ensure_ascii=False)
                    )

            # 风控规则种子
            rules = await TradeDao.list_risk_rules(db)
            if not rules:
                seeds = [
                    ('单票仓位上限', 'position', None, 20.0, '单标的仓位不超过总资产20%'),
                    ('单日亏损熔断', 'loss', None, 5.0, '当日浮亏超过5%触发熔断提示'),
                    ('集中度限制', 'concentration', None, 40.0, '行业/主题集中度警戒线'),
                ]
                for name, typ, sym, thr, remark in seeds:
                    await TradeDao.add_risk_rule(
                        db,
                        {
                            'rule_name': name,
                            'rule_type': typ,
                            'symbol': sym,
                            'threshold': thr,
                            'enabled': '1',
                            'remark': remark,
                        },
                    )

            await db.commit()
            _SEEDS_DONE = True
        except Exception as e:
            logger.warning(f'[平台扩展] 种子数据初始化跳过: {e}')

    # ---------- 行情覆盖 ----------
    @classmethod
    async def history_coverage(cls, db: AsyncSession) -> dict[str, Any]:
        await cls.ensure_seed_data(db)
        items = []

        async def _check_item(symbol: str, name: str, market: str, category: str) -> dict[str, Any]:
            latest = await asyncio.to_thread(InfluxUtil.latest_date, market, symbol)
            return {
                'symbol': symbol,
                'name': name,
                'market': market,
                'category': category,
                'latestDate': latest,
                'covered': bool(latest),
                'status': 'ok' if latest else 'missing',
            }

        tasks = [_check_item(sym, n, m, cat) for sym, n, m, cat in TARGET_INSTRUMENTS]
        items = await asyncio.gather(*tasks)

        covered = sum(1 for i in items if i['covered'])
        return {
            'total': len(items),
            'covered': covered,
            'missing': len(items) - covered,
            'coveragePct': round(covered / len(items) * 100, 1) if items else 0,
            'items': items,
        }

    # ---------- 策略配置 ----------
    @classmethod
    async def list_strategy_profiles(cls, db: AsyncSession) -> list[dict[str, Any]]:
        await cls.ensure_seed_data(db)
        rows = await TradeDao.list_strategy_profiles(db)
        out = []
        for r in rows:
            cfg = {}
            try:
                cfg = json.loads(r.config_json or '{}')
            except Exception:
                cfg = {}
            out.append(
                {
                    'profileCode': r.profile_code,
                    'profileName': r.profile_name,
                    'config': cfg,
                    'updateTime': r.update_time.strftime('%Y-%m-%d %H:%M:%S') if r.update_time else None,
                }
            )
        return out

    @classmethod
    async def save_strategy_profile(cls, db: AsyncSession, code: str, name: str, config: dict) -> None:
        await cls.ensure_seed_data(db)
        await TradeDao.upsert_strategy_profile(
            db,
            code=code,
            name=name or code,
            config_json=json.dumps(config or {}, ensure_ascii=False),
        )
        await db.commit()

    # ---------- 风控 ----------
    @classmethod
    async def list_risk_rules(cls, db: AsyncSession) -> list[dict[str, Any]]:
        await cls.ensure_seed_data(db)
        rows = await TradeDao.list_risk_rules(db)
        return [
            {
                'ruleId': r.rule_id,
                'ruleName': r.rule_name,
                'ruleType': r.rule_type,
                'symbol': r.symbol,
                'threshold': r.threshold,
                'enabled': r.enabled,
                'remark': r.remark,
                'createTime': r.create_time.strftime('%Y-%m-%d %H:%M:%S') if r.create_time else None,
            }
            for r in rows
        ]

    @classmethod
    async def save_risk_rule(cls, db: AsyncSession, payload: dict[str, Any]) -> int:
        await cls.ensure_seed_data(db)
        rid = payload.get('ruleId')
        if rid:
            await TradeDao.update_risk_rule(
                db,
                rule_id=int(rid),
                item={
                    'rule_name': payload.get('ruleName') or '规则',
                    'rule_type': payload.get('ruleType') or 'position',
                    'symbol': payload.get('symbol'),
                    'threshold': payload.get('threshold'),
                    'enabled': payload.get('enabled') or '1',
                    'remark': payload.get('remark'),
                },
            )
            await db.commit()
            return int(rid)
        item = await TradeDao.add_risk_rule(
            db,
            {
                'rule_name': payload.get('ruleName') or '规则',
                'rule_type': payload.get('ruleType') or 'position',
                'symbol': payload.get('symbol'),
                'threshold': payload.get('threshold'),
                'enabled': payload.get('enabled') or '1',
                'remark': payload.get('remark'),
            },
        )
        await db.commit()
        return item.rule_id

    @classmethod
    async def delete_risk_rule(cls, db: AsyncSession, rule_id: int) -> None:
        await cls.ensure_seed_data(db)
        await TradeDao.delete_risk_rule(db, rule_id)
        await db.commit()

    @classmethod
    async def list_risk_events(
        cls, db: AsyncSession, limit: int = 50, status: str | None = None
    ) -> list[dict[str, Any]]:
        await cls.ensure_seed_data(db)
        expired = await TradeDao.expire_overdue_risk_events(db)
        if expired:
            await db.commit()
        rows = await TradeDao.list_risk_events(db, limit=limit, status=status)
        items = []
        for r in rows:
            stored = normalize_status(getattr(r, 'review_status', None), r.handled)
            status_code = effective_status(stored, r.create_time, r.handled)
            items.append(
                {
                    'eventId': r.event_id,
                    'ruleId': r.rule_id,
                    'eventLevel': r.event_level,
                    'title': r.title,
                    'content': r.content,
                    'symbol': r.symbol,
                    'handled': handled_flag(status_code),
                    'reviewStatus': status_code,
                    'reviewStatusLabel': STATUS_LABELS.get(status_code, status_code),
                    'handleRemark': getattr(r, 'handle_remark', None),
                    'handledBy': getattr(r, 'handled_by', None),
                    'handleTime': r.handle_time.strftime('%Y-%m-%d %H:%M:%S')
                    if getattr(r, 'handle_time', None)
                    else None,
                    'createTime': r.create_time.strftime('%Y-%m-%d %H:%M:%S') if r.create_time else None,
                }
            )
        return items

    @classmethod
    async def update_risk_event_review(
        cls,
        db: AsyncSession,
        event_id: int,
        payload: dict[str, Any],
        operator: str | None = None,
    ) -> dict[str, Any]:
        await cls.ensure_seed_data(db)
        event = await TradeDao.get_risk_event(db, event_id)
        if not event:
            raise ServiceException(message='风控事件不存在')
        await TradeDao.expire_overdue_risk_events(db)
        await db.refresh(event)
        current = effective_status(
            getattr(event, 'review_status', None), event.create_time, event.handled
        )
        target = payload.get('reviewStatus') or payload.get('status')
        if not target and str(payload.get('handled') or '') == '1':
            target = 'confirmed'
        if not target and str(payload.get('handled') or '') == '0':
            target = 'need_review'
        values = apply_status_change(
            current=current,
            target=str(target or ''),
            remark=payload.get('handleRemark') or payload.get('remark'),
            operator=operator,
        )
        ok = await TradeDao.update_risk_event_status(
            db,
            event_id,
            handled=values['handled'],
            review_status=values['review_status'],
            handle_remark=values['handle_remark'],
            handled_by=values['handled_by'],
            handle_time=values['handle_time'],
        )
        if not ok:
            raise ServiceException(message='更新风控状态失败')
        await db.commit()
        return {
            'eventId': event_id,
            'reviewStatus': values['review_status'],
            'reviewStatusLabel': STATUS_LABELS[values['review_status']],
            'handled': values['handled'],
            'handleRemark': values['handle_remark'],
            'handledBy': values['handled_by'],
        }

    @classmethod
    async def evaluate_risk(cls, db: AsyncSession) -> dict[str, Any]:
        """基于规则 + 最近策略信号生成风险事件。"""
        await cls.ensure_seed_data(db)
        from module_quant.entity.do.quant_do import QuantStrategySignal
        from sqlalchemy import desc, select

        rules = await cls.list_risk_rules(db)
        enabled = [r for r in rules if str(r.get('enabled')) == '1']
        sig_rows = (
            (
                await db.execute(
                    select(QuantStrategySignal).order_by(desc(QuantStrategySignal.create_time)).limit(30)
                )
            )
            .scalars()
            .all()
        )
        created = 0
        for sig in sig_rows[:20]:
            score = float(sig.score or 0)
            symbol = sig.symbol or ''
            for rule in enabled:
                thr = float(rule.get('threshold') or 0)
                if 0 < thr <= 100 and score and score < min(thr, 55):
                    await TradeDao.add_risk_event(
                        db,
                        {
                            'rule_id': rule['ruleId'],
                            'event_level': 'warn',
                            'title': f"{rule['ruleName']} · {symbol}",
                            'content': f'标的 {symbol} 综合分 {score} 触发规则阈值 {thr}（signal={sig.signal}）',
                            'symbol': symbol,
                            'review_status': 'pending_review',
                            'handled': '0',
                        },
                    )
                    created += 1
                    break
        await db.commit()
        if created:
            await cls.push_notice_db(db, f'风控扫描产生 {created} 条事件', '请查看风控事件列表', 'warning', 'risk')
        return {'created': created, 'rules': len(enabled), 'signalsChecked': len(sig_rows)}

    # ---------- 通知落库 ----------
    @classmethod
    async def push_notice_db(
        cls, db: AsyncSession, title: str, content: str, level: str = 'info', category: str = 'system'
    ) -> None:
        await cls.ensure_seed_data(db)
        await TradeDao.add_notification(
            db, {'title': title, 'content': content, 'level': level, 'category': category}
        )
        await db.commit()

    @classmethod
    async def list_notices_db(cls, db: AsyncSession, limit: int = 50) -> list[dict[str, Any]]:
        await cls.ensure_seed_data(db)
        rows = await TradeDao.list_notifications(db, limit=limit)
        return [
            {
                'id': r.notice_id,
                'title': r.title,
                'content': r.content,
                'level': r.level,
                'category': r.category,
                'read': str(r.is_read) == '1',
                'createTime': r.create_time.strftime('%Y-%m-%d %H:%M:%S') if r.create_time else None,
            }
            for r in rows
        ]

    @classmethod
    async def mark_notice_read_db(cls, db: AsyncSession, notice_id: int | None = None) -> int:
        await cls.ensure_seed_data(db)
        updated = await TradeDao.mark_notifications_read(db, notice_id=notice_id)
        await db.commit()
        return updated

    # ---------- 批量 AI ----------
    @classmethod
    async def run_ai_batch(
        cls, db: AsyncSession, symbols: list[str] | None = None, market: str = 'US', days: int = 90
    ) -> dict[str, Any]:
        await cls.ensure_seed_data(db)
        if not symbols:
            symbols = [s for s, _n, m, c in TARGET_INSTRUMENTS if m == market and not s.startswith('^')][:8]
        cycle = uuid.uuid4().hex[:16]

        batch_record = await TradeDao.add_ai_batch_run(
            db,
            {
                'cycle_id': cycle,
                'symbols_count': len(symbols),
                'success_count': 0,
                'status': '0',
                'summary': '任务执行中',
            },
        )
        await db.commit()
        batch_id = batch_record.batch_id

        success = 0
        items_to_add: list[dict[str, Any]] = []
        for sym in symbols:
            try:
                result = await MarketService.ai_analyze_services(
                    db, MarketAiAnalyzeModel(symbol=sym, market=market, days=days)
                )
                ok = bool(result.get('ok'))
                if ok:
                    success += 1
                items_to_add.append(
                    {
                        'batch_id': batch_id,
                        'symbol': sym,
                        'market': market,
                        'decision': result.get('finalDecision') or result.get('trend'),
                        'confidence': result.get('finalConfidence'),
                        'summary': (result.get('summary') or '')[:2000],
                        'status': '1' if ok else '2',
                    }
                )
            except Exception as e:
                logger.warning(f'[批量AI] {sym} 失败: {e}')
                items_to_add.append(
                    {
                        'batch_id': batch_id,
                        'symbol': sym,
                        'market': market,
                        'decision': None,
                        'confidence': None,
                        'summary': str(e)[:500],
                        'status': '2',
                    }
                )

        await TradeDao.add_ai_batch_items(db, items_to_add)

        # 更新批次状态
        batch_record.success_count = success
        batch_record.status = '1'
        batch_record.summary = f'完成 {success}/{len(symbols)}'
        await db.commit()

        await cls.push_notice_db(
            db, '批量AI研判完成', f'批次 {cycle} 成功 {success}/{len(symbols)}', 'success', 'ai'
        )
        return {'batchId': batch_id, 'cycleId': cycle, 'total': len(symbols), 'success': success}

    @classmethod
    async def list_ai_batches(cls, db: AsyncSession, limit: int = 20) -> list[dict[str, Any]]:
        await cls.ensure_seed_data(db)
        rows = await TradeDao.list_ai_batch_runs(db, limit=limit)
        return [
            {
                'batchId': r.batch_id,
                'cycleId': r.cycle_id,
                'symbolsCount': r.symbols_count,
                'successCount': r.success_count,
                'status': r.status,
                'summary': r.summary,
                'createTime': r.create_time.strftime('%Y-%m-%d %H:%M:%S') if r.create_time else None,
            }
            for r in rows
        ]

    @classmethod
    async def list_ai_batch_items(cls, db: AsyncSession, batch_id: int) -> list[dict[str, Any]]:
        await cls.ensure_seed_data(db)
        rows = await TradeDao.get_ai_batch_items(db, batch_id)
        return [
            {
                'itemId': r.item_id,
                'symbol': r.symbol,
                'market': r.market,
                'decision': r.decision,
                'confidence': r.confidence,
                'summary': r.summary,
                'status': r.status,
                'createTime': r.create_time.strftime('%Y-%m-%d %H:%M:%S') if r.create_time else None,
            }
            for r in rows
        ]
