# Python RuoYi-FastAPI 后端已从 main 删除

生产路径自 #96–#98 起即为 **Go-only**（`sfp-backend`、`sfp-intel`、`sentiment-trade-api`、`sentiment-data-api`、`sentiment-market-read`、workers、`sfp-scheduler`）。`main` 上不再保留 fat FastAPI 运行时或 Python compose 回退 overlay。

GitHub Linguist 按**字节**统计语言，不按运行时。旧树 `ruoyi-fastapi-backend`（约 550 个 `.py`）把仓库语言条显示成 Python ~50%。删除后 Python 只剩两个宿主运维脚本。

## 从 main 删除的内容

| 路径 | 说明 |
|------|------|
| `ruoyi-fastapi-backend/` | FastAPI 应用、测试、Dockerfile.sentiment / .my / .pg |
| `ruoyi-fastapi-test/` | 旧 RuoYi Playwright/页面测试 |
| `docker-compose.sentiment.*python*.yml` | intel / platform / quant / trade / scheduler Python fallback |
| `docker-compose.my.yml` / `docker-compose.pg.yml` | 原版 RuoYi Python 栈 |
| `ruoyi-fastapi-frontend/bin/nginx.dockersentiment.slim.python-intel.conf` | Python intel nginx |
| `scripts/backfill_heat_top50_last.py` | 依赖 `module_market`；改用 Go `workers/market-worker/cmd/heat-backfill-last` |
| `scripts/seed_real_klines.py` | 依赖已删后端 |
| `scripts/sync_klines_slow.py` | 依赖已删后端 |
| `scripts/sync_market_listings.py` | 依赖已删后端 |

**未删：** `ruoyi-fastapi-frontend/`（Vue）、`ruoyi-fastapi-app/`（uni-app H5）、`flutter_client/`、`services/`、`workers/`。

## 迁到仓库根、仍给 Go 用

| 新路径 | 用途 |
|--------|------|
| `sql/*.sql` | MySQL 基线 + 增量（compose initdb + `scripts/sql_migrate.py`） |
| `.env.dockersentiment.example` | Go 服务 `env_file` 模板 |

## 仍留在 main 的 Python（约 31 KiB）

- `scripts/sql_migrate.py` — 增量 SQL 登记器（标准库；`--host` 直连才需要 pymysql）
- `scripts/sync_from_prod.py` — 生产→本地同步（stdlib HTTP + 传输层信封）

这两份不导入已删的 `module_*`。不要再加 thin Python 代理或把 FastAPI 套回来。

## 回滚

不要在 `main` 上复活 fat Python。若必须对照旧代码：

```bash
# 本 PR 合并前的 main（含完整 ruoyi-fastapi-backend）
git log --oneline -- ruoyi-fastapi-backend | head
git checkout <pre-delete-sha> -- ruoyi-fastapi-backend
```

或从该 SHA 检出整个工作树。合并后 Linguist 会在下次统计刷新（通常数小时内）下降 Python 占比。
