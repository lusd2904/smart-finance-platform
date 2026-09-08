# 内存预算、Slim 部署与后续迁移（运维速查）

本文是 **运维向** 的补充说明，与 [DEPLOY.md](./DEPLOY.md)、[SFP-TWO-HOST-DEPLOY.md](./SFP-TWO-HOST-DEPLOY.md) 配套。  
**Slim compose 叠加层**（`docker-compose.sentiment.slim.yml`、部署脚本等）由 **PR #64** 落地；合并后另见 [SLIM-POST-MERGE.md](./SLIM-POST-MERGE.md)。

---

## 优先级（生产 cursor-1）

| 主机 | RAM | 编排 | 说明 |
|------|-----|------|------|
| **cursor-1**（+ grok2api，无 swap） | 16 GiB | **Slim 双文件 compose** | **唯一推荐生产模式**；整栈峰值 RSS **< 5.5 GiB** |
| 大内存开发机 / 压测 | ≥ 32 GiB | Full split（`docker-compose.sentiment.yml`） | 6 API + 1 scheduler + 3 workers；**禁止在 cursor-1 上用于生产** |

**cursor-1 上 full-split 已弃用**：不要再起 `sentiment-market` / `sentiment-quant` / `sentiment-ai` / `sentiment-news` / `jobs-market` / `jobs-quant` / `jobs-llm` 等拆分容器（10+ Python 进程易 OOM）。需要隔离 profiling 时用大内存机 + `--profile full-split`（PR #64 合并后）。

---

## Slim 栈做什么（对用户透明）

对外 **HTTP 路径、WebSocket、任务 ticket、菜单与功能说明不变**。仅容器拓扑与内存上限不同：

| Slim 容器 | 合并内容 | 对外路径（不变） |
|-----------|----------|------------------|
| `sentiment-data` | market + quant API | `/market/`、`/quant/`、`/ws/` |
| `sentiment-intel` | sentiment + ai（含采集） | `/sentiment/`、`/ai/`、`/open/`（除 `/open/sync/`） |
| `sentiment-trade` | **仍独立** | `/trade/` |
| `sentiment-jobs` | `APP_JOB_GROUP=all`：APScheduler + market/quant/llm 三队列 | 任务中心「jobs 在线」 |
| `sentiment-backend` | 登录 / 系统 / dashboard | `/prod-api/` 等 |

稳态 RSS 目标 **4–5 GiB**；`mem_limit` 合计约 **5.0–5.4 GiB**（见 PR #64 预算表）。`sfp-backup` 在 slim 默认关闭，用宿主机 cron + `scripts/backup_data.sh`。

---

## cursor-1 日常命令（PR #64 合并后）

```bash
cd /path/to/smart-finance-platform
git fetch origin && git checkout main && git pull --ff-only origin main

source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data

# 首次或改 compose 后
sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --build

# 日常滚动（不碰 MySQL / Redis / Influx）
bash scripts/deploy_and_verify_slim.sh
```

### 验收

```bash
sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
sudo docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}'
curl -sf http://127.0.0.1:19099/health && echo
curl -sf http://127.0.0.1:12580/ -o /dev/null -w '%{http_code}\n'
```

- 应有：`sentiment-backend`、`sentiment-trade`、`sentiment-data`、`sentiment-intel`、`sentiment-jobs`、`sentiment-frontend` 为 healthy
- **不应**再跑：`sentiment-market`、`sentiment-ai`、`jobs-market` 等 full-split 容器名
- Influx healthy 后空闲 5 分钟，整栈 RSS **< 5.5 GiB**

### 禁止（与 DEPLOY.md 一致）

- `docker compose down` / `down -v`
- 为「省内存」重建 MySQL / Redis / Influx
- 在 cursor-1 上无 overlay 起 full 栈
- 改 grok2api

---

## 从 full-split 迁到 slim（一次性）

