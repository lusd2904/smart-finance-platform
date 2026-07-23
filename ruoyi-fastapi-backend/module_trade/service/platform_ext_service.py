"""
平台能力加深：风控规则/事件、行情覆盖、策略配置、批量AI、通知落库。
表不存在时自动建表（MySQL）。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from module_market.constant.instruments import TARGET_INSTRUMENTS
from module_market.service.market_service import MarketService
from module_market.entity.vo.market_vo import MarketAiAnalyzeModel
from utils.influx_util import InfluxUtil
from utils.log_util import logger

_DDL_DONE = False

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
    async def ensure_tables(cls, db: AsyncSession) -> None:
        global _DDL_DONE
        if _DDL_DONE:
            return
        ddls = [
            """
            CREATE TABLE IF NOT EXISTS plat_risk_rule (
              rule_id BIGINT PRIMARY KEY AUTO_INCREMENT,
              rule_name VARCHAR(100) NOT NULL,
              rule_type VARCHAR(32) NOT NULL DEFAULT 'position',
              symbol VARCHAR(32) NULL,
              threshold DOUBLE NULL,
              enabled CHAR(1) NOT NULL DEFAULT '1',
              remark VARCHAR(500) NULL,
              create_time DATETIME NULL,
              update_time DATETIME NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS plat_risk_event (
              event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
              rule_id BIGINT NULL,
              event_level VARCHAR(16) NOT NULL DEFAULT 'warn',
              title VARCHAR(200) NOT NULL,
              content VARCHAR(1000) NULL,
              symbol VARCHAR(32) NULL,
              handled CHAR(1) NOT NULL DEFAULT '0',
              create_time DATETIME NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS plat_strategy_profile (
              profile_code VARCHAR(32) PRIMARY KEY,
              profile_name VARCHAR(64) NOT NULL,
              config_json TEXT NOT NULL,
              update_time DATETIME NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS plat_notification (
              notice_id BIGINT PRIMARY KEY AUTO_INCREMENT,
              title VARCHAR(200) NOT NULL,
              content VARCHAR(2000) NULL,
              level VARCHAR(16) NOT NULL DEFAULT 'info',
              category VARCHAR(32) NOT NULL DEFAULT 'system',
              is_read CHAR(1) NOT NULL DEFAULT '0',
              create_time DATETIME NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS plat_ai_batch_run (
              batch_id BIGINT PRIMARY KEY AUTO_INCREMENT,
              cycle_id VARCHAR(64) NOT NULL,
              symbols_count INT NOT NULL DEFAULT 0,
              success_count INT NOT NULL DEFAULT 0,
              status CHAR(1) NOT NULL DEFAULT '0',
              summary TEXT NULL,
              create_time DATETIME NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS plat_ai_batch_item (
              item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
              batch_id BIGINT NOT NULL,
              symbol VARCHAR(32) NOT NULL,
              market VARCHAR(10) NOT NULL DEFAULT 'US',
              decision VARCHAR(32) NULL,
              confidence INT NULL,
              summary TEXT NULL,
              status CHAR(1) NOT NULL DEFAULT '0',
              create_time DATETIME NULL,
              KEY ix_batch (batch_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
        for sql in ddls:
            await db.execute(text(sql))
        # seed strategy profiles
        for code, cfg in DEFAULT_STRATEGY_PROFILES.items():
            exists = (
                await db.execute(
                    text('SELECT profile_code FROM plat_strategy_profile WHERE profile_code=:c'),
                    {'c': code},
                )
            ).first()
            if not exists:
                await db.execute(
                    text(
                        'INSERT INTO plat_strategy_profile(profile_code,profile_name,config_json,update_time) '
                        'VALUES(:c,:n,:j,:t)'
                    ),
                    {
                        'c': code,
                        'n': cfg['name'],
                        'j': json.dumps(cfg, ensure_ascii=False),
                        't': datetime.now(),
                    },
                )
        # seed default risk rules
        cnt = (await db.execute(text('SELECT COUNT(1) FROM plat_risk_rule'))).scalar() or 0
        if cnt == 0:
            now = datetime.now()
            seeds = [
                ('单票仓位上限', 'position', None, 20.0, '单标的仓位不超过总资产20%'),
                ('单日亏损熔断', 'loss', None, 5.0, '当日浮亏超过5%触发熔断提示'),
                ('集中度限制', 'concentration', None, 40.0, '行业/主题集中度警戒线'),
            ]
            for name, typ, sym, thr, remark in seeds:
                await db.execute(
                    text(
                        'INSERT INTO plat_risk_rule(rule_name,rule_type,symbol,threshold,enabled,remark,create_time,update_time) '
                        'VALUES(:n,:t,:s,:th,"1",:r,:c,:u)'
                    ),
                    {'n': name, 't': typ, 's': sym, 'th': thr, 'r': remark, 'c': now, 'u': now},
                )
        await db.commit()
        _DDL_DONE = True

    # ---------- 行情覆盖 ----------
    @classmethod
    async def history_coverage(cls, db: AsyncSession) -> dict[str, Any]:
        await cls.ensure_tables(db)
        items = []
        for symbol, name, market, category in TARGET_INSTRUMENTS:
            latest = await asyncio_latest(market, symbol)
            items.append(
                {
                    'symbol': symbol,
                    'name': name,
                    'market': market,
                    'category': category,
                    'latestDate': latest,
                    'covered': bool(latest),
                    'status': 'ok' if latest else 'missing',
                }
            )
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
        await cls.ensure_tables(db)
        rows = (await db.execute(text('SELECT profile_code, profile_name, config_json, update_time FROM plat_strategy_profile'))).all()
        out = []
        for r in rows:
            cfg = {}
            try:
                cfg = json.loads(r[2] or '{}')
            except Exception:
                cfg = {}
            out.append(
                {
                    'profileCode': r[0],
                    'profileName': r[1],
                    'config': cfg,
                    'updateTime': r[3].strftime('%Y-%m-%d %H:%M:%S') if r[3] else None,
                }
            )
        return out

    @classmethod
    async def save_strategy_profile(cls, db: AsyncSession, code: str, name: str, config: dict) -> None:
        await cls.ensure_tables(db)
        await db.execute(
            text(
                'INSERT INTO plat_strategy_profile(profile_code,profile_name,config_json,update_time) VALUES(:c,:n,:j,:t) '
                'ON DUPLICATE KEY UPDATE profile_name=VALUES(profile_name), config_json=VALUES(config_json), update_time=VALUES(update_time)'
            ),
            {'c': code, 'n': name or code, 'j': json.dumps(config or {}, ensure_ascii=False), 't': datetime.now()},
        )
        await db.commit()

    # ---------- 风控 ----------
    @classmethod
    async def list_risk_rules(cls, db: AsyncSession) -> list[dict[str, Any]]:
        await cls.ensure_tables(db)
        rows = (
            await db.execute(
                text(
                    'SELECT rule_id, rule_name, rule_type, symbol, threshold, enabled, remark, create_time '
                    'FROM plat_risk_rule ORDER BY rule_id'
                )
            )
        ).all()
        return [
            {
                'ruleId': r[0],
                'ruleName': r[1],
                'ruleType': r[2],
                'symbol': r[3],
                'threshold': r[4],
                'enabled': r[5],
                'remark': r[6],
                'createTime': r[7].strftime('%Y-%m-%d %H:%M:%S') if r[7] else None,
            }
            for r in rows
        ]

    @classmethod
    async def save_risk_rule(cls, db: AsyncSession, payload: dict[str, Any]) -> int:
        await cls.ensure_tables(db)
        rid = payload.get('ruleId')
        now = datetime.now()
        if rid:
            await db.execute(
                text(
                    'UPDATE plat_risk_rule SET rule_name=:n, rule_type=:t, symbol=:s, threshold=:th, enabled=:e, remark=:r, update_time=:u '
                    'WHERE rule_id=:id'
                ),
                {
                    'id': int(rid),
                    'n': payload.get('ruleName') or '规则',
                    't': payload.get('ruleType') or 'position',
                    's': payload.get('symbol'),
                    'th': payload.get('threshold'),
                    'e': payload.get('enabled') or '1',
                    'r': payload.get('remark'),
                    'u': now,
                },
            )
            await db.commit()
            return int(rid)
        await db.execute(
            text(
                'INSERT INTO plat_risk_rule(rule_name,rule_type,symbol,threshold,enabled,remark,create_time,update_time) '
                'VALUES(:n,:t,:s,:th,:e,:r,:c,:u)'
            ),
            {
                'n': payload.get('ruleName') or '规则',
                't': payload.get('ruleType') or 'position',
                's': payload.get('symbol'),
                'th': payload.get('threshold'),
                'e': payload.get('enabled') or '1',
                'r': payload.get('remark'),
                'c': now,
                'u': now,
            },
        )
        await db.commit()
        rid = (await db.execute(text('SELECT LAST_INSERT_ID()'))).scalar()
        return int(rid or 0)

    @classmethod
    async def delete_risk_rule(cls, db: AsyncSession, rule_id: int) -> None:
        await cls.ensure_tables(db)
        await db.execute(text('DELETE FROM plat_risk_rule WHERE rule_id=:id'), {'id': rule_id})
        await db.commit()

    @classmethod
    async def list_risk_events(cls, db: AsyncSession, limit: int = 50) -> list[dict[str, Any]]:
        await cls.ensure_tables(db)
        rows = (
            await db.execute(
                text(
                    'SELECT event_id, rule_id, event_level, title, content, symbol, handled, create_time '
                    'FROM plat_risk_event ORDER BY event_id DESC LIMIT :lim'
                ),
                {'lim': limit},
            )
        ).all()
        return [
            {
                'eventId': r[0],
                'ruleId': r[1],
                'eventLevel': r[2],
                'title': r[3],
                'content': r[4],
                'symbol': r[5],
                'handled': r[6],
                'createTime': r[7].strftime('%Y-%m-%d %H:%M:%S') if r[7] else None,
            }
            for r in rows
        ]

    @classmethod
    async def evaluate_risk(cls, db: AsyncSession) -> dict[str, Any]:
        """基于规则 + 最近策略信号生成风险事件。"""
        await cls.ensure_tables(db)
        from module_quant.entity.do.quant_do import QuantStrategySignal
        from sqlalchemy import select, desc

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
        now = datetime.now()
        for sig in sig_rows[:20]:
            score = float(sig.score or 0)
            symbol = sig.symbol or ''
            for rule in enabled:
                thr = float(rule.get('threshold') or 0)
                # 低分/高波动类规则：score 低于阈值时记事件
                if thr > 0 and thr <= 100 and score and score < min(thr, 55):
                    await db.execute(
                        text(
                            'INSERT INTO plat_risk_event(rule_id,event_level,title,content,symbol,handled,create_time) '
                            'VALUES(:rid,"warn",:title,:content,:sym,"0",:t)'
                        ),
                        {
                            'rid': rule['ruleId'],
                            'title': f"{rule['ruleName']} · {symbol}",
                            'content': f'标的 {symbol} 综合分 {score} 触发规则阈值 {thr}（signal={sig.signal}）',
                            'sym': symbol,
                            't': now,
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
        await cls.ensure_tables(db)
        await db.execute(
            text(
                'INSERT INTO plat_notification(title,content,level,category,is_read,create_time) '
                'VALUES(:t,:c,:l,:cat,"0",:tm)'
            ),
            {'t': title, 'c': content, 'l': level, 'cat': category, 'tm': datetime.now()},
        )
        await db.commit()

    @classmethod
    async def list_notices_db(cls, db: AsyncSession, limit: int = 50) -> list[dict[str, Any]]:
        await cls.ensure_tables(db)
        rows = (
            await db.execute(
                text(
                    'SELECT notice_id, title, content, level, category, is_read, create_time '
                    'FROM plat_notification ORDER BY notice_id DESC LIMIT :lim'
                ),
                {'lim': limit},
            )
        ).all()
        return [
            {
                'id': r[0],
                'title': r[1],
                'content': r[2],
                'level': r[3],
                'category': r[4],
                'read': str(r[5]) == '1',
                'createTime': r[6].strftime('%Y-%m-%d %H:%M:%S') if r[6] else None,
            }
            for r in rows
        ]

    @classmethod
    async def mark_notice_read_db(cls, db: AsyncSession, notice_id: int | None = None) -> int:
        await cls.ensure_tables(db)
        if notice_id:
            await db.execute(text('UPDATE plat_notification SET is_read="1" WHERE notice_id=:id'), {'id': notice_id})
        else:
            await db.execute(text('UPDATE plat_notification SET is_read="1"'))
        await db.commit()
        return 1

    # ---------- 批量 AI ----------
    @classmethod
    async def run_ai_batch(cls, db: AsyncSession, symbols: list[str] | None = None, market: str = 'US', days: int = 90) -> dict[str, Any]:
        await cls.ensure_tables(db)
        if not symbols:
            symbols = [s for s, _n, m, c in TARGET_INSTRUMENTS if m == market and not s.startswith('^')][:8]
        cycle = uuid.uuid4().hex[:16]
        now = datetime.now()
        await db.execute(
            text(
                'INSERT INTO plat_ai_batch_run(cycle_id,symbols_count,success_count,status,summary,create_time) '
                'VALUES(:c,:n,0,"1",NULL,:t)'
            ),
            {'c': cycle, 'n': len(symbols), 't': now},
        )
        await db.commit()
        batch_id = (await db.execute(text('SELECT LAST_INSERT_ID()'))).scalar()
        success = 0
        for sym in symbols:
            try:
                result = await MarketService.ai_analyze_services(
                    db, MarketAiAnalyzeModel(symbol=sym, market=market, days=days)
                )
                ok = bool(result.get('ok'))
                if ok:
                    success += 1
                await db.execute(
                    text(
                        'INSERT INTO plat_ai_batch_item(batch_id,symbol,market,decision,confidence,summary,status,create_time) '
                        'VALUES(:b,:s,:m,:d,:cf,:sm,:st,:t)'
                    ),
                    {
                        'b': batch_id,
                        's': sym,
                        'm': market,
                        'd': result.get('finalDecision') or result.get('trend'),
                        'cf': result.get('finalConfidence'),
                        'sm': (result.get('summary') or '')[:2000],
                        'st': '0' if ok else '1',
                        't': datetime.now(),
                    },
                )
            except Exception as e:
                logger.warning(f'[批量AI] {sym} 失败: {e}')
                await db.execute(
                    text(
                        'INSERT INTO plat_ai_batch_item(batch_id,symbol,market,decision,confidence,summary,status,create_time) '
                        'VALUES(:b,:s,:m,NULL,NULL,:sm,"1",:t)'
                    ),
                    {'b': batch_id, 's': sym, 'm': market, 'sm': str(e)[:500], 't': datetime.now()},
                )
        await db.execute(
            text('UPDATE plat_ai_batch_run SET success_count=:s, status="0", summary=:sm WHERE batch_id=:id'),
            {'s': success, 'sm': f'成功 {success}/{len(symbols)}', 'id': batch_id},
        )
        await db.commit()
        await cls.push_notice_db(db, '批量AI研判完成', f'批次 {cycle} 成功 {success}/{len(symbols)}', 'success', 'ai')
        return {'batchId': batch_id, 'cycleId': cycle, 'total': len(symbols), 'success': success}

    @classmethod
    async def list_ai_batches(cls, db: AsyncSession, limit: int = 20) -> list[dict[str, Any]]:
        await cls.ensure_tables(db)
        rows = (
            await db.execute(
                text(
                    'SELECT batch_id, cycle_id, symbols_count, success_count, status, summary, create_time '
                    'FROM plat_ai_batch_run ORDER BY batch_id DESC LIMIT :lim'
                ),
                {'lim': limit},
            )
        ).all()
        return [
            {
                'batchId': r[0],
                'cycleId': r[1],
                'symbolsCount': r[2],
                'successCount': r[3],
                'status': r[4],
                'summary': r[5],
                'createTime': r[6].strftime('%Y-%m-%d %H:%M:%S') if r[6] else None,
            }
            for r in rows
        ]

    @classmethod
    async def list_ai_batch_items(cls, db: AsyncSession, batch_id: int) -> list[dict[str, Any]]:
        await cls.ensure_tables(db)
        rows = (
            await db.execute(
                text(
                    'SELECT item_id, symbol, market, decision, confidence, summary, status, create_time '
                    'FROM plat_ai_batch_item WHERE batch_id=:b ORDER BY item_id'
                ),
                {'b': batch_id},
            )
        ).all()
        return [
            {
                'itemId': r[0],
                'symbol': r[1],
                'market': r[2],
                'decision': r[3],
                'confidence': r[4],
                'summary': r[5],
                'status': r[6],
                'createTime': r[7].strftime('%Y-%m-%d %H:%M:%S') if r[7] else None,
            }
            for r in rows
        ]


async def asyncio_latest(market: str, symbol: str) -> str | None:
    import asyncio

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, InfluxUtil.latest_date, market, symbol)
    except Exception:
        return None
