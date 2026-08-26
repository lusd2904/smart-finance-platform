"""common_util boot path: CamelCaseUtil must not pull pandas/openpyxl."""

import os
import subprocess
import sys


def test_importing_camel_case_util_does_not_import_pandas() -> None:
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env.setdefault('JWT_SECRET_KEY', 'a' * 64)
    env.setdefault('CREDENTIAL_ENCRYPTION_KEY', 'b' * 64)
    pythonpath = env.get('PYTHONPATH', '')
    env['PYTHONPATH'] = backend_root if not pythonpath else f'{backend_root}{os.pathsep}{pythonpath}'
    proc = subprocess.run(
        [
            sys.executable,
            '-c',
            (
                'import sys\n'
                'from utils.common_util import CamelCaseUtil\n'
                'assert CamelCaseUtil.snake_to_camel("user_name") == "userName"\n'
                'assert "pandas" not in sys.modules\n'
                'assert "openpyxl" not in sys.modules\n'
            ),
        ],
        cwd=backend_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
