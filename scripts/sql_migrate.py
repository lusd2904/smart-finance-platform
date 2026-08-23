#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sql 增量迁移器：以 schema_version 表登记已执行的增量 SQL，统一两条执行路径。

背景：
  - docker-compose.sentiment.yml 在数据卷首次挂载时通过 /docker-entrypoint-initdb.d
    执行全量基线（BASELINE_FILES，编号 01-19，跳过废弃的 08）；
  - 此前 scripts/deploy_and_verify.sh 硬编码重放 8 个增量文件且 stderr 被 2>/dev/null 吞掉。
  本工具按文件名排序扫描 ruoyi-fastapi-backend/sql/*.sql，未登记的依序执行并登记，
  错误透传可见。

用法：
  python3 scripts/sql_migrate.py apply                 # 执行所有未登记增量
  python3 scripts/sql_migrate.py apply --keep-going    # 单个失败不中断，最后汇总
  python3 scripts/sql_migrate.py apply --dry-run       # 不连库，仅列出待执行计划
  python3 scripts/sql_migrate.py apply --file xxx.sql  # 单文件追加执行并登记
  python3 scripts/sql_migrate.py status                # 查看已登记 / 待执行清单

常用参数：
  --db sentiment-mysql     MySQL 容器名（默认 sentiment-mysql）
  --database sentiment-ai  目标库（默认 sentiment-ai）
  --password ...           root 密码；缺省时依次回退环境变量 MYSQL_ROOT_PASSWORD、
                           容器内 printenv MYSQL_ROOT_PASSWORD
  --host/--port/--user     提供 --host 时改用 pymysql 直连（不经 docker exec）

依赖：标准库；--host 直连模式额外使用 pymysql。

注意（事务语义）：MySQL 的 DDL 语句（CREATE/ALTER/DROP/TRUNCATE 等）会隐式提交当前
事务，因此单个迁移文件不是原子执行的——中途失败时前面的语句可能已经生效。本工具按
「文件」登记 schema_version，且仅在客户端返回码为 0 时登记；失败的文件不登记，修复后
重跑 apply 即可从该文件续传。这要求每个增量脚本自身尽量幂等。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SQL_DIR = REPO / "ruoyi-fastapi-backend" / "sql"

# PostgreSQL 版本基线，不适用于 MySQL，永不扫描
EXCLUDE_FILES = {"ruoyi-fastapi-pg.sql"}

# compose 首次挂载初始化执行的基线（对应 docker-entrypoint-initdb.d 编号 01-19，08 废弃跳过）。
# 首建 schema_version 时自动预登记，避免对老环境重复执行全量基线。
BASELINE_FILES = (
    "ruoyi-fastapi.sql",
    "sentiment-menu.sql",
    "market-menu.sql",
    "quant-menu.sql",
    "auto-trade.sql",
    "full-feature-menu.sql",
    "deep-feature-menu.sql",
    "risk-event-workflow.sql",
    "quant-phase2-snapshots.sql",
    "quant-factor-qc.sql",
    "market-watchlist.sql",
    "web-polish.sql",
    "analysis-scheduler.sql",
    "quant-longbridge-user.sql",
    "ai-requirement-board.sql",
    "ai-req-bots.sql",
    "quant-daily-list.sql",
    "plat-feishu-push.sql",
)

SCHEMA_VERSION_DDL = (
    "CREATE TABLE IF NOT EXISTS schema_version ("
    "name VARCHAR(255) PRIMARY KEY, applied_at DATETIME) "
    "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
)


class MigrationError(Exception):
    pass


def discover_files() -> list[str]:
    """按文件名排序扫描 sql 目录（排除 PG 基线）。"""
    return sorted(p.name for p in SQL_DIR.glob("*.sql") if p.name not in EXCLUDE_FILES)


def resolve_password(args: argparse.Namespace) -> str:
    """密码来源优先级：--password > 环境变量 MYSQL_ROOT_PASSWORD > 容器内 printenv。"""
    pw = args.password or os.environ.get("MYSQL_ROOT_PASSWORD") or ""
    if pw:
        return pw
    probe = subprocess.run(
        ["docker", "exec", args.db, "printenv", "MYSQL_ROOT_PASSWORD"],
        capture_output=True, text=True,
    )
    if probe.returncode == 0 and probe.stdout.strip():
        return probe.stdout.strip()
    raise MigrationError(
        "未找到 MYSQL_ROOT_PASSWORD：请用 --password、环境变量 MYSQL_ROOT_PASSWORD，"
        "或确保目标容器内存在该环境变量"
    )


class CliBackend:
    """默认后端：全部操作经 `docker exec` 内的 mysql 客户端（无需暴露端口）。"""

    def __init__(self, container: str, database: str, password: str):
        self.container = container
        self.database = database
        self.password = password

    def _base(self, stdin: bool) -> list[str]:
        cmd = ["docker", "exec"]
        if stdin:
            cmd.append("-i")
        return cmd + [
            self.container, "mysql", "-uroot", f"-p{self.password}", self.database,
        ]

    def query(self, sql: str) -> list[list[str]]:
        r = subprocess.run(
            self._base(stdin=False) + ["-N", "-B", "-e", sql],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            raise MigrationError(f"查询失败（退出码 {r.returncode}）：{sql[:120]}")
        return [line.split("\t") for line in r.stdout.splitlines()]

    def execute(self, sql: str) -> None:
        # stderr 透传打印（含 mysql 客户端警告），不再吞错
        r = subprocess.run(
            self._base(stdin=False) + ["-e", sql],
            stderr=None,
        )
        if r.returncode != 0:
            raise MigrationError(f"执行失败（退出码 {r.returncode}）")

    def run_script(self, content: bytes) -> None:
        # 走 mysql 客户端原生解析器，天然支持存储过程/DELIMITER 等完整语法
        r = subprocess.run(
            self._base(stdin=True),
            input=content,
            stderr=None,
        )
        if r.returncode != 0:
            raise MigrationError(f"脚本执行失败（退出码 {r.returncode}）")


class PymysqlBackend:
    """直连后端：提供 --host 时使用 pymysql（不经 docker）。"""

    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        import pymysql  # noqa: PLC0415 —— 仅直连模式需要

        self.conn = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=database, charset="utf8mb4", autocommit=True,
        )

    def query(self, sql: str) -> list[list[str]]:
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return [[str(c) for c in row] for row in cur.fetchall()]

    def execute(self, sql: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(sql)

    def run_script(self, content: bytes) -> None:
        statements = split_mysql_statements(content.decode("utf-8"))
        with self.conn.cursor() as cur:
            for idx, stmt in enumerate(statements, 1):
                head = " ".join(stmt.split())[:80]
                try:
                    cur.execute(stmt)
                except Exception as e:  # noqa: BLE001 —— 定位到具体语句再抛出
                    raise MigrationError(f"第 {idx} 条语句失败: {head}… ({e})") from e


def split_mysql_statements(text: str) -> list[str]:
    """按分隔符切分 SQL 语句；处理 DELIMITER 指令、引号与三种注释。跨行块注释有状态。"""
    stmts: list[str] = []
    buf: list[str] = []
    delim = ";"
    in_block_comment = False

    for raw_line in text.splitlines(keepends=True):
        stripped = raw_line.strip()
        low = stripped.lower()
        if not in_block_comment and (low.startswith("delimiter ") or low.startswith("delimiter\t")):
            parts = stripped.split()
            if len(parts) == 2:
                if "".join(buf).strip():
                    stmts.append("".join(buf))
                buf = []
                delim = parts[1]
                continue

        j, n = 0, len(raw_line)
        while j < n:
            if in_block_comment:
                end = raw_line.find("*/", j)
                if end == -1:
                    j = n
                else:
                    in_block_comment = False
                    j = end + 2
                continue
            c = raw_line[j]
            if c in ("'", '"', "`"):
                quote = c
                buf.append(c)
                j += 1
                while j < n:
                    buf.append(raw_line[j])
                    if quote != "`" and raw_line[j] == "\\" and j + 1 < n:
                        buf.append(raw_line[j + 1])
                        j += 2
                        continue
                    if raw_line[j] == quote:
                        j += 1
                        break
                    j += 1
                continue
            if c == "/" and raw_line[j:j + 2] == "/*":
                end = raw_line.find("*/", j + 2)
                if end == -1:
                    in_block_comment = True
                    j = n
                else:
                    j = end + 2
                continue
            if c == "-" and raw_line[j:j + 2] == "--":
                break  # 行注释
            if c == "#":
                break
            if raw_line.startswith(delim, j):
                stmt = "".join(buf)
                if stmt.strip():
                    stmts.append(stmt)
                buf = []
                j += len(delim)
                continue
            buf.append(c)
            j += 1

    tail = "".join(buf)
    if tail.strip():
        stmts.append(tail)
    return stmts


