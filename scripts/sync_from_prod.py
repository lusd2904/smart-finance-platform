#!/usr/bin/env python3
"""Download allowlisted prod data into local MySQL (and optional Influx dump).

Flow: GET public-key → RSA-OAEP + AES-256-GCM login → JWT pull pages → upsert.

Example:
  python3 scripts/sync_from_prod.py \\
    --base-url https://sfp.luapi.top/prod-api \\
    --user USER --password PASS \\
    --datasets market,quant,trade \\
    --mysql-host 127.0.0.1 --mysql-port 13306
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DUMP_DIR = Path('/tmp/sfp-sync')

ALLOWED_TABLES = frozenset(
    {
        'market_instrument',
        'market_price_history_daily',
        'market_watchlist',
        'market_heat_daily',
        'market_top50_snapshot',
        'market_daily_review',
        'quant_daily_list',
        'quant_daily_list_item',
        'quant_factor_snapshot',
        'quant_readmodel_snapshot',
        'plat_auto_trade_decision',
        'plat_ai_trade_run_log',
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
DATASET_ALIASES = {
    'market': 'mysql.market',
    'mysql.market': 'mysql.market',
    'quant': 'mysql.quant',
    'mysql.quant': 'mysql.quant',
    'trade': 'mysql.trade',
    'mysql.trade': 'mysql.trade',
    'influx': 'influx.daily',
    'influx.daily': 'influx.daily',
}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _b64url_decode(text: str) -> bytes:
    padding = '=' * ((-len(text)) % 4)
    return base64.urlsafe_b64decode(f'{text}{padding}'.encode('ascii'))


def _aad_bytes(aad: dict[str, str]) -> bytes:
    return json.dumps(aad, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def encrypt_json_envelope(
    public_key_pem: str,
    kid: str,
    alg: str,
    method: str,
    path: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], bytes]:
    """RSA-OAEP-SHA256 wrap AES-256-GCM; AAD binds {method, path}."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aes_key = os.urandom(32)
    public_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))
    encrypted_key = public_key.encrypt(
        aes_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    aad = {'method': method.upper(), 'path': path}
    iv = os.urandom(12)
    plaintext = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    ciphertext = AESGCM(aes_key).encrypt(iv, plaintext, _aad_bytes(aad))
    envelope = {
        'v': '1',
        'kid': kid,
        'alg': alg,
        'ts': int(time.time()),
        'nonce': str(uuid.uuid4()),
        'ek': _b64url(encrypted_key),
        'iv': _b64url(iv),
        'ct': _b64url(ciphertext),
        'aad': aad,
    }
    return envelope, aes_key


def decrypt_response_envelope(aes_key: bytes, envelope: dict[str, Any], method: str, path: str) -> dict[str, Any]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aad = envelope.get('aad')
    if not isinstance(aad, dict):
        raise RuntimeError('响应信封缺少 aad')
    expected = {'method': method.upper(), 'path': path, 'direction': 'response'}
    if (
        str(aad.get('method', '')).upper() != expected['method']
        or str(aad.get('path', '')) != expected['path']
        or str(aad.get('direction', '')) != expected['direction']
    ):
        raise RuntimeError('响应信封 method/path 与当前请求不匹配')
    plaintext = AESGCM(aes_key).decrypt(
        _b64url_decode(str(envelope['iv'])),
        _b64url_decode(str(envelope['ct'])),
        _aad_bytes(
            {
                'method': str(aad.get('method', '')).upper(),
                'path': str(aad.get('path', '')),
                'direction': str(aad.get('direction', '')),
            }
        ),
    )
    return json.loads(plaintext.decode('utf-8'))


def http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    timeout: int = 120,
) -> tuple[int, dict[str, str], bytes]:
    raw_headers = {str(key): str(value) for key, value in (headers or {}).items()}
    data = None
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode('utf-8')
        raw_headers.setdefault('Content-Type', 'application/json')
    request = Request(url, data=data, headers=raw_headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            header_map = {k.lower(): v for k, v in response.headers.items()}
            return int(response.status), header_map, response.read()
    except HTTPError as exc:
        header_map = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
        return int(exc.code), header_map, exc.read()
    except URLError as exc:
        raise RuntimeError(f'请求失败 {url}: {exc}') from exc


def parse_datasets(raw: str) -> list[str]:
    datasets: list[str] = []
    seen: set[str] = set()
    for item in (raw or '').split(','):
        key = item.strip()
        if not key:
            continue
        dataset = DATASET_ALIASES.get(key) or DATASET_ALIASES.get(key.lower())
        if not dataset:
            raise SystemExit(f'不支持的数据集: {key}')
        if dataset not in seen:
            seen.add(dataset)
            datasets.append(dataset)
    if not datasets:
        raise SystemExit('datasets 不能为空')
    return datasets


def join_url(base_url: str, path: str) -> str:
    return f'{base_url.rstrip("/")}{path}'


def load_public_key(base_url: str) -> dict[str, str]:
    status, _headers, body = http_request('GET', join_url(base_url, '/transport/crypto/public-key'), timeout=30)
    payload = json.loads(body.decode('utf-8'))
    data = payload.get('data') if isinstance(payload, dict) else None
    if status != 200 or not isinstance(data, dict) or payload.get('code') not in (200, None):
        raise RuntimeError(payload.get('msg') if isinstance(payload, dict) else '获取传输层公钥失败')
    kid = str(data.get('kid') or '')
    pem = str(data.get('publicKey') or data.get('public_key') or '')
    alg = str(data.get('alg') or 'RSA_OAEP_AES_256_GCM')
    if not kid or not pem:
        raise RuntimeError('传输层公钥不完整')
    return {'kid': kid, 'publicKey': pem, 'alg': alg}


def encrypted_json(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    key_meta: dict[str, str],
    *,
    extra_headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    envelope, aes_key = encrypt_json_envelope(
        key_meta['publicKey'],
        key_meta['kid'],
        key_meta['alg'],
        'POST',
        path,
        payload,
    )
    headers = {
        'X-Transport-Encrypt': '1',
        'X-Key-Id': key_meta['kid'],
        'Accept': 'application/json',
    }
    if extra_headers:
        headers.update(extra_headers)
    status, resp_headers, body = http_request(
        'POST',
        join_url(base_url, path),
        headers=headers,
        json_body=envelope,
        timeout=timeout,
    )
    if not body:
        raise RuntimeError(f'{path} 空响应 HTTP {status}')
    try:
        parsed = json.loads(body.decode('utf-8'))
    except json.JSONDecodeError as exc:
        preview = body[:180].decode('utf-8', errors='replace')
        raise RuntimeError(f'{path} 非 JSON 响应 HTTP {status}: {preview}') from exc
    if str(resp_headers.get('x-body-encrypted') or '') == '1':
        parsed = decrypt_response_envelope(aes_key, parsed, 'POST', path)
    if not isinstance(parsed, dict):
        raise RuntimeError(f'{path} 响应不是 JSON 对象')
    if parsed.get('code') not in (200, None) or parsed.get('success') is False:
        raise RuntimeError(str(parsed.get('msg') or f'{path} 失败 HTTP {status}'))
    data = parsed.get('data')
    if not isinstance(data, dict):
        raise RuntimeError(f'{path} 缺少 data')
    return data


def assert_table_allowed(table: str) -> None:
    if table in FORBIDDEN_TABLES or table not in ALLOWED_TABLES:
        raise RuntimeError(f'拒绝写入表: {table}')


def mysql_connect(args: argparse.Namespace):
    import pymysql

    return pymysql.connect(
        host=args.mysql_host,
        port=args.mysql_port,
        user=args.mysql_user,
        password=args.mysql_password,
        database=args.mysql_database,
        charset='utf8mb4',
        autocommit=False,
    )


def table_columns(conn, table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            'SELECT COLUMN_NAME FROM information_schema.columns '
            'WHERE table_schema = DATABASE() AND table_name = %s ORDER BY ordinal_position',
            (table,),
        )
        return [str(row[0]) for row in cur.fetchall()]


def upsert_rows(conn, table: str, rows: list[dict[str, Any]]) -> int:
    assert_table_allowed(table)
    if not rows:
        return 0
    try:
        local_cols = set(table_columns(conn, table))
    except Exception as exc:
        print(f'  skip {table}: 本地表不可用 ({exc})', file=sys.stderr)
        conn.rollback()
        return 0
    cols = [key for key in rows[0].keys() if key in local_cols]
    if not cols:
        print(f'  skip {table}: 无交集列', file=sys.stderr)
        return 0
    col_sql = ','.join(f'`{name}`' for name in cols)
    placeholders = ','.join(['%s'] * len(cols))
    updates = ','.join(f'`{name}`=VALUES(`{name}`)' for name in cols)
    sql = f'INSERT INTO `{table}` ({col_sql}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {updates}'
    values = [[row.get(name) for name in cols] for row in rows]
    with conn.cursor() as cur:
        cur.executemany(sql, values)
    conn.commit()
    return len(rows)


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='从生产拉取白名单数据写入本地 MySQL')
    parser.add_argument('--base-url', default='https://sfp.luapi.top/prod-api')
    parser.add_argument('--user', required=True, help='生产管理员用户名')
    parser.add_argument('--password', default=os.environ.get('SFP_SYNC_PASSWORD') or '', help='生产密码；也可用环境变量 SFP_SYNC_PASSWORD')
    parser.add_argument('--datasets', default='market,quant,trade')
    parser.add_argument('--markets', default='US,CN,HK')
    parser.add_argument('--since', default='')
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--mysql-host', default='127.0.0.1')
    parser.add_argument('--mysql-port', type=int, default=13306)
    parser.add_argument('--mysql-user', default='root')
    parser.add_argument('--mysql-password', default=os.environ.get('MYSQL_ROOT_PASSWORD') or '')
    parser.add_argument('--mysql-database', default='sentiment-ai')
    parser.add_argument('--dump-dir', default=str(DEFAULT_DUMP_DIR))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.password:
        print('缺少密码：请传 --password 或设置 SFP_SYNC_PASSWORD', file=sys.stderr)
        return 2
    if not args.mysql_password:
        print('缺少本地 MySQL 密码：请传 --mysql-password 或设置 MYSQL_ROOT_PASSWORD', file=sys.stderr)
        return 2
    datasets = parse_datasets(args.datasets)
    markets = [item.strip().upper() for item in args.markets.split(',') if item.strip()]
    dump_dir = Path(args.dump_dir)
    print(f'==> public-key {args.base_url}')
    key_meta = load_public_key(args.base_url)
    print('==> encrypted login /open/sync/token')
    token_data = encrypted_json(
        args.base_url,
        '/open/sync/token',
        {'username': args.user, 'password': args.password},
        key_meta,
        timeout=30,
    )
    token = str(token_data.get('token') or '')
    if not token:
        print('登录成功但未返回 token', file=sys.stderr)
        return 1
    print(f'    token ttl={token_data.get("expiresIn")}s datasets={token_data.get("datasets")}')
    conn = mysql_connect(args)
    cursor = None
    pages = 0
    total_rows = 0
    auth_header = {'Authorization': f'Bearer {token}'}
    try:
        while True:
            page = encrypted_json(
                args.base_url,
                '/open/sync/pull',
                {
                    'datasets': datasets,
                    'markets': markets,
                    'since': args.since or None,
                    'cursor': cursor,
                    'limit': args.limit,
                },
                key_meta,
                extra_headers=auth_header,
            )
            pages += 1
            dataset = str(page.get('dataset') or '')
            if page.get('skipped'):
                print(f'    skip {dataset}: {page.get("reason")}')
            rows = page.get('rows') if isinstance(page.get('rows'), list) else []
            klines = page.get('klines') if isinstance(page.get('klines'), list) else []
            table = str(page.get('table') or '')
            if rows:
                if not table:
                    print('    pull 返回 rows 但缺少 table', file=sys.stderr)
                    return 1
                written = upsert_rows(conn, table, rows)
                total_rows += written
                print(f'    {dataset} {table} +{written} (page {pages})')
            if klines:
                append_jsonl(dump_dir / 'influx_daily.jsonl', klines)
                total_rows += len(klines)
                print(f'    {dataset} klines +{len(klines)} -> {dump_dir / "influx_daily.jsonl"}')
            cursor = page.get('nextCursor')
            if not cursor:
                break
    finally:
        conn.close()
    print(f'完成：{pages} 页，约 {total_rows} 行写入本地 {args.mysql_host}:{args.mysql_port}/{args.mysql_database}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
