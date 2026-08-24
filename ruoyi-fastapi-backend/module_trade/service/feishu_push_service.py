"""飞书策略摘要推送：固定卡片、双渠道、用户自设时间、交易日历静默。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import httpx

from exceptions.exception import ServiceException
from module_quant.dao.quant_dao import QuantDailyListDao
from module_quant.service.daily_list_service import serialize_list
from module_trade.dao.trade_dao import TradeDao
from utils.log_util import logger
from utils.trading_calendar import is_cn_trading_day, today_cn

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

DISCLAIMER = '本内容为量化策略摘要，不构成投资建议或荐股，过往表现不代表未来。交易有风险，决策请独立判断。'
CARD_HEADER = '次日策略摘要'
# 飞书自定义机器人对非法参数/被限流返回 HTTP >= 400 或业务码非 0
FEISHU_HTTP_FAIL_MIN = 400


def _flag(value: Any) -> str:
    # True == 1，集合内无需重复写两个
    return '1' if value in {True, '1', 'true'} else '0'


def serialize_sub(row: Any) -> dict[str, Any]:
    return {
        'subId': row.sub_id,
        'userId': row.user_id,
        'personalEnabled': row.personal_enabled == '1',
        'groupEnabled': row.group_enabled == '1',
        'personalWebhook': row.personal_webhook or '',
        'groupWebhook': row.group_webhook or '',
        'pushTime': row.push_time or '18:30',
        'timezone': row.timezone or 'Asia/Shanghai',
        'lastPersonalKey': row.last_personal_key,
        'lastGroupKey': row.last_group_key,
        'lastError': row.last_error,
    }


def build_card(list_data: dict[str, Any]) -> dict[str, Any]:
    items = list_data.get('items') or []
    lines = []
    for item in items[:12]:
        direction = item.get('signal') or 'BUY'
        score = item.get('score')
        reason = (item.get('reason') or '')[:40]
        lines.append(
            f"{item.get('symbol')} {item.get('market')}  {direction}  评分{score if score is not None else '--'}  {reason}"
        )
    body = '\n'.join(lines) or '当日无可交易标的'
    return {
        'msg_type': 'interactive',
        'card': {
            'header': {'title': {'tag': 'plain_text', 'content': CARD_HEADER}, 'template': 'blue'},
            'elements': [
                {
                    'tag': 'div',
                    'text': {
                        'tag': 'lark_md',
                        'content': f"**交易日** {list_data.get('tradeDate') or '--'}  ·  {list_data.get('itemCount') or 0} 只",
                    },
                },
                {'tag': 'div', 'text': {'tag': 'lark_md', 'content': body}},
                {'tag': 'hr'},
                {'tag': 'note', 'elements': [{'tag': 'plain_text', 'content': DISCLAIMER}]},
            ],
        },
    }


def due_now(push_time: str, timezone: str, now: datetime | None = None) -> bool:
    try:
        tz = ZoneInfo(timezone or 'Asia/Shanghai')
    except Exception:
        tz = ZoneInfo('Asia/Shanghai')
    stamp = now or datetime.now(tz)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=tz)
    local = stamp.astimezone(tz)
    try:
        hour, minute = [int(p) for p in str(push_time or '18:30').split(':')[:2]]
    except ValueError:
        hour, minute = 18, 30
    return local.hour == hour and local.minute >= minute and local.minute < minute + 5


class FeishuPushService:
    @classmethod
    async def get_config(cls, db: AsyncSession, user_id: int) -> dict[str, Any]:
        row = await TradeDao.get_feishu_sub(db, user_id)
        if not row:
            return {
                'personalEnabled': False,
                'groupEnabled': False,
                'personalWebhook': '',
                'groupWebhook': '',
                'pushTime': '18:30',
                'timezone': 'Asia/Shanghai',
            }
        return serialize_sub(row)

    @classmethod
    async def save_config(cls, db: AsyncSession, user_id: int, body: dict[str, Any]) -> dict[str, Any]:
        push_time = str(body.get('pushTime') or '18:30').strip()
        # 最短允许 'H:MM'（4 字符），必须含小时分钟分隔符
        if len(push_time) < len('H:MM') or ':' not in push_time:
            raise ServiceException(message='推送时间格式应为 HH:MM')
        row = await TradeDao.upsert_feishu_sub(
            db,
            user_id,
            {
                'personal_enabled': _flag(body.get('personalEnabled')),
                'group_enabled': _flag(body.get('groupEnabled')),
                'personal_webhook': str(body.get('personalWebhook') or '').strip()[:500] or None,
                'group_webhook': str(body.get('groupWebhook') or '').strip()[:500] or None,
                'push_time': push_time[:8],
                'timezone': str(body.get('timezone') or 'Asia/Shanghai')[:64],
            },
        )
        data = serialize_sub(row)
        await db.commit()
        return data

    @classmethod
    async def test_push(cls, db: AsyncSession, user_id: int, channel: str = 'personal') -> dict[str, Any]:
        row = await TradeDao.get_feishu_sub(db, user_id)
        if not row:
            raise ServiceException(message='请先保存订阅配置')
        webhook = row.personal_webhook if channel == 'personal' else row.group_webhook
        if not webhook:
            raise ServiceException(message='该渠道未配置 Webhook')
        payload = build_card(
            {
                'tradeDate': today_cn().isoformat(),
                'itemCount': 0,
                'items': [],
            }
        )
        payload['card']['elements'][1]['text']['content'] = '这是一条测试卡片，正式推送会带上当日策略标的。'
        ok, message = await cls._post(webhook, payload)
        if not ok:
            raise ServiceException(message=message)
        return {'ok': True, 'message': '测试卡片已发送'}

    @classmethod
    async def run_due(cls, db: AsyncSession) -> dict[str, Any]:
        if not is_cn_trading_day():
            return {'skipped': True, 'reason': 'non_trading_day'}
        subs = await TradeDao.list_feishu_subs(db)
        sent = 0
        silent = 0
        for sub in subs:
            if not due_now(sub.push_time, sub.timezone):
                continue
            latest = await QuantDailyListDao.latest_for_user(db, sub.user_id)
            if not latest or latest.status != 'open' or not latest.item_count:
                silent += 1
                continue
            items = await QuantDailyListDao.list_items(db, latest.list_id)
            card = build_card(serialize_list(latest, items))
            trade_key_day = latest.trade_date.isoformat() if latest.trade_date else today_cn().isoformat()
            error = None
            if sub.personal_enabled == '1' and sub.personal_webhook:
                key = f'{sub.user_id}:personal:{trade_key_day}'
                if sub.last_personal_key != key:
                    ok, message = await cls._post(sub.personal_webhook, card)
                    if ok:
                        sub.last_personal_key = key
                        sent += 1
                    else:
                        error = message
            if sub.group_enabled == '1' and sub.group_webhook:
                key = f'{sub.user_id}:group:{trade_key_day}'
                if sub.last_group_key != key:
                    ok, message = await cls._post(sub.group_webhook, card)
                    if ok:
                        sub.last_group_key = key
                        sent += 1
                    else:
                        error = message or error
            sub.last_error = error
            sub.update_time = datetime.now()
        await db.commit()
        return {'skipped': False, 'sent': sent, 'silent': silent}

    @classmethod
    async def _post(cls, webhook: str, payload: dict[str, Any]) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(webhook, json=payload)
                data = resp.json() if resp.content else {}
            if resp.status_code >= FEISHU_HTTP_FAIL_MIN or int(data.get('code') or 0) != 0:
                text = str(data.get('msg') or data.get('message') or resp.text)[:300]
                logger.warning(f'[飞书推送] 失败: {text}')
                return False, text or f'HTTP {resp.status_code}'
            return True, 'ok'
        except Exception as exc:
            logger.warning(f'[飞书推送] 异常: {exc}')
            return False, str(exc)[:300]
