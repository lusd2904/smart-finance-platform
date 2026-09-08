# sfp-scheduler（Go）与 Python sentiment-jobs

P4 把 slim/full 默认调度从 Python `sentiment-jobs`（`APP_JOB_GROUP=none`）换成 Go `sfp-scheduler`。队列消费仍是三个 Go worker。任务中心启停 / 立即执行 / 心跳契约不变。

## cursor-1 并排切换（Python 关、Go 开）

**不要** `compose down`，不要动 MySQL / Redis / Influx / grok2api。

```bash
cd /workspace/sfp-slim-64   # 或生产部署树
source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data

# 1. 拉代码后只滚调度 + 确认 compose
sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  config >/dev/null

sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --no-deps --build sfp-scheduler

# 2. 停 Python 调度（profile 已默认不启；若旧容器还在）
sudo docker rm -f sentiment-jobs

# 3. 健康
curl -sf http://127.0.0.1:19098/health && echo
# 期望: "engine":"sfp-scheduler","leader":true,"schedulerRunning":true

# 4. 任务中心心跳（Redis DB 2）
sudo docker exec sentiment-redis redis-cli -n 2 -a "$REDIS_PASSWORD" GET sfp:scheduler:heartbeat
```

锁键仍是 `app:scheduler:lock`。Go 与 Python **不能同时当 Leader**，否则会双入队。

### 回滚到 Python

```bash
sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  -f docker-compose.sentiment.scheduler-python.yml \
  --profile legacy-python \
  up -d --no-deps sentiment-jobs
sudo docker rm -f sfp-scheduler
curl -sf http://127.0.0.1:19098/health && echo
```

## 入队核对清单（sys_job → Redis）

在 `SCHEDULER_TZ` 下等下一拍，或任务中心点「立即执行」，然后：

```bash
sudo docker exec sentiment-redis redis-cli -n 2 -a "$REDIS_PASSWORD" LRANGE sfp:job:queue:market 0 20
sudo docker exec sentiment-redis redis-cli -n 2 -a "$REDIS_PASSWORD" LRANGE sfp:job:queue:quant 0 20
sudo docker exec sentiment-redis redis-cli -n 2 -a "$REDIS_PASSWORD" LRANGE sfp:job:queue:llm 0 20
```

| id | 核对 | type | queue | payload |
|---:|------|------|-------|---------|
| 101 | [ ] | `market_sync` | market | `{"years":10}` |
| 103 | [ ] | `finance_briefings` | market | `{}` |
| 104 | [ ] | `symbol_content` | market | `{}` |
| 107 | [ ] | `indicator_refresh` | quant | `{}` |
| 113 | [ ] | `market_heat_collect` | market | `{"market":"CN","tradeDate":null}` |
| 114 | [ ] | `market_heat_collect` | market | `{"market":"HK","tradeDate":null}` |
| 115 | [ ] | `market_heat_collect` | market | `{"market":"US","tradeDate":null}` |
| 117 | [ ] | `feishu_push` | llm | `{}` |
| 121 | [ ] | `eod_kline_sync` | market | `{"market":"CN"}` |
| 122 | [ ] | `eod_kline_sync` | market | `{"market":"HK"}` |
| 123 | [ ] | `eod_kline_sync` | market | `{"market":"US"}` |

JSON 还必须带 `jobId`（32 hex）、`queue`、`enqueuedAt`（`YYYY-MM-DD HH:MM:SS`）。

立即执行：平台 API 往 `sfp:scheduler:command` 发 `{action:run,jobId}`；Go 入队后写 `sys_job_log`。

## 时区

- 代码默认 `SCHEDULER_TZ=Asia/Shanghai`。
- **compose 钉 `SCHEDULER_TZ=UTC`**：与 Python Docker（未设 TZ → UTC）以及现网 `sys_job` 小时字段一致。例：`0 25 7 * * ?` 仍是北京 15:25，不是上海墙钟 07:25。
- 若要把 cron 改成北京墙钟，先改 `sys_job.cron_expression` 再设 `SCHEDULER_TZ=Asia/Shanghai`。

## Misfire

| policy | Python APScheduler | Go |
|--------|--------------------|----|
| `3`（库默认，注释写「放弃」） | `misfire_grace_time≈1e12`，迟到仍跑 | 进程内错过的一拍仍入队一次 |
| `2` | `coalesce=True` | 错过窗口 24h 内入队一次 |
| `1` / 其他 | grace `None`（约 1s） | 迟到 >1s 跳过 |

冷启动**不会**把过去 7 天的周期任务全部补入队（避免重启踩踏）。只对**本进程运行期间**错过的 `next` 做一次补发。

## 内存

`sfp-scheduler` slim `mem_limit` **64m**（full 128m），替代 Python scheduler ~384m。

## `sys_job.invoke_target`：Go key 为库内真源

`jobs.Resolve` 的规范输入是 Redis 作业类型（`finance_briefings`、`market_heat_collect` 等）。
Python `module_task.*` 仍解析一轮（#92 别名），方便混跑或回滚；**库内应以 Go key 为准**。

幂等迁移（可重复执行，不停机）：

```bash
# 部署后由 sql_migrate 自动跑，或手工：
mysql ... < scripts/migrate_sys_job_go_invoke_targets.sql
# 等价增量：ruoyi-fastapi-backend/sql/sys-job-go-invoke-targets.sql
```

热度 / 收盘 K 线等按市场拆行的任务，Go key 相同，市场写在 `job_kwargs`（例如 `{"market":"CN"}`）。
`module_task.scheduler_test.job`（若依演示行）不改。

别名可在确认 `python_analysis = 0` 且稳定一版后从 `resolveTarget` 删掉。

### 核对计数

```sql
-- BEFORE / AFTER 同一条：分析任务里还应剩几条 Python 路径
SELECT COUNT(*) AS python_analysis
FROM sys_job
WHERE invoke_target LIKE 'module_task%'
  AND invoke_target NOT LIKE 'module_task.scheduler_test%';

-- 启用中的任务应已是 Go key
SELECT job_id, job_name, invoke_target, job_kwargs, status
FROM sys_job
WHERE status = '0'
  AND invoke_target NOT LIKE 'module_task.scheduler_test%'
ORDER BY job_id;
```

应用后期望：`python_analysis = 0`；启用行的 `invoke_target` 都在 `jobs.jobGroups` 里。
