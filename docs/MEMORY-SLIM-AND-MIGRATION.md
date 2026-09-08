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
| `sentiment-data` | remaining market + quant API + WS | 其余 `/market/`、`/quant/`、`/ws/` |
| `sentiment-market-read` | Go 热读（256m） | kline / board / heat / index / `symbols/*/history` |
| `sentiment-intel` | sentiment + ai（含采集） | `/sentiment/`、`/ai/`、`/open/`（除 `/open/sync/`） |
| `sentiment-trade` | **仍独立** | `/trade/` |
| `sentiment-jobs` | `APP_JOB_GROUP=none`：仅 APScheduler；market/quant/llm 队列由 Go workers 消费 | 任务中心「jobs 在线」 |
| `sfp-market-worker` / `sfp-quant-worker` / `sfp-notify-worker` | Go 消费三队列（slim ~768m RSS 合计） | 后台任务执行 |
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

- 应有：`sentiment-backend`、`sentiment-trade`、`sentiment-data`、`sentiment-intel`、`sentiment-jobs`、`sentiment-market-read`、`sfp-market-worker`、`sfp-quant-worker`、`sfp-notify-worker`、`sentiment-frontend` 为 healthy
- **不应**再跑：`sentiment-market`、`sentiment-ai`、`jobs-market` 等 full-split 容器名（`sentiment-market-read` 是 slim 热读，不是 full-split）
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

## market-read on slim（已落地）

PR **#66** / **#67** 落地 full 栈 `sentiment-market-read` 与三 Go workers。**Slim 生产（cursor-1）现状**：

| 组件 | Slim 状态 |
|------|-----------|
| Go workers（market / quant / llm） | **已启用**（`docker-compose.sentiment.slim.yml` + `deploy_and_verify_slim.sh`） |
| `sentiment-market-read` | **已启用**（去掉 slim `profiles: [full-split]`）；slim nginx 热读与 full 栈相同 |
| `sentiment-data` | **仍保留**：`/quant/`、其余 `/market/`、行情 WS。**不要删除。** `mem_limit` 仍 512m |
| `sentiment-jobs` | scheduler-only（`APP_JOB_GROUP=none`） |

HTTP / ticket / WS 契约不变。`sentiment-data` 512m → 384m 需 cursor-1 实测后再降。

### 与 slim 的关系

- Slim 是当前 **16 GiB 上的进程合并**；Go workers + market-read 已叠加在 slim 拓扑上。
- `sentiment-market-read` 只替换热读路径；量化、剩余行情写/业务、行情 WS 仍在 `sentiment-data`。

---

## 子系统功能说明索引

侧栏「使用说明」与本文一致口径：

| 模块 | 指南文件 | Slim / 迁移相关要点 |
|------|----------|---------------------|
| 行情中心 | `resources/guides/market.md` | slim 下 remaining market+quant 同进程；热读 offload 至 Go market-read |
| 任务中心 | `resources/guides/analysis.md` | slim：`sentiment-jobs` scheduler + 三 Go workers |
| 舆情 / AI | `resources/guides/sentiment.md`、`ai.md` | slim 下 intel 合并；LLM 队列后续迁 worker |
| 量化 / 交易 | `resources/guides/quant.md`、`trade.md` | `sentiment-trade` 始终独立；quant 队列 worker 可迁 Go |

---

## 相关 PR

| PR | 内容 |
|----|------|
| **#64** | Slim overlay、`docker-compose.sentiment.slim.yml`、`deploy_and_verify_slim.sh`、`SFP-TWO-HOST-DEPLOY.md`、`SLIM-POST-MERGE.md` |
| **#66** | Full 栈 `sentiment-market-read`（Go 热读） |
| **#67** | Go workers + slim scheduler-only `sentiment-jobs` |
| **本 PR** | Slim 启用 `sentiment-market-read` + nginx 热读 offload；`sentiment-data` 仍保留 |
