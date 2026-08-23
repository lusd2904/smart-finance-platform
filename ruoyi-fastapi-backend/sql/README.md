# SQL 目录与迁移治理

本目录包含 MySQL 增量/基线脚本。`ruoyi-fastapi-pg.sql` 是 PostgreSQL 版基线，
**永不**在 MySQL 路径中执行，也不被迁移器扫描。

## 两条执行路径（已统一登记制）

| 路径 | 触发时机 | 覆盖范围 |
| --- | --- | --- |
| **compose 首次挂载初始化** | 数据卷 `sentiment-mysql-data` 为空、MySQL 容器首次启动时，自动执行 `/docker-entrypoint-initdb.d/` 下挂载的全量基线（编号 01–19，08 废弃跳过） | 全量基线：建库建表 + 截至当前的菜单/功能数据 |
| **`scripts/sql_migrate.py`** | 每次部署（`deploy_and_verify.sh` 第 [3/5] 段）或手动执行 | 全部增量：按文件名序扫描本目录 `*.sql`（排除 PG 版），以 `schema_version` 表登记，只执行未登记的 |

两条路径靠 `schema_version(name VARCHAR(255) PRIMARY KEY, applied_at DATETIME)`
衔接：

- 老环境（由 compose 初始化、没有该表）：迁移器**首次接管建表时，自动预登记
  compose 基线的 18 个文件**，避免把全量基线重放一遍。
- 新环境：compose 先跑全量基线 → 迁移器随后建表预登记同一批基线 → 只补真正的新增量。
- 此前 deploy 脚本硬编码重放的 8 个文件若已被手工执行过且不幂等，首次接入登记制时
  可能重复执行一次；各脚本设计为可重复执行，风险可控。

> 事务语义提醒：MySQL 的 DDL（CREATE/ALTER/DROP 等）会隐式提交，单个迁移文件不是
> 原子的。迁移器仅在 mysql 客户端退出码为 0 时登记该文件；失败的文件不登记，
> 修复后重跑即从失败处续传。

## 迁移器用法

```bash
python3 scripts/sql_migrate.py apply                # 执行未登记增量并登记
python3 scripts/sql_migrate.py apply --keep-going   # 单个失败不中断（deploy 脚本使用此模式）
python3 scripts/sql_migrate.py apply --dry-run      # 不连库，仅列出待执行计划
python3 scripts/sql_migrate.py apply --file xx.sql  # 单文件追加执行并登记
python3 scripts/sql_migrate.py status               # 只读查看已登记/待执行

# 常用参数（对 apply/status 均有效）
--db sentiment-mysql        # MySQL 容器名（默认）
--database sentiment-ai     # 目标库（默认）
--password '...'            # 缺省依次回退 $MYSQL_ROOT_PASSWORD、容器内 printenv
--host 127.0.0.1 --port 13306   # 可选：pymysql 直连模式（需容器暴露端口）
```

## 新环境首次部署流程

1. 在仓库根目录 `.env` 中设置 `MYSQL_ROOT_PASSWORD`；
2. `docker compose -f docker-compose.sentiment.yml up -d` —— MySQL 数据卷为空时
   自动执行全量基线；
3. 等待 `ruoyi-mysql` 健康（healthcheck 通过）；
4. `python3 scripts/sql_migrate.py apply --keep-going`
   —— 建表并预登记基线后，补齐基线之后的所有增量；
5. 之后每次部署只需 `bash scripts/deploy_and_verify.sh`（内部已调用迁移器）。

## 如何新增一个增量脚本

1. 在本目录新建 `<主题>.sql`，文件名用小写英文与连字符（如 `quant-phase3.sql`）。
   文件名决定执行顺序，请勿重命名历史文件；
2. 脚本要求：
   - 尽量幂等（`CREATE TABLE IF NOT EXISTS`、插入前先查或用唯一键 `INSERT IGNORE`），
     因为 DDL 隐式提交导致失败续传时前面的语句可能已生效；
   - 不使用 `DELIMITER` 存储过程（直连模式解析有限；docker exec 路径支持但不建议）；
3. 本地验证计划：`python3 scripts/sql_migrate.py apply --dry-run`；
4. 提交代码即可——下次部署时迁移器按文件名序自动发现、执行并登记，
   **无需**修改 compose 挂载清单或 deploy 脚本。

注意：不要修改既有 `.sql` 文件内容（历史环境可能已按原样执行）；需要变更就新增增量文件。
