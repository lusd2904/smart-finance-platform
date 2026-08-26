"""Unit tests for open-sync allowlist, JWT claims, and cursor paging."""

import asyncio
import os
import sys
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'a' * 64)
os.environ.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from exceptions.exception import AuthException, PermissionException, ServiceException
from module_admin.service.login_service import LoginService
from module_admin.service.open_sync_service import (
    FORBIDDEN_TABLES,
    INFLUX_DATASET,
    OpenSyncService,
    advance_influx_cursor,
    advance_mysql_cursor,
    assert_table_allowed,
    build_sync_token_claims,
    clamp_page_size,
    decode_sync_token,
    extract_bearer_token,
    initial_cursor,
    is_sync_admin_user,
    normalize_datasets,
    parse_cursor,
    resolve_sync_tables,
    sanitize_row,
    tables_for_dataset,
    validate_sync_token_payload,
)


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def test_allowlist_expands_aliases_and_excludes_forbidden_tables() -> None:
    specs = resolve_sync_tables(['market', 'quant', 'trade'])
    names = [spec.name for spec in specs]
    assert 'market_instrument' in names
    assert 'quant_daily_list' in names
    assert 'plat_auto_trade_decision' in names
    for forbidden in FORBIDDEN_TABLES:
        assert forbidden not in names


def test_forbidden_tables_rejected() -> None:
    import pytest

    for table in ('quant_longbridge_config', 'sys_user', 'ai_models', 'plat_feishu_subscription'):
        with pytest.raises(ServiceException) as exc_info:
            assert_table_allowed(table)
        assert '拒绝同步表' in exc_info.value.message


def test_unknown_dataset_rejected() -> None:
    try:
        normalize_datasets(['sys_user'])
    except ServiceException:
        pass
    else:
        raise AssertionError('未知数据集应被拒绝')


def test_dataset_cannot_include_password_tables() -> None:
    trade_names = [spec.name for spec in tables_for_dataset('mysql.trade')]
    assert 'sys_user' not in trade_names
    assert 'quant_longbridge_config' not in trade_names


def test_sync_admin_gate() -> None:
    assert is_sync_admin_user(SimpleNamespace(user_id=1, user_name='admin')) is True
    assert is_sync_admin_user(SimpleNamespace(user_id=2, admin=True)) is True
    assert is_sync_admin_user(SimpleNamespace(user_id=7), role_ids=[1]) is True
    assert is_sync_admin_user(SimpleNamespace(user_id=7), role_ids=[2]) is False


def test_token_claims_helper() -> None:
    claims = build_sync_token_claims(1, 'admin', 'sess-1')
    assert claims['scope'] == 'sync'
    assert claims['aud'] == 'open-sync'
    assert claims['user_id'] == '1'
    validate_sync_token_payload(claims)
    try:
        validate_sync_token_payload({**claims, 'scope': 'login'})
    except AuthException:
        pass
    else:
        raise AssertionError('非 sync scope 应失败')
    try:
        validate_sync_token_payload({**claims, 'aud': 'api'})
    except AuthException:
        pass
    else:
        raise AssertionError('错误 aud 应失败')


def test_token_encode_decode_roundtrip() -> None:
    claims = build_sync_token_claims(1, 'admin', 'sess-round')
    token = _run(LoginService.create_access_token(data=claims, expires_delta=timedelta(minutes=30)))
    payload = decode_sync_token(token)
    assert payload['scope'] == 'sync'
    assert payload['user_name'] == 'admin'
    payload_bearer = decode_sync_token(f'Bearer {token}')
    assert payload_bearer['session_id'] == 'sess-round'


def test_extract_bearer_token() -> None:
    assert extract_bearer_token('Bearer abc') == 'abc'
    try:
        extract_bearer_token('Bearer ')
    except AuthException:
        pass
    else:
        raise AssertionError('空 Bearer 应失败')


