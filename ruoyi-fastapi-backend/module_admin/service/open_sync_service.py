"""Production → local data sync: encrypted login token and allowlisted pull."""

import re
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import jwt
from fastapi import Request
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config.env import JwtConfig
from exceptions.exception import AuthException, PermissionException, ServiceException
from module_admin.entity.do.user_do import SysUserRole
from module_admin.entity.vo.login_vo import UserLogin
from module_admin.service.login_service import LoginService
from utils.log_util import logger

SYNC_TOKEN_AUD = 'open-sync'
SYNC_TOKEN_SCOPE = 'sync'
SYNC_TOKEN_TTL_MINUTES = 30
SYNC_PAGE_DEFAULT = 1000
SYNC_PAGE_MAX = 2000
SYNC_TEXT_TRIM = 16384
SYNC_REDIS_KEY_PREFIX = 'sync_token'
_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_ALLOWED_MARKETS = frozenset({'US', 'CN', 'HK'})
_CURSOR_PIPE_FIELDS = 3
_BEARER_TOKEN_PARTS = 2

SENSITIVE_COLUMN_NAMES = frozenset(
    {
        'password',
        'api_key',
        'apikey',
        'app_secret',
        'appsecret',
        'access_token',
        'accesstoken',
        'refresh_token',
        'private_key',
        'secret',
        'jwt',
        'feishu_token',
        'webhook',
        'webhook_url',
    }
)

FORBIDDEN_TABLES = frozenset(
    {
        'quant_longbridge_config',
        'sys_user',
        'sys_user_role',
        'sys_logininfor',
        'ai_models',
        'plat_feishu_subscription',
        'plat_feishu_push',
    }
)


class SyncTableSpec:
    """Allowlisted MySQL table metadata used by cursor paging."""

    __slots__ = ('date_column', 'market_column', 'name', 'pk', 'trim_columns')

    def __init__(
        self,
        name: str,
        pk: str,
        date_column: str | None = None,
        market_column: str | None = None,
        trim_columns: tuple[str, ...] = (),
    ) -> None:
        self.name = name
        self.pk = pk
        self.date_column = date_column
        self.market_column = market_column
        self.trim_columns = trim_columns


DATASET_TABLES: dict[str, tuple[SyncTableSpec, ...]] = {
    'mysql.market': (
        SyncTableSpec('market_instrument', 'instrument_id', date_column='create_time', market_column='market'),
        SyncTableSpec('market_price_history_daily', 'id', date_column='trade_date', market_column='market'),
        SyncTableSpec('market_watchlist', 'id', date_column='create_time', market_column='market'),
        SyncTableSpec('market_heat_daily', 'id', date_column='trade_date', market_column='market'),
        SyncTableSpec('market_top50_snapshot', 'id', date_column='trade_date', market_column='market'),
        SyncTableSpec('market_daily_review', 'review_id', date_column='trade_date', market_column='market'),
    ),
    'mysql.quant': (
        SyncTableSpec('quant_daily_list', 'list_id', date_column='scan_date'),
        SyncTableSpec('quant_daily_list_item', 'item_id', date_column='trade_date', market_column='market'),
        SyncTableSpec('quant_factor_snapshot', 'snapshot_id', date_column='create_time', market_column='market'),
        SyncTableSpec('quant_readmodel_snapshot', 'snapshot_id', date_column='create_time'),
        SyncTableSpec('quant_watchlist', 'id', date_column='create_time', market_column='market'),
    ),
    'mysql.trade': (
        SyncTableSpec(
            'plat_auto_trade_decision',
            'decision_id',
            date_column='create_time',
            market_column='market',
            trim_columns=('reason', 'error'),
        ),
        SyncTableSpec(
            'plat_ai_trade_run_log',
            'run_id',
            date_column='create_time',
            trim_columns=(
                'guardrail_snapshot',
                'candidates_snapshot',
                'opportunities_snapshot',
                'skipped_reasons',
                'message',
            ),
        ),
    ),
}

INFLUX_DATASET = 'influx.daily'
CANONICAL_DATASETS = (*DATASET_TABLES.keys(), INFLUX_DATASET)
DATASET_ALIASES = {
    'market': 'mysql.market',
    'mysql.market': 'mysql.market',
    'quant': 'mysql.quant',
    'mysql.quant': 'mysql.quant',
    'trade': 'mysql.trade',
    'mysql.trade': 'mysql.trade',
    'influx': INFLUX_DATASET,
    'influx.daily': INFLUX_DATASET,
    'daily': INFLUX_DATASET,
}
ALLOWED_TABLE_NAMES = frozenset(spec.name for tables in DATASET_TABLES.values() for spec in tables)
TABLE_BY_NAME = {spec.name: spec for tables in DATASET_TABLES.values() for spec in tables}


