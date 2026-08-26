"""Lazy-import boot paths: UserService/TradeService must not pull pandas/MarketService at import."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _toplevel_imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_user_service_does_not_import_pandas_at_module_level() -> None:
    names = _toplevel_imported_modules(BACKEND_ROOT / 'module_admin/service/user_service.py')
    assert 'pandas' not in names


def test_trade_service_does_not_import_market_service_at_module_level() -> None:
    names = _toplevel_imported_modules(BACKEND_ROOT / 'module_trade/service/trade_service.py')
    assert 'module_market.service.market_service' not in names


def test_importing_trade_service_does_not_load_market_service() -> None:
    env = os.environ.copy()
    env.setdefault('JWT_SECRET_KEY', 'a' * 64)
    env.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)
    pythonpath = env.get('PYTHONPATH', '')
    env['PYTHONPATH'] = str(BACKEND_ROOT) if not pythonpath else f'{BACKEND_ROOT}{os.pathsep}{pythonpath}'
    proc = subprocess.run(
        [
            sys.executable,
            '-c',
            (
                'import sys\n'
                'from module_trade.service.trade_service import TradeService\n'
                'assert TradeService.__name__ == "TradeService"\n'
                'assert "module_market.service.market_service" not in sys.modules\n'
            ),
        ],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
