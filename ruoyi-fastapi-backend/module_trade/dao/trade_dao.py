from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, desc, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from module_trade.entity.do.trade_do import (
    PlatAiBatchItem,
    PlatAiBatchRun,
    PlatAiTradeRunLog,
    PlatAutoTradeDecision,
    PlatBacktestRun,
    PlatFeishuSubscription,
    PlatNotification,
    PlatRiskEvent,
    PlatRiskRule,
    PlatStrategyProfile,
    PlatStrategyProfileUser,
    PlatUserStrategyBind,
)


class TradeDao:
    """
    交易、风控、通知与回测数据库操作层
    """

    # ---------------- 飞书订阅 ----------------
    @classmethod
    async def get_feishu_sub(cls, db: AsyncSession, user_id: int) -> PlatFeishuSubscription | None:
        return (
            (await db.execute(select(PlatFeishuSubscription).where(PlatFeishuSubscription.user_id == int(user_id))))
            .scalars()
            .first()
        )

    @classmethod
    async def list_feishu_subs(cls, db: AsyncSession) -> list[PlatFeishuSubscription]:
        return list((await db.execute(select(PlatFeishuSubscription))).scalars().all())

    @classmethod
    async def upsert_feishu_sub(cls, db: AsyncSession, user_id: int, values: dict[str, Any]) -> PlatFeishuSubscription:
        row = await cls.get_feishu_sub(db, user_id)
        now = datetime.now()
        if row:
            for key, value in values.items():
                setattr(row, key, value)
            row.update_time = now
            await db.flush()
            return row
        row = PlatFeishuSubscription(user_id=int(user_id), create_time=now, update_time=now, **values)
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    # ---------------- 通知 ----------------
    @classmethod
    async def add_notification(cls, db: AsyncSession, item: dict[str, Any]) -> PlatNotification:
        db_item = PlatNotification(
            user_id=int(item.get('user_id') or 1),
            title=item.get('title', ''),
            content=item.get('content', ''),
            level=item.get('level', 'info'),
            category=item.get('category', 'system'),
            is_read='0',
            create_time=datetime.now(),
        )
        db.add(db_item)
        await db.flush()
        return db_item

    @classmethod
    async def list_notifications(
        cls, db: AsyncSession, limit: int = 50, user_id: int | None = None
    ) -> list[PlatNotification]:
        if user_id is None:
            return []
        stmt = (
            select(PlatNotification)
            .where(PlatNotification.user_id == int(user_id))
            .order_by(desc(PlatNotification.create_time))
            .limit(limit)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def mark_notifications_read(
        cls, db: AsyncSession, notice_id: int | None = None, user_id: int | None = None
    ) -> int:
        if user_id is None:
            return 0
        if notice_id is not None:
            stmt = (
                update(PlatNotification)
                .where(
                    PlatNotification.notice_id == notice_id,
                    PlatNotification.user_id == int(user_id),
                )
                .values(is_read='1')
            )
        else:
            stmt = (
                update(PlatNotification)
                .where(
                    PlatNotification.is_read == '0',
                    PlatNotification.user_id == int(user_id),
                )
                .values(is_read='1')
            )
        res = await db.execute(stmt)
        return res.rowcount or 0

    # ---------------- 回测 ----------------
    @classmethod
    async def add_backtest_run(cls, db: AsyncSession, item: dict[str, Any]) -> PlatBacktestRun:
        db_item = PlatBacktestRun(
            user_id=int(item.get('user_id') or 1),
            symbol=item.get('symbol', ''),
            market=item.get('market', 'US'),
            days=int(item.get('days', 120)),
            strategy=item.get('strategy', 'factor-8family:balanced'),
            trades=int(item.get('trades', 0)),
            return_pct=float(item.get('return_pct', 0.0)),
            final_equity=float(item.get('final_equity', 0.0)),
            max_drawdown=float(item.get('max_drawdown', 0.0)),
            win_rate=float(item.get('win_rate', 0.0)),
            equity_curve_json=item.get('equity_curve_json', '[]'),
            message=item.get('message', ''),
            create_time=datetime.now(),
        )
        db.add(db_item)
        await db.flush()
        return db_item

    @classmethod
    async def list_backtest_runs(
        cls, db: AsyncSession, limit: int = 50, user_id: int | None = None
    ) -> list[PlatBacktestRun]:
        if user_id is None:
            return []
        stmt = (
            select(PlatBacktestRun)
            .where(PlatBacktestRun.user_id == int(user_id))
            .order_by(desc(PlatBacktestRun.create_time))
            .limit(limit)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_backtest_run_by_id(
        cls, db: AsyncSession, run_id: int, user_id: int | None = None
    ) -> PlatBacktestRun | None:
        if user_id is None:
            return None
        stmt = select(PlatBacktestRun).where(
            PlatBacktestRun.run_id == run_id,
            PlatBacktestRun.user_id == int(user_id),
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    # ---------------- 风控规则 ----------------
    @classmethod
    async def list_risk_rules(cls, db: AsyncSession) -> list[PlatRiskRule]:
        stmt = select(PlatRiskRule).order_by(desc(PlatRiskRule.rule_id))
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_risk_rule(cls, db: AsyncSession, rule_id: int) -> PlatRiskRule | None:
        stmt = select(PlatRiskRule).where(PlatRiskRule.rule_id == rule_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def add_risk_rule(cls, db: AsyncSession, item: dict[str, Any]) -> PlatRiskRule:
        now = datetime.now()
        db_item = PlatRiskRule(
            rule_name=item.get('rule_name', ''),
            rule_type=item.get('rule_type', 'position'),
            symbol=item.get('symbol'),
            threshold=item.get('threshold'),
            enabled=item.get('enabled', '1'),
            remark=item.get('remark'),
            create_time=now,
            update_time=now,
        )
        db.add(db_item)
        await db.flush()
        return db_item

    @classmethod
    async def update_risk_rule(cls, db: AsyncSession, rule_id: int, item: dict[str, Any]) -> bool:
        stmt = (
            update(PlatRiskRule)
            .where(PlatRiskRule.rule_id == rule_id)
            .values(
                rule_name=item.get('rule_name'),
                rule_type=item.get('rule_type'),
                symbol=item.get('symbol'),
                threshold=item.get('threshold'),
                enabled=item.get('enabled'),
                remark=item.get('remark'),
                update_time=datetime.now(),
            )
        )
        res = await db.execute(stmt)
        return (res.rowcount or 0) > 0

    @classmethod
    async def delete_risk_rule(cls, db: AsyncSession, rule_id: int) -> bool:
        stmt = delete(PlatRiskRule).where(PlatRiskRule.rule_id == rule_id)
        res = await db.execute(stmt)
        return (res.rowcount or 0) > 0

    # ---------------- 风控事件 ----------------
    @classmethod
    async def ensure_risk_event_table(cls, db: AsyncSession) -> None:
        """确保 plat_risk_event 表存在（重复执行安全）。"""
        await db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS plat_risk_event (
                  event_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '事件ID',
                  user_id BIGINT NOT NULL DEFAULT 1 COMMENT '用户ID',
                  rule_id BIGINT NULL COMMENT '关联规则ID',
                  event_level VARCHAR(16) NOT NULL DEFAULT 'warn' COMMENT '事件等级',
                  title VARCHAR(200) NOT NULL COMMENT '事件标题',
                  content VARCHAR(1000) NULL COMMENT '事件详情',
                  symbol VARCHAR(32) NULL COMMENT '标的代码',
                  handled CHAR(1) NOT NULL DEFAULT '0' COMMENT '是否已处理（0否 1是）',
                  review_status VARCHAR(32) NOT NULL DEFAULT 'pending_review' COMMENT '复核状态',
                  handle_remark VARCHAR(500) NULL COMMENT '处理备注',
                  handled_by VARCHAR(64) NULL COMMENT '处理人',
                  handle_time DATETIME NULL COMMENT '处理时间',
                  create_time DATETIME NULL COMMENT '触发时间',
                  PRIMARY KEY (event_id),
                  KEY ix_review_status (review_status),
                  KEY ix_create_time (create_time),
                  KEY ix_risk_event_user_time (user_id, create_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='风控触发事件表'
                """
            )
        )
        await db.commit()

    @classmethod
    async def ensure_risk_event_schema(cls, db: AsyncSession) -> None:
        """给已有 plat_risk_event 表补齐审批流字段，重复执行安全。"""
        await cls.ensure_risk_event_table(db)
        alters = [
            "ALTER TABLE plat_risk_event ADD COLUMN review_status VARCHAR(32) NOT NULL DEFAULT 'pending_review'",
            'ALTER TABLE plat_risk_event ADD COLUMN handle_remark VARCHAR(500) NULL',
            'ALTER TABLE plat_risk_event ADD COLUMN handled_by VARCHAR(64) NULL',
            'ALTER TABLE plat_risk_event ADD COLUMN handle_time DATETIME NULL',
            'ALTER TABLE plat_risk_event ADD COLUMN user_id BIGINT NOT NULL DEFAULT 1',
            'ALTER TABLE plat_risk_event ADD KEY ix_risk_event_user_time (user_id, create_time)',
        ]
        for sql in alters:
            try:
                await db.execute(text(sql))
                await db.commit()
            except Exception:  # noqa: PERF203 - 单条 DDL 失败不中断其余迁移
                await db.rollback()
        try:
            await db.execute(
                text(
                    "UPDATE plat_risk_event SET review_status = 'confirmed' "
                    "WHERE handled = '1' AND (review_status IS NULL OR review_status = '' "
                    "OR review_status = 'pending_review')"
                )
            )
            await db.commit()
        except Exception:
            await db.rollback()

    @classmethod
    async def expire_overdue_risk_events(
        cls, db: AsyncSession, hours: int = 24, user_id: int | None = None
    ) -> int:
        cutoff = datetime.now() - timedelta(hours=hours)
        cond = [
            PlatRiskEvent.review_status.in_(['pending_review', 'need_review']),
            PlatRiskEvent.create_time <= cutoff,
        ]
        if user_id is not None:
            cond.append(PlatRiskEvent.user_id == int(user_id))
        stmt = update(PlatRiskEvent).where(*cond).values(review_status='overdue')
        res = await db.execute(stmt)
        return res.rowcount or 0

    @classmethod
    async def list_risk_events(
        cls,
        db: AsyncSession,
        limit: int = 50,
        status: str | None = None,
        user_id: int | None = None,
    ) -> list[PlatRiskEvent]:
        if user_id is None:
            return []
        stmt = select(PlatRiskEvent).where(PlatRiskEvent.user_id == int(user_id))
        if status:
            stmt = stmt.where(PlatRiskEvent.review_status == status)
        stmt = stmt.order_by(desc(PlatRiskEvent.create_time)).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_risk_event(
        cls, db: AsyncSession, event_id: int, user_id: int | None = None
    ) -> PlatRiskEvent | None:
        if user_id is None:
            return None
        stmt = select(PlatRiskEvent).where(
            PlatRiskEvent.event_id == event_id,
            PlatRiskEvent.user_id == int(user_id),
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def add_risk_event(cls, db: AsyncSession, item: dict[str, Any]) -> PlatRiskEvent:
        db_item = PlatRiskEvent(
            user_id=int(item.get('user_id') or 1),
            rule_id=item.get('rule_id'),
            event_level=item.get('event_level', 'warn'),
            title=item.get('title', ''),
            content=item.get('content', ''),
            symbol=item.get('symbol'),
            handled=item.get('handled', '0'),
            review_status=item.get('review_status', 'pending_review'),
            handle_remark=item.get('handle_remark'),
            handled_by=item.get('handled_by'),
            handle_time=item.get('handle_time'),
            create_time=datetime.now(),
        )
        db.add(db_item)
        await db.flush()
        return db_item

    @classmethod
    async def mark_risk_event_handled(cls, db: AsyncSession, event_id: int) -> bool:
        return await cls.update_risk_event_status(db, event_id, handled='1')

    @classmethod
    async def update_risk_event_status(
        cls,
        db: AsyncSession,
        event_id: int,
        handled: str = '1',
        review_status: str | None = None,
        handle_remark: str | None = None,
        handled_by: str | None = None,
        handle_time: datetime | None = None,
        user_id: int | None = None,
    ) -> bool:
        values: dict[str, Any] = {'handled': handled}
        if review_status is not None:
            values['review_status'] = review_status
        if handle_remark is not None:
            values['handle_remark'] = handle_remark
        if handled_by is not None:
            values['handled_by'] = handled_by
        if handle_time is not None:
            values['handle_time'] = handle_time
        if user_id is None:
            return False
        cond = [
            PlatRiskEvent.event_id == event_id,
            PlatRiskEvent.user_id == int(user_id),
        ]
        stmt = update(PlatRiskEvent).where(*cond).values(**values)
        res = await db.execute(stmt)
        return (res.rowcount or 0) > 0

    # ---------------- 策略配置 ----------------
    @classmethod
    async def list_strategy_profiles(cls, db: AsyncSession) -> list[PlatStrategyProfile]:
        stmt = select(PlatStrategyProfile).order_by(PlatStrategyProfile.profile_code)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_strategy_profile(cls, db: AsyncSession, code: str) -> PlatStrategyProfile | None:
        stmt = select(PlatStrategyProfile).where(PlatStrategyProfile.profile_code == code)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def upsert_strategy_profile(cls, db: AsyncSession, code: str, name: str, config_json: str) -> PlatStrategyProfile:
        existing = await cls.get_strategy_profile(db, code)
        now = datetime.now()
        if existing:
            existing.profile_name = name
            existing.config_json = config_json
            existing.update_time = now
            await db.flush()
            return existing
        db_item = PlatStrategyProfile(
            profile_code=code,
            profile_name=name,
            config_json=config_json,
            update_time=now,
        )
        db.add(db_item)
        await db.flush()
        return db_item

    @classmethod
    async def list_user_strategy_profiles(cls, db: AsyncSession, user_id: int) -> list[PlatStrategyProfileUser]:
        stmt = (
            select(PlatStrategyProfileUser)
            .where(PlatStrategyProfileUser.user_id == int(user_id))
            .order_by(PlatStrategyProfileUser.profile_code)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_user_strategy_profile(
        cls, db: AsyncSession, user_id: int, code: str
    ) -> PlatStrategyProfileUser | None:
        stmt = select(PlatStrategyProfileUser).where(
            PlatStrategyProfileUser.user_id == int(user_id),
            PlatStrategyProfileUser.profile_code == code,
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def upsert_user_strategy_profile(
        cls, db: AsyncSession, user_id: int, code: str, name: str, config_json: str
    ) -> PlatStrategyProfileUser:
        existing = await cls.get_user_strategy_profile(db, user_id, code)
        now = datetime.now()
        if existing:
            existing.profile_name = name
            existing.config_json = config_json
            existing.update_time = now
            await db.flush()
            return existing
        db_item = PlatStrategyProfileUser(
            user_id=int(user_id),
            profile_code=code,
            profile_name=name,
            config_json=config_json,
            update_time=now,
        )
        db.add(db_item)
        await db.flush()
        return db_item

    @classmethod
    async def get_user_strategy_bind(cls, db: AsyncSession, user_id: int) -> PlatUserStrategyBind | None:
        stmt = select(PlatUserStrategyBind).where(PlatUserStrategyBind.user_id == int(user_id))
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def upsert_user_strategy_bind(
        cls, db: AsyncSession, user_id: int, profile_code: str
    ) -> PlatUserStrategyBind:
        existing = await cls.get_user_strategy_bind(db, user_id)
        now = datetime.now()
        if existing:
            existing.profile_code = profile_code
            existing.update_time = now
            await db.flush()
            return existing
        db_item = PlatUserStrategyBind(
            user_id=int(user_id),
            profile_code=profile_code,
            update_time=now,
        )
        db.add(db_item)
        await db.flush()
        return db_item

    # ---------------- 批量 AI ----------------
    @classmethod
    async def add_ai_batch_run(cls, db: AsyncSession, item: dict[str, Any]) -> PlatAiBatchRun:
        db_item = PlatAiBatchRun(
            cycle_id=item.get('cycle_id', ''),
            symbols_count=int(item.get('symbols_count', 0)),
            success_count=int(item.get('success_count', 0)),
            status=item.get('status', '0'),
            summary=item.get('summary', ''),
            create_time=datetime.now(),
        )
        db.add(db_item)
        await db.flush()
        return db_item

    @classmethod
    async def add_ai_batch_items(cls, db: AsyncSession, items: list[dict[str, Any]]) -> list[PlatAiBatchItem]:
        now = datetime.now()
        db_items = [
            PlatAiBatchItem(
                batch_id=int(i.get('batch_id', 0)),
                symbol=i.get('symbol', ''),
                market=i.get('market', 'US'),
                decision=i.get('decision'),
                confidence=i.get('confidence'),
                summary=i.get('summary'),
                status=i.get('status', '0'),
                create_time=now,
            )
            for i in items
        ]
        db.add_all(db_items)
        await db.flush()
        return db_items

    @classmethod
    async def list_ai_batch_runs(cls, db: AsyncSession, limit: int = 20) -> list[PlatAiBatchRun]:
        stmt = select(PlatAiBatchRun).order_by(desc(PlatAiBatchRun.create_time)).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_ai_batch_items(cls, db: AsyncSession, batch_id: int) -> list[PlatAiBatchItem]:
        stmt = (
            select(PlatAiBatchItem)
            .where(PlatAiBatchItem.batch_id == batch_id)
            .order_by(PlatAiBatchItem.item_id)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # ---------------- 自动交易决策与扫描台账 ----------------
    @classmethod
    async def add_auto_trade_decision(cls, db: AsyncSession, item: dict[str, Any]) -> PlatAutoTradeDecision:
        db_item = PlatAutoTradeDecision(
            cycle_id=item.get('cycle_id', ''),
            user_id=int(item.get('user_id') or 1),
            account_id=item.get('account_id'),
            symbol=item.get('symbol', ''),
            market=item.get('market', 'US'),
            side=item.get('side', 'BUY'),
            quantity=int(item.get('quantity', 0)),
            price=item.get('price'),
            confidence=item.get('confidence'),
            status=item.get('status', 'pending'),
            reason=item.get('reason'),
            source=item.get('source', 'auto'),
            order_id=item.get('order_id'),
            error=item.get('error'),
            create_time=datetime.now(),
        )
        db.add(db_item)
        await db.flush()
        return db_item

    @classmethod
    async def list_auto_trade_decisions(
        cls, db: AsyncSession, limit: int = 50, cycle_id: str | None = None
    ) -> list[PlatAutoTradeDecision]:
        stmt = select(PlatAutoTradeDecision)
        if cycle_id:
            stmt = stmt.where(PlatAutoTradeDecision.cycle_id == cycle_id)
        stmt = stmt.order_by(desc(PlatAutoTradeDecision.decision_id)).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def add_ai_trade_run_log(cls, db: AsyncSession, item: dict[str, Any]) -> PlatAiTradeRunLog:
        db_item = PlatAiTradeRunLog(
            cycle_id=item.get('cycle_id', ''),
            user_id=int(item.get('user_id') or 1),
            source=item.get('source', 'scheduler'),
            strategy_profile=item.get('strategy_profile', 'balanced'),
            target_count=int(item.get('target_count', 0)),
            evaluated_count=int(item.get('evaluated_count', 0)),
            opportunity_count=int(item.get('opportunity_count', 0)),
            submitted_orders_count=int(item.get('submitted_orders_count', 0)),
            status=item.get('status', 'completed'),
            guardrail_snapshot=item.get('guardrail_snapshot'),
            candidates_snapshot=item.get('candidates_snapshot'),
            opportunities_snapshot=item.get('opportunities_snapshot'),
            skipped_reasons=item.get('skipped_reasons'),
            message=item.get('message'),
            started_at=item.get('started_at') or datetime.now(),
            finished_at=item.get('finished_at') or datetime.now(),
            create_time=datetime.now(),
        )
        db.add(db_item)
        await db.flush()
        return db_item

    @classmethod
    async def list_ai_trade_run_logs(
        cls, db: AsyncSession, limit: int = 30, user_id: int | None = None
    ) -> list[PlatAiTradeRunLog]:
        stmt = select(PlatAiTradeRunLog)
        if user_id is not None:
            stmt = stmt.where(PlatAiTradeRunLog.user_id == int(user_id))
        stmt = stmt.order_by(desc(PlatAiTradeRunLog.run_id)).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_ai_trade_run_log_by_cycle(cls, db: AsyncSession, cycle_id: str) -> PlatAiTradeRunLog | None:
        stmt = select(PlatAiTradeRunLog).where(PlatAiTradeRunLog.cycle_id == cycle_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()