def test_cursor_paging_same_table() -> None:
    datasets = ['mysql.market']
    cursor = {'dataset': 'mysql.market', 'table': 'market_instrument', 'pk': 0}
    nxt = advance_mysql_cursor(datasets, cursor, last_pk=1500, row_count=1000, page_size=1000, markets=['US'])
    assert nxt == {'dataset': 'mysql.market', 'table': 'market_instrument', 'pk': 1500}


def test_cursor_paging_next_table() -> None:
    datasets = ['mysql.market']
    cursor = {'dataset': 'mysql.market', 'table': 'market_instrument', 'pk': 9}
    nxt = advance_mysql_cursor(datasets, cursor, last_pk=12, row_count=3, page_size=1000, markets=['US'])
    assert nxt['dataset'] == 'mysql.market'
    assert nxt['table'] == 'market_price_history_daily'
    assert nxt['pk'] == 0


def test_cursor_paging_next_dataset_and_done() -> None:
    datasets = ['mysql.trade', INFLUX_DATASET]
    last_trade = tables_for_dataset('mysql.trade')[-1].name
    cursor = {'dataset': 'mysql.trade', 'table': last_trade, 'pk': 8}
    nxt = advance_mysql_cursor(datasets, cursor, last_pk=8, row_count=2, page_size=1000, markets=['US', 'CN'])
    assert nxt == {'dataset': INFLUX_DATASET, 'market': 'US', 'offset': 0}
    influx_done = advance_influx_cursor(
        datasets,
        ['US', 'CN'],
        {'dataset': INFLUX_DATASET, 'market': 'CN', 'offset': 10},
        row_count=3,
        page_size=1000,
    )
    assert influx_done is None


def test_cursor_parse_and_initial() -> None:
    assert parse_cursor(None) is None
    parsed = parse_cursor('market_instrument:99')
    assert parsed['table'] == 'market_instrument'
    assert parsed['pk'] == '99'
    start = initial_cursor(['mysql.quant'], ['US'])
    assert start['table'] == 'quant_daily_list'
    assert start['pk'] == 0


def test_page_size_clamp() -> None:
    assert clamp_page_size(None) == 1000
    assert clamp_page_size(5000) == 2000
    try:
        clamp_page_size(0)
    except ServiceException:
        pass
    else:
        raise AssertionError('limit=0 应失败')


def test_sanitize_row_drops_secrets_and_trims() -> None:
    row = sanitize_row(
        {'id': 1, 'password': 'secret', 'api_key': 'sk', 'note': 'ok', 'blob': 'x' * 20000},
        trim_columns=('blob',),
    )
    assert 'password' not in row
    assert 'api_key' not in row
    assert row['note'] == 'ok'
    assert row['blob'].endswith('…')
    assert len(row['blob']) == 16384 + 1


def test_issue_token_rejects_non_admin() -> None:
    user = SimpleNamespace(user_id=2, user_name='bob', user_type='00', status='0')
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=None)))
    db = SimpleNamespace()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=list)))
    with patch.object(LoginService, 'authenticate_user', AsyncMock(return_value=(user, None))):
        try:
            _run(OpenSyncService.issue_token(request, db, 'bob', 'unused'))
        except PermissionException as exc:
            assert '管理员' in exc.message
        else:
            raise AssertionError('非管理员应被拒绝')


def test_issue_token_admin_mocked() -> None:
    user = SimpleNamespace(user_id=1, user_name='admin', user_type='00', status='0')
    stored: dict[str, str] = {}

    class _Redis:
        async def set(self, key, value, ex=None):
            stored[key] = value

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=_Redis())))
    db = SimpleNamespace()
    with (
        patch.object(LoginService, 'authenticate_user', AsyncMock(return_value=(user, None))),
        patch.object(LoginService, 'create_access_token', AsyncMock(return_value='sync-jwt')),
    ):
        result = _run(OpenSyncService.issue_token(request, db, 'admin', 'unused'))
    assert result['token'] == 'sync-jwt'
    assert result['expiresIn'] == 1800
    assert 'mysql.market' in result['datasets']
    assert any(key.startswith('sync_token:') for key in stored)
