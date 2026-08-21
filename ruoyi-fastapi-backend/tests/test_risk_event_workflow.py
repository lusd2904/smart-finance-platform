from datetime import datetime, timedelta

import pytest

from exceptions.exception import ServiceException
from module_trade.service.risk_event_workflow import (
    apply_status_change,
    can_transition,
    effective_status,
    handled_flag,
    normalize_status,
)


def test_normalize_and_handled_flag() -> None:
    assert normalize_status(None) == 'pending_review'
    assert normalize_status('', '1') == 'confirmed'
    assert normalize_status('need_review') == 'need_review'
    assert handled_flag('confirmed') == '1'
    assert handled_flag('pending_review') == '0'
    assert handled_flag('overdue') == '0'


def test_effective_status_marks_overdue() -> None:
    now = datetime(2026, 8, 20, 12, 0, 0)
    fresh = now - timedelta(hours=2)
    stale = now - timedelta(hours=25)
    assert effective_status('pending_review', fresh, now=now) == 'pending_review'
    assert effective_status('pending_review', stale, now=now) == 'overdue'
    assert effective_status('need_review', stale, now=now) == 'overdue'
    assert effective_status('confirmed', stale, now=now) == 'confirmed'


def test_allowed_transitions() -> None:
    assert can_transition('pending_review', 'confirmed')
    assert can_transition('pending_review', 'ignored')
    assert can_transition('overdue', 'need_review')
    assert can_transition('confirmed', 'need_review')
    assert can_transition('confirmed', 'ignored') is False
    assert can_transition('ignored', 'confirmed') is False


def test_apply_status_requires_remark_and_blocks_illegal() -> None:
    with pytest.raises(ServiceException):
        apply_status_change(current='pending_review', target='confirmed', remark='', operator='admin')
    with pytest.raises(ServiceException):
        apply_status_change(current='confirmed', target='ignored', remark='no', operator='admin')

    values = apply_status_change(
        current='pending_review',
        target='confirmed',
        remark='仓位已降到阈值内',
        operator='admin',
        now=datetime(2026, 8, 20, 12, 0, 0),
    )
    assert values['review_status'] == 'confirmed'
    assert values['handled'] == '1'
    assert values['handled_by'] == 'admin'
    assert values['handle_remark'] == '仓位已降到阈值内'

    reopen = apply_status_change(
        current='ignored',
        target='need_review',
        remark='行情再恶化，重新打开',
        operator='admin',
    )
    assert reopen['review_status'] == 'need_review'
    assert reopen['handled'] == '0'
