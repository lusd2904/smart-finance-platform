from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from exceptions.exception import ServiceException

STATUS_LABELS = {
    'pending_review': '待复核',
    'confirmed': '已确认',
    'ignored': '已忽略',
    'need_review': '需复核',
    'overdue': '超期',
}

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    'pending_review': frozenset({'confirmed', 'ignored', 'need_review', 'overdue'}),
    'need_review': frozenset({'confirmed', 'ignored', 'overdue', 'pending_review'}),
    'overdue': frozenset({'confirmed', 'ignored', 'need_review'}),
    'confirmed': frozenset({'need_review'}),
    'ignored': frozenset({'need_review'}),
}

TERMINAL_STATUSES = frozenset({'confirmed', 'ignored'})
OPEN_STATUSES = frozenset({'pending_review', 'need_review'})
OVERDUE_HOURS = 24
REMARK_REQUIRED = frozenset({'confirmed', 'ignored', 'need_review'})


def normalize_status(raw: str | None, handled: str | None = None) -> str:
    value = str(raw or '').strip()
    if value in STATUS_LABELS:
        return value
    if str(handled or '') == '1':
        return 'confirmed'
    return 'pending_review'


def effective_status(
    stored: str | None,
    create_time: datetime | None,
    handled: str | None = None,
    now: datetime | None = None,
    overdue_hours: int = OVERDUE_HOURS,
) -> str:
    status = normalize_status(stored, handled)
    if status in TERMINAL_STATUSES or status == 'overdue':
        return status
    if status in OPEN_STATUSES and create_time:
        current = now or datetime.now()
        if current - create_time >= timedelta(hours=overdue_hours):
            return 'overdue'
    return status


def handled_flag(status: str) -> str:
    return '1' if normalize_status(status) in TERMINAL_STATUSES else '0'


def can_transition(source: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(source, frozenset())


def apply_status_change(
    *,
    current: str,
    target: str,
    remark: str | None,
    operator: str | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    source = normalize_status(current)
    dest = normalize_status(target)
    if dest not in STATUS_LABELS:
        raise ServiceException(message=f'不支持的风控状态: {target}')
    if source == dest:
        raise ServiceException(message='状态未变化')
    if not can_transition(source, dest):
        raise ServiceException(message=f'不允许从{STATUS_LABELS[source]}变更为{STATUS_LABELS[dest]}')
    note = str(remark or '').strip()
    if dest in REMARK_REQUIRED and not note:
        raise ServiceException(message='请填写处理备注')
    stamp = now or datetime.now()
    return {
        'review_status': dest,
        'handled': handled_flag(dest),
        'handle_remark': note or None,
        'handled_by': operator,
        'handle_time': stamp,
    }