def normalize_dataset_name(raw: str) -> str:
    """Map a CLI/API dataset alias to a canonical dataset id."""
    key = str(raw or '').strip().lower()
    dataset = DATASET_ALIASES.get(key) or DATASET_ALIASES.get(str(raw or '').strip())
    if not dataset:
        raise ServiceException(message=f'不支持的数据集: {raw}')
    return dataset


def normalize_datasets(raw_datasets: list[str] | None) -> list[str]:
    """Deduplicate and canonicalize requested datasets, preserving order."""
    if not raw_datasets:
        raise ServiceException(message='datasets 不能为空')
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_datasets:
        dataset = normalize_dataset_name(item)
        if dataset in seen:
            continue
        seen.add(dataset)
        normalized.append(dataset)
    if not normalized:
        raise ServiceException(message='datasets 不能为空')
    return normalized


def available_datasets() -> list[str]:
    """Return the public dataset catalog advertised after login."""
    return list(CANONICAL_DATASETS)


def assert_table_allowed(table: str) -> None:
    """Reject forbidden or non-allowlisted tables."""
    name = str(table or '').strip()
    if not name or name in FORBIDDEN_TABLES or name not in ALLOWED_TABLE_NAMES:
        raise ServiceException(message=f'拒绝同步表: {table}')


def tables_for_dataset(dataset: str) -> tuple[SyncTableSpec, ...]:
    """Return allowlisted MySQL tables for a dataset."""
    if dataset == INFLUX_DATASET:
        return ()
    tables = DATASET_TABLES.get(dataset)
    if not tables:
        raise ServiceException(message=f'不支持的数据集: {dataset}')
    for spec in tables:
        if spec.name in FORBIDDEN_TABLES:
            raise ServiceException(message=f'拒绝同步表: {spec.name}')
        assert_table_allowed(spec.name)
    return tables


def resolve_sync_tables(raw_datasets: list[str] | None) -> list[SyncTableSpec]:
    """Expand datasets into allowlisted table specs; never includes forbidden tables."""
    specs: list[SyncTableSpec] = []
    for dataset in normalize_datasets(raw_datasets):
        specs.extend(tables_for_dataset(dataset))
    leaked = [spec.name for spec in specs if spec.name in FORBIDDEN_TABLES]
    if leaked:
        raise ServiceException(message=f'拒绝同步表: {",".join(leaked)}')
    return specs


def is_sync_admin_user(user: Any, role_ids: list[int] | None = None) -> bool:
    """Admin-only gate: user_id=1 (RuoYi admin) or superadmin role_id=1."""
    user_id = int(getattr(user, 'user_id', 0) or 0)
    if user_id == 1 or bool(getattr(user, 'admin', False)):
        return True
    return 1 in {int(role_id) for role_id in (role_ids or [])}


def build_sync_token_claims(user_id: int | str, user_name: str, session_id: str) -> dict[str, Any]:
    """Build JWT claims for an open-sync token (scope+aud isolate it from login tokens)."""
    return {
        'user_id': str(user_id),
        'user_name': user_name,
        'session_id': session_id,
        'scope': SYNC_TOKEN_SCOPE,
        'aud': SYNC_TOKEN_AUD,
    }