1. 确认 Influx 数据已在 `$SFP_DATA_ROOT/influx/data`（或已 bind 到 slim 卷）。
2. **不要** `compose down -v`。
3. 双文件 `up -d --build`；overlay 的 `profiles: [full-split]` 会停掉拆分服务。
4. 若残留旧容器：`sudo docker rm -f sentiment-market sentiment-quant sentiment-news sentiment-ai sentiment-jobs-market sentiment-jobs-quant sentiment-jobs-llm`（仅当已停且无依赖）。

细节见 PR #64 合并后的 [SLIM-POST-MERGE.md](./SLIM-POST-MERGE.md)。

---

## 后续迁移：market-read 与 workers（计划，独立 PR）

以下 **尚未在本仓库实现**；落地在后续 PR，**不改变**侧栏功能说明中的用户操作路径。

### market-read（Go / Rust）

**目标**：把高 QPS、低延迟的 **行情读取** 从 Python `sentiment-data` 拆出为独立进程，减轻 Influx tail / 报价缓存 / 指数 WS 对 API 进程的压力。

| 范围（计划） | 现 Python 职责 | 迁移后 |
|--------------|----------------|--------|
| K 线 tail、日 K 批量读 | `module_market` Influx 查询 | Go/Rust `market-read` 服务，同源 Influx |
| 热度 / Top50 快照读 | Redis + Influx 聚合 | 同上，HTTP 仍经 nginx 反代 |
| 指数报价、行情 WS 推送 | 长桥订阅 + 内存缓存 | 读路径迁出；**写路径 / 下单仍在 `sentiment-trade`** |

**不变**：`/market/*`、`/quant/*` URL、JWT、Flutter/Web 轮询与 WS 协议；nginx 仅改 upstream 目标。

### workers（Go / Rust）

**目标**：Redis 队列消费（market / quant / llm）逐步由 **Go/Rust worker** 承担，Python `sentiment-jobs` 保留 **APScheduler 入队** 或最终也迁出。

| 队列 | 典型任务 | 迁移顺序（计划） |
|------|----------|------------------|
| `market` | 热度采集、收盘 K、自选分析 | 第二批 |
| `quant` | 因子日扫、自动交易扫描、次日清单 | 第三批 |
| `llm` | Grok 研判、需求沟通、舆情分析 | 最后（依赖模型 HTTP） |

**不变**：任务中心启停、立即执行、`GET /market/jobs/{jobId}` ticket 状态机、Redis 队列名与 payload 契约。

### 与 slim 的关系

- Slim 是当前 **16 GiB 上的进程合并**；Go/Rust 迁移是 **语言/runtime 拆分**，可叠加在 slim 拓扑上（例如 `sentiment-market-read` 容器替换 `sentiment-data` 中的读逻辑）。
- 每个迁移 PR 应自带：compose 服务定义、回滚说明、本文件与 [DEPLOY.md](./DEPLOY.md) 的增量更新。

---

## 子系统功能说明索引

侧栏「使用说明」与本文一致口径：

| 模块 | 指南文件 | Slim / 迁移相关要点 |
|------|----------|---------------------|
| 行情中心 | `resources/guides/market.md` | slim 下 market+quant 同进程；market-read 迁 Go 后路径不变 |
| 任务中心 | `resources/guides/analysis.md` | slim 单 `sentiment-jobs`；workers 迁 Go 后仍显示 jobs 在线 |
| 舆情 / AI | `resources/guides/sentiment.md`、`ai.md` | slim 下 intel 合并；LLM 队列后续迁 worker |
| 量化 / 交易 | `resources/guides/quant.md`、`trade.md` | `sentiment-trade` 始终独立；quant 队列 worker 可迁 Go |

---

## 相关 PR

| PR | 内容 |
|----|------|
| **#64** | Slim overlay、`docker-compose.sentiment.slim.yml`、`deploy_and_verify_slim.sh`、`SFP-TWO-HOST-DEPLOY.md`、`SLIM-POST-MERGE.md` |
| **后续** | `market-read` Go/Rust 服务、队列 worker Go/Rust 消费端（分 PR 交付） |