def make_backend(args: argparse.Namespace, password: str):
    if args.host:
        return PymysqlBackend(args.host, args.port, args.user, password, args.database)
    return CliBackend(args.db, args.database, password)


def registry_table_exists(backend) -> bool:
    rows = backend.query(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = 'schema_version'"
    )
    return rows and rows[0][0] not in ("0", "")


def ensure_registry(backend) -> None:
    """建表；若为本工具首次接管（表新建），预登记 compose 基线，防止重复执行全量初始化。"""
    fresh = not registry_table_exists(backend)
    backend.execute(SCHEMA_VERSION_DDL)
    if fresh:
        seeds = [name for name in BASELINE_FILES if (SQL_DIR / name).exists()]
        values = ", ".join(f"('{name}', NOW())" for name in seeds)
        if values:
            backend.execute(f"INSERT IGNORE INTO schema_version (name, applied_at) VALUES {values}")
        print(f"-- 首次初始化 schema_version：预登记 {len(seeds)} 个 compose 基线文件")


def applied_names(backend) -> set[str]:
    return {row[0] for row in backend.query("SELECT name FROM schema_version")}


def record_applied(backend, name: str) -> None:
    escaped = name.replace("\\", "\\\\").replace("'", "\\'")
    backend.execute(
        f"INSERT INTO schema_version (name, applied_at) VALUES ('{escaped}', NOW())"
    )