def validate_sync_token_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate decoded JWT claims for sync pull."""
    if not isinstance(payload, dict):
        raise AuthException(data='', message='同步令牌不合法')
    if payload.get('scope') != SYNC_TOKEN_SCOPE:
        raise AuthException(data='', message='同步令牌范围无效')
    audience = payload.get('aud')
    if audience not in (SYNC_TOKEN_AUD, [SYNC_TOKEN_AUD]):
        raise AuthException(data='', message='同步令牌受众无效')
    if not payload.get('user_id'):
        raise AuthException(data='', message='同步令牌不合法')
    return payload


def decode_sync_token(token: str) -> dict[str, Any]:
    """Verify JWT signature, expiry, audience and sync scope."""
    raw = extract_bearer_token(token)
    try:
        payload = jwt.decode(
            raw,
            JwtConfig.jwt_secret_key,
            algorithms=[JwtConfig.jwt_algorithm],
            audience=SYNC_TOKEN_AUD,
        )
    except InvalidTokenError as exc:
        logger.warning('同步令牌校验失败')
        raise AuthException(data='', message='同步令牌已失效，请重新登录') from exc
    return validate_sync_token_payload(payload)


def extract_bearer_token(authorization: str | None) -> str:
    """Parse Authorization: Bearer <jwt> (also accepts a bare JWT)."""
    raw = (authorization or '').strip()
    if raw.lower().startswith('bearer'):
        parts = raw.split(None, 1)
        if len(parts) != _BEARER_TOKEN_PARTS or parts[0].lower() != 'bearer' or not parts[1].strip():
            raise AuthException(data='', message='同步令牌不合法')
        return parts[1].strip()
    if not raw:
        raise AuthException(data='', message='同步令牌不合法')
    return raw


def clamp_page_size(limit: int | None) -> int:
    """Clamp a pull page size to (0, SYNC_PAGE_MAX]."""
    if limit is None:
        return SYNC_PAGE_DEFAULT
    try:
        value = int(limit)
    except (TypeError, ValueError) as exc:
        raise ServiceException(message='limit 非法') from exc
    if value < 1:
        raise ServiceException(message='limit 必须大于 0')
    return min(value, SYNC_PAGE_MAX)


def normalize_markets(markets: list[str] | None) -> list[str]:
    """Whitelist US/CN/HK; default to all three."""
    if not markets:
        return ['US', 'CN', 'HK']
    normalized: list[str] = []
    for item in markets:
        market = str(item or '').strip().upper()
        if market not in _ALLOWED_MARKETS:
            raise ServiceException(message=f'不支持的市场: {item}')
        if market not in normalized:
            normalized.append(market)
    return normalized or ['US', 'CN', 'HK']


def normalize_since(since: str | None) -> str | None:
    """Accept YYYY-MM-DD or empty."""
    text_value = str(since or '').strip()
    if not text_value:
        return None
    if not _DATE_RE.fullmatch(text_value):
        raise ServiceException(message='since 必须为 YYYY-MM-DD')
    return text_value


def parse_cursor(cursor: Any) -> dict[str, Any] | None:
    """Parse a pull cursor from dict or `table:pk` / `dataset|table|pk` string."""
    if cursor is None or cursor == '':
        return None
    if isinstance(cursor, dict):
        return dict(cursor)
    if isinstance(cursor, str):
        text_value = cursor.strip()
        if not text_value:
            return None
        if '|' in text_value:
            parts = text_value.split('|')
            if len(parts) >= _CURSOR_PIPE_FIELDS:
                return {'dataset': parts[0], 'table': parts[1], 'pk': parts[2]}
        if ':' in text_value:
            table, pk = text_value.split(':', 1)
            return {'table': table, 'pk': pk}
        raise ServiceException(message='cursor 格式不合法')
    raise ServiceException(message='cursor 格式不合法')


def initial_cursor(datasets: list[str], markets: list[str]) -> dict[str, Any]:
    """Cursor for the first page of the first requested dataset."""
    dataset = datasets[0]
    if dataset == INFLUX_DATASET:
        return {'dataset': dataset, 'market': markets[0], 'offset': 0}
    spec = tables_for_dataset(dataset)[0]
    return {'dataset': dataset, 'table': spec.name, 'pk': 0}


def _next_dataset(datasets: list[str], current: str) -> str | None:
    try:
        index = datasets.index(current)
    except ValueError:
        return None
    if index + 1 >= len(datasets):
        return None
    return datasets[index + 1]


def advance_mysql_cursor(
    datasets: list[str],
    cursor: dict[str, Any],
    *,
    last_pk: int,
    row_count: int,
    page_size: int,
    markets: list[str],
) -> dict[str, Any] | None:
    """Advance a MySQL table+pk cursor; move to next table/dataset when the page is short."""
    dataset = str(cursor.get('dataset') or '')
    table = str(cursor.get('table') or '')
    if row_count >= page_size:
        return {'dataset': dataset, 'table': table, 'pk': last_pk}
    specs = tables_for_dataset(dataset)
    names = [spec.name for spec in specs]
    try:
        index = names.index(table)
    except ValueError as exc:
        raise ServiceException(message=f'cursor 表不在允许列表: {table}') from exc
    if index + 1 < len(names):
        return {'dataset': dataset, 'table': names[index + 1], 'pk': 0}
    nxt = _next_dataset(datasets, dataset)
    if nxt is None:
        return None
    if nxt == INFLUX_DATASET:
        return {'dataset': nxt, 'market': markets[0], 'offset': 0}
    return {'dataset': nxt, 'table': tables_for_dataset(nxt)[0].name, 'pk': 0}


def advance_influx_cursor(
    datasets: list[str],
    markets: list[str],
    cursor: dict[str, Any],
    *,
    row_count: int,
    page_size: int,
) -> dict[str, Any] | None:
    """Advance influx market+offset cursor."""
    market = str(cursor.get('market') or markets[0]).upper()
    offset = int(cursor.get('offset') or 0) + row_count
    if row_count >= page_size:
        return {'dataset': INFLUX_DATASET, 'market': market, 'offset': offset}
    try:
        index = markets.index(market)
    except ValueError:
        index = 0
    if index + 1 < len(markets):
        return {'dataset': INFLUX_DATASET, 'market': markets[index + 1], 'offset': 0}
    nxt = _next_dataset(datasets, INFLUX_DATASET)
    if nxt is None:
        return None
    if nxt == INFLUX_DATASET:
        return None
    return {'dataset': nxt, 'table': tables_for_dataset(nxt)[0].name, 'pk': 0}


def _quote_ident(name: str) -> str:
    if not _IDENT_RE.fullmatch(name):
        raise ServiceException(message='非法数据表或字段名')
    return f'`{name}`'


def _trim_text(value: str) -> str:
    if len(value) <= SYNC_TEXT_TRIM:
        return value
    return value[:SYNC_TEXT_TRIM] + '…'


def sanitize_row(row: dict[str, Any], trim_columns: tuple[str, ...] = ()) -> dict[str, Any]:
    """Drop secrets, coerce JSON types, trim oversized TEXT."""
    cleaned: dict[str, Any] = {}
    trim_set = {item.lower() for item in trim_columns}
    for key, raw in row.items():
        column = str(key)
        lowered = column.lower()
        if lowered in SENSITIVE_COLUMN_NAMES:
            continue
        converted: Any = raw
        if isinstance(converted, datetime):
            converted = converted.isoformat(sep=' ', timespec='seconds')
        elif isinstance(converted, date):
            converted = converted.isoformat()
        elif isinstance(converted, Decimal):
            converted = float(converted)
        elif isinstance(converted, bytes):
            converted = converted.decode('utf-8', errors='replace')
        if isinstance(converted, str) and (lowered in trim_set or len(converted) > SYNC_TEXT_TRIM):
            converted = _trim_text(converted)
        cleaned[column] = converted
    return cleaned


class OpenSyncService:
    """Encrypted username/password sync token + allowlisted data pull."""

    @classmethod
    async def issue_token(
        cls,
        request: Request,
        query_db: AsyncSession,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        """Authenticate (no captcha), restrict to admin, issue a 30-minute sync JWT."""
        user_name = str(username or '').strip()
        if not user_name or not password:
            raise ServiceException(message='用户名或密码不能为空')
        login_user = UserLogin(user_name=user_name, password=password, captcha_enabled=False)
        result = await LoginService.authenticate_user(request, query_db, login_user)
        user = result[0]
        role_ids: list[int] = []
        user_id = int(user.user_id)
        if user_id != 1:
            role_rows = await query_db.execute(select(SysUserRole.role_id).where(SysUserRole.user_id == user_id))
            role_ids = [int(role_id) for role_id in role_rows.scalars().all()]
        if not is_sync_admin_user(user, role_ids):
            raise PermissionException(data='', message='仅管理员可同步数据')
        session_id = str(uuid.uuid4())
        claims = build_sync_token_claims(user_id, user.user_name, session_id)
        access_token = await LoginService.create_access_token(
            data=claims,
            expires_delta=timedelta(minutes=SYNC_TOKEN_TTL_MINUTES),
        )
        redis = getattr(getattr(request, 'app', None), 'state', None)
        redis_client = getattr(redis, 'redis', None) if redis is not None else None
        if redis_client is not None:
            await redis_client.set(
                f'{SYNC_REDIS_KEY_PREFIX}:{session_id}',
                access_token,
                ex=timedelta(minutes=SYNC_TOKEN_TTL_MINUTES),
            )
        logger.info(f'数据同步令牌已签发 user={user.user_name}')
        return {
            'token': access_token,
            'expiresIn': SYNC_TOKEN_TTL_MINUTES * 60,
            'datasets': available_datasets(),
        }

    @classmethod
    async def verify_pull_token(cls, request: Request, authorization: str | None) -> dict[str, Any]:
        """Verify Bearer JWT; Redis match is optional extra, JWT signature is authoritative."""
        token = extract_bearer_token(authorization)
        payload = decode_sync_token(token)
        session_id = str(payload.get('session_id') or '')
        redis_client = getattr(getattr(getattr(request, 'app', None), 'state', None), 'redis', None)
        if redis_client is not None and session_id:
            stored = await redis_client.get(f'{SYNC_REDIS_KEY_PREFIX}:{session_id}')
            if stored is not None:
                stored_text = stored.decode() if isinstance(stored, (bytes, bytearray)) else str(stored)
                if stored_text != token:
                    raise AuthException(data='', message='同步令牌已失效，请重新登录')
        return payload

    @classmethod
    async def pull(
        cls,
        query_db: AsyncSession,
        *,
        datasets: list[str] | None,
        markets: list[str] | None = None,
        since: str | None = None,
        cursor: Any = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return one page of allowlisted MySQL rows or Influx klines."""
        normalized_datasets = normalize_datasets(datasets)
        normalized_markets = normalize_markets(markets)
        since_date = normalize_since(since)
        page_size = clamp_page_size(limit)
        current = parse_cursor(cursor) or initial_cursor(normalized_datasets, normalized_markets)
        dataset = str(current.get('dataset') or '')
        if dataset not in normalized_datasets:
            raise ServiceException(message='cursor 与 datasets 不匹配')
        if dataset == INFLUX_DATASET:
            return await cls._pull_influx(
                datasets=normalized_datasets,
                markets=normalized_markets,
                since=since_date,
                cursor=current,
                page_size=page_size,
            )
        return await cls._pull_mysql(
            query_db,
            datasets=normalized_datasets,
            markets=normalized_markets,
            since=since_date,
            cursor=current,
            page_size=page_size,
        )

    @classmethod
    async def _pull_mysql(
        cls,
        query_db: AsyncSession,
        *,
        datasets: list[str],
        markets: list[str],
        since: str | None,
        cursor: dict[str, Any],
        page_size: int,
    ) -> dict[str, Any]:
        dataset = str(cursor.get('dataset') or '')
        table = str(cursor.get('table') or '')
        assert_table_allowed(table)
        spec = TABLE_BY_NAME.get(table)
        if spec is None or spec not in tables_for_dataset(dataset):
            raise ServiceException(message=f'表不在数据集 {dataset} 的允许列表: {table}')
        try:
            last_pk = int(cursor.get('pk') or 0)
        except (TypeError, ValueError) as exc:
            raise ServiceException(message='cursor.pk 非法') from exc
        try:
            rows = await cls._fetch_table_page(
                query_db, spec, last_pk=last_pk, page_size=page_size, markets=markets, since=since
            )
        except Exception as exc:
            logger.warning(f'数据同步跳过表 {table}: {exc}')
            nxt = advance_mysql_cursor(
                datasets,
                cursor,
                last_pk=last_pk,
                row_count=0,
                page_size=page_size,
                markets=markets,
            )
            return {
                'dataset': dataset,
                'table': table,
                'rows': [],
                'rowCount': 0,
                'nextCursor': nxt,
                'skipped': True,
                'reason': '表不存在或查询失败',
            }
        next_pk = last_pk
        if rows:
            next_pk = int(rows[-1].get(spec.pk) or last_pk)
        nxt = advance_mysql_cursor(
            datasets,
            cursor,
            last_pk=next_pk,
            row_count=len(rows),
            page_size=page_size,
            markets=markets,
        )
        logger.info(f'数据同步拉取 dataset={dataset} table={table} rows={len(rows)}')
        return {
            'dataset': dataset,
            'table': table,
            'rows': rows,
            'rowCount': len(rows),
            'nextCursor': nxt,
        }

    @classmethod
    async def _fetch_table_page(
        cls,
        query_db: AsyncSession,
        spec: SyncTableSpec,
        *,
        last_pk: int,
        page_size: int,
        markets: list[str],
        since: str | None,
    ) -> list[dict[str, Any]]:
        quoted_table = _quote_ident(spec.name)
        quoted_pk = _quote_ident(spec.pk)
        clauses = [f'{quoted_pk} > :pk']
        params: dict[str, Any] = {'pk': last_pk, 'limit': page_size}
        if spec.market_column and markets:
            quoted_market = _quote_ident(spec.market_column)
            placeholders = []
            for index, market in enumerate(markets):
                key = f'market_{index}'
                placeholders.append(f':{key}')
                params[key] = market
            clauses.append(f'{quoted_market} IN ({", ".join(placeholders)})')
        if spec.date_column and since:
            clauses.append(f'{_quote_ident(spec.date_column)} >= :since')
            params['since'] = since
        sql = text(f'SELECT * FROM {quoted_table} WHERE {" AND ".join(clauses)} ORDER BY {quoted_pk} ASC LIMIT :limit')
        result = await query_db.execute(sql, params)
        return [sanitize_row(dict(row), spec.trim_columns) for row in result.mappings().all()]

    @classmethod
    async def _pull_influx(
        cls,
        *,
        datasets: list[str],
        markets: list[str],
        since: str | None,
        cursor: dict[str, Any],
        page_size: int,
    ) -> dict[str, Any]:
        market = str(cursor.get('market') or markets[0]).upper()
        if market not in _ALLOWED_MARKETS:
            raise ServiceException(message=f'不支持的市场: {market}')
        offset = int(cursor.get('offset') or 0)
        klines, skipped_reason = cls._query_influx_daily(market, since, page_size, offset)
        if skipped_reason:
            nxt = advance_influx_cursor(
                datasets,
                markets,
                {'dataset': INFLUX_DATASET, 'market': market, 'offset': offset},
                row_count=0,
                page_size=page_size,
            )
            return {
                'dataset': INFLUX_DATASET,
                'klines': [],
                'rowCount': 0,
                'nextCursor': nxt,
                'skipped': True,
                'reason': skipped_reason,
            }
        nxt = advance_influx_cursor(
            datasets,
            markets,
            {'dataset': INFLUX_DATASET, 'market': market, 'offset': offset},
            row_count=len(klines),
            page_size=page_size,
        )
        logger.info(f'数据同步拉取 dataset={INFLUX_DATASET} market={market} rows={len(klines)}')
        return {
            'dataset': INFLUX_DATASET,
            'market': market,
            'klines': klines,
            'rowCount': len(klines),
            'nextCursor': nxt,
        }

    @classmethod
    def _query_influx_daily(
        cls,
        market: str,
        since: str | None,
        page_size: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], str | None]:
        try:
            from config.env import InfluxConfig
            from utils.influx_util import InfluxQueryError, InfluxUtil, bucket_for_market, get_client
        except Exception:
            return [], 'Influx 客户端不可用'
        if not str(getattr(InfluxConfig, 'influx_token', '') or '').strip():
            return [], 'Influx 未配置'
        start_clause = f'time(v: "{since}T00:00:00Z")' if since else '-2y'
        bucket = bucket_for_market(market)
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', bucket or ''):
            return [], 'Influx bucket 非法'
        flux = (
            f'from(bucket: "{bucket}")\n'
            f'  |> range(start: {start_clause})\n'
            f'  |> filter(fn: (r) => r._measurement == "{InfluxUtil.MEASUREMENT}")\n'
            f'  |> filter(fn: (r) => r.market == "{market}")\n'
            f'  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")\n'
            f'  |> sort(columns: ["_time", "symbol"])\n'
            f'  |> limit(n: {int(page_size)}, offset: {int(offset)})\n'
        )
        try:
            tables = get_client().query_api().query(flux)
        except InfluxQueryError as exc:
            logger.warning(f'数据同步 Influx 查询失败: {exc}')
            return [], 'Influx 查询失败'
        except Exception as exc:
            logger.warning(f'数据同步 Influx 查询失败: {exc}')
            return [], 'Influx 查询失败'
        rows: list[dict[str, Any]] = []
        for table in tables:
            for record in table.records:
                ts = record.get_time()
                rows.append(
                    {
                        'market': market,
                        'symbol': record.values.get('symbol'),
                        'date': ts.strftime('%Y-%m-%d') if ts else None,
                        'open': record.values.get('open'),
                        'high': record.values.get('high'),
                        'low': record.values.get('low'),
                        'close': record.values.get('close'),
                        'volume': record.values.get('volume'),
                    }
                )
        return rows, None