def print_plan(names: list[str], args: argparse.Namespace, single_file: bool) -> None:
    baseline_on_disk = [n for n in BASELINE_FILES if (SQL_DIR / n).exists()]
    if single_file:
        pending = names
        print("==> 迁移计划（--dry-run，未连接数据库，单文件追加模式）")
        print(f"目标文件: {names[0]}")
    else:
        pending = [n for n in names if n not in BASELINE_FILES]
        print("==> 迁移计划（--dry-run，未连接数据库）")
        print(f"容器/库: {args.db} / {args.database}")
        print(f"扫描 {SQL_DIR.relative_to(REPO)}/*.sql：共 {len(names)} 个"
              f"（排除 {', '.join(sorted(EXCLUDE_FILES))}）")
        print(f"compose 基线（首建 schema_version 时自动预登记，不重复执行）：{len(baseline_on_disk)} 个")
    print(f"待执行候选（按文件名序；实际执行时扣除已登记文件）：{len(pending)} 个")
    for i, name in enumerate(pending, 1):
        tag = " [基线]" if name in BASELINE_FILES else ""
        print(f"  {i:>2}. {name}{tag}")
    print("提示：去掉 --dry-run 运行 apply 可读取真实 schema_version 并逐个执行登记。")


def cmd_apply(args: argparse.Namespace) -> int:
    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.is_file():
            print(f"!! 文件不存在: {path}", file=sys.stderr)
            return 1
        names = [path.name]
    else:
        names = discover_files()

    if args.dry_run:
        print_plan(names, args, single_file=bool(args.file))
        return 0

    backend = make_backend(args, resolve_password(args))
    ensure_registry(backend)
    done = applied_names(backend)

    pending = [n for n in names if n not in done]
    if not pending:
        print("无待执行增量，schema 已是最新。")
        return 0
    print(f"待执行 {len(pending)} 个（已登记 {len(done & set(names)) if args.file else len(done)} 个跳过）")

    failed: list[str] = []
    for name in pending:
        print(f"--> 执行 {name}")
        try:
            backend.run_script((SQL_DIR / name).read_bytes())
            record_applied(backend, name)
            print(f"    OK 已登记 schema_version ← {name}（{datetime.now():%Y-%m-%d %H:%M:%S}）")
        except Exception as e:  # noqa: BLE001 —— 单文件失败不影响 --keep-going 续传
            print(f"    !! {name} 失败: {e}", file=sys.stderr)
            failed.append(name)
            if not args.keep_going:
                print("中止（未使用 --keep-going）。修复后重跑 apply 将从该文件续传。", file=sys.stderr)
                return 1

    if failed:
        print(f"!! 完成，但有 {len(failed)} 个失败（未登记，可修复后重跑）: {', '.join(failed)}",
              file=sys.stderr)
        return 1
    print(f"全部完成：本次应用 {len(pending)} 个增量并登记。")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    backend = make_backend(args, resolve_password(args))
    names = discover_files()
    if not registry_table_exists(backend):
        print("schema_version 表不存在（迁移器尚未接管）。首次 apply 时将建表并预登记 compose 基线。")
        print(f"当前磁盘上的增量文件共 {len(names)} 个。运行 `apply --dry-run` 查看计划。")
        return 0
    done = applied_names(backend)
    baseline = [n for n in BASELINE_FILES if (SQL_DIR / n).exists()]
    print(f"已登记 {len(done)} 个，其中 compose 基线 {len([n for n in baseline if n in done])}"
          f"/{len(baseline)} 个；磁盘扫描 {len(names)} 个。")
    pending = [n for n in names if n not in done]
    if pending:
        print(f"待执行 {len(pending)} 个:")
        for name in pending:
            print(f"  - {name}")
    else:
        print("无待执行增量，schema 已是最新。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="sql 增量迁移器（schema_version 登记制）")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", default="sentiment-mysql", help="MySQL 容器名")
    common.add_argument("--database", default="sentiment-ai", help="目标数据库名")
    common.add_argument("--password", help="root 密码；缺省回退 MYSQL_ROOT_PASSWORD/容器 printenv")
    common.add_argument("--host", help="提供则用 pymysql 直连（默认走 docker exec）")
    common.add_argument("--port", type=int, default=3306, help="直连端口")
    common.add_argument("--user", default="root", help="直连用户名")

    p_apply = sub.add_parser("apply", parents=[common], help="执行未登记增量并登记")
    p_apply.add_argument("--dry-run", action="store_true", help="不连库，仅列出待执行计划")
    p_apply.add_argument("--keep-going", action="store_true", help="单个失败不中断，最后汇总")
    p_apply.add_argument("--file", help="单文件追加执行并登记（供 DDL 迁出流程消费）")

    sub.add_parser("status", parents=[common], help="查看已登记/待执行清单（只读）")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return cmd_apply(args) if args.command == "apply" else cmd_status(args)
    except MigrationError as e:
        print(f"!! {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
