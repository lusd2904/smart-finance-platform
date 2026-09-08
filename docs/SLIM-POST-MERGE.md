# Slim 合并后运维说明（cursor-1）

本文件描述 **PR #64（slim overlay）合并之后** 在 16 GiB 生产机上的固定做法，以及 **Go workers（PR #67）** 在 slim 上的部署方式。

---

## 合并后：cursor-1 只用 slim

生产命令（Coordinator 合并后由主机管理员执行，**Agent 不自行 merge**）：

```bash
cd /workspace/sfp-slim-64   # cursor-1 部署树（git checkout main）
git fetch origin && git checkout main && git pull --ff-only origin main
source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data

sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --build
```

日常滚动（不碰 MySQL / Redis / Influx）：

```bash
bash scripts/deploy_and_verify_slim.sh
```

### Compose 文件与服务名（hub 必跑）

| 文件 | 作用 |
|------|------|
| `docker-compose.sentiment.yml` | 基础服务定义 |
| `docker-compose.sentiment.slim.yml` | **cursor-1 唯一 overlay**（合并 API、Go workers、Influx 12g） |
| `docker-compose.sentiment.scheduler-python.yml` | 可选：回滚到 Python `sentiment-jobs`（见 [SFP-SCHEDULER.md](./SFP-SCHEDULER.md)） |

**全栈 `up -d --build` 会起的 slim 服务**（`profiles: [full-split]` 的拆分 API **不会**起；`sentiment-market-read` **会**起）：

| 服务名 | 容器名 | 说明 |
|--------|--------|------|
| `sentiment-mysql` | `sentiment-mysql` | MySQL |
| `ruoyi-redis` | `sentiment-redis` | Redis DB 2 队列 |
| `sentiment-influxdb` | `sentiment-influxdb` | 冷开 12g |
| `sentiment-backend` | `sentiment-backend` | 登录 / 系统 |
| `sentiment-trade` | `sentiment-trade` | 交易（独立） |
| `sentiment-data-api` | `sentiment-data-api` | remaining `/market/` + `/quant/`（Go；热读与行情 WS 已 offload） |
| `sentiment-market-read` | `sentiment-market-read` | Go 热读 + WS / live quotes，320m |
| `sentiment-intel` | `sentiment-intel` | sentiment + ai API |
| `sfp-scheduler` | `sfp-scheduler` | Go 读 `sys_job` 入队（Python `sentiment-jobs` 仅回滚） |
| `sfp-market-worker` | `sfp-market-worker` | Go 消费 **market** 队列 |
| `sfp-quant-worker` | `sfp-quant-worker` | Go 消费 **quant** 队列（含 Longbridge 交易作业，见 `docs/TRADE-GO-MIGRATION.md`） |
| `sfp-notify-worker` | `sfp-notify-worker` | Go 消费 **llm** 队列 |
| `sentiment-frontend` | `sentiment-frontend` | nginx（`nginx.dockersentiment.slim.conf`） |

- 数据：`$SFP_DATA_ROOT`（cursor-1 默认 `/workspace/sfp-data`；Influx 已有数据；MySQL 待上传后首次 init）
- 内存：Influx **冷开** `mem_limit` **12g** / `GOMEMLIMIT` **10GiB** + **4G loop swap**（vfs 服务级 bind；峰值 ~11.7GiB → healthy）。**勿冷开后立即降至 3g**；长期稳态可选 `influx-steady`
- 功能：登录、热度、舆情、选股、交易、自选、H5 `/m`、任务中心 jobs **路径与行为不变**
- `sentiment-trade` **仍独立**；LLM/采集不与交易共进程

### market-read 与 slim nginx

- **Full / Slim 栈**：nginx 把 K 线 / 热度 / 看板 / 指数条 / `symbols/*/history` / `quotes/live` / `WS /ws/market/quotes` offload 到 `sentiment-market-read`（Go，`mem_limit` 320m）。
- **Slim 仍保留 `sentiment-data`**：`/quant/`、其余 `/market/` 仍走 Python。**不要删除 `sentiment-data`。**
- `sentiment-data` slim `mem_limit` 仍为 **512m**（量化 + 剩余行情尚未测到可安全降到 384m；后续再压）。
- 行为不变：URL、JWT、WS 协议相同。回退只改 nginx，见 [SENTIMENT-DATA-OFFLOAD.md](./SENTIMENT-DATA-OFFLOAD.md)。

### 从旧 full 栈迁移到 slim

1. **不要** `compose down -v`。
2. 确认 Influx 数据已在 `$SFP_DATA_ROOT/influx/`（含 `engine/`、`influxd.bolt` 等）。
3. 用双文件 `up -d --build`；overlay 的 `profiles: [full-split]` 会停掉拆分 API / Python fallback workers。`sentiment-market-read` **会**随 slim 启动。
4. 若仍有旧容器名：`sudo docker rm -f sentiment-market sentiment-quant sentiment-news sentiment-ai sentiment-jobs-market sentiment-jobs-quant sentiment-jobs-llm`（仅当已停且确认无依赖）。**不要**删正在跑的 `sentiment-market-read`。

---

## 验证清单（主机 retest，#67 合并后）

```bash
cd /workspace/sfp-slim-64
source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data

# 1. 配置合法
sudo docker compose -f docker-compose.sentiment.yml -f docker-compose.sentiment.slim.yml config >/dev/null

# 2. 起栈（或 deploy 脚本）
bash scripts/deploy_and_verify_slim.sh

# 3. 健康（Influx healthy 后）
sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | rg 'sentiment-(backend|trade|data|intel|frontend|influx|market-read)|sfp-'

# 4. Worker / scheduler 回环健康
curl -sf http://127.0.0.1:19098/health && echo   # sfp-scheduler
curl -sf http://127.0.0.1:19097/health && echo   # sfp-market-worker
curl -sf http://127.0.0.1:19096/health && echo   # sfp-quant-worker
curl -sf http://127.0.0.1:19095/health && echo   # sfp-notify-worker
docker exec sentiment-market-read wget -q --spider http://127.0.0.1:8080/health && echo market-read ok

# 5. 内存（冷开 12g + swap；healthy 后保留 headroom — 勿立即 influx_slim_steady）
sudo docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}'

# 6. 功能冒烟
curl -sf http://127.0.0.1:19099/health
curl -sf http://127.0.0.1:12580/ -o /dev/null -w '%{http_code}\n'
# 浏览器：登录、/m 热度、舆情、选股、交易台、任务中心 jobs 在线
```

### Influx-only 阶段（MySQL 未就绪）

```bash
bash scripts/sfp_data_init.sh --influx-only
bash scripts/up_slim_influx_phase.sh
# 仅验证 sentiment-data 热度/分钟 K 线读路径；登录、舆情、Go workers 需全栈（Phase B）
```

Phase B（MySQL 就绪后）：

```bash
bash scripts/sfp_data_init.sh
sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --build
```

---

## Go quant-worker 原生任务（P2）

`sfp-quant-worker` 原生跑 `factor_scan` / `factor_qc` / `strategy_run` / `daily_list_scan`（#77）以及 `daily_list_open` / `auto_trade_scan` / `position_monitor` MO sell（#78）。门户 `/trade/*` 仍走 `sentiment-trade`。

cursor-1 只重建 worker（不碰 MySQL / Redis / Influx）：

```bash
sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --no-deps --build sfp-quant-worker

curl -sf http://127.0.0.1:19096/health
```

冒烟步骤见 `workers/quant-worker/README.md`。

---

## 下一 PR（计划，本 PR 不实施）

目标：**删除**默认 compose 中的冗余拆分服务，避免新人误起 full 栈导致 OOM。**不要删除 `sentiment-data`**（slim 上仍承接 `/quant/`、剩余 `/market/` 写/入队）。

可选方案（二选一，由 Coordinator 定）：

| 方案 | 做法 |
|------|------|
| **A. Slim 为默认** | 将 `docker-compose.sentiment.slim.yml` 内容并入 `docker-compose.sentiment.yml`；删除 `sentiment-market` 等拆分 API 定义；`full-split` 移至 `docker-compose.sentiment.full.yml` 可选 overlay |
| **B. 仅删 dead 代码** | 保留 base 中 `profiles: [full-split]` 的拆分服务定义但文档标明 deprecated；cursor-1 文档只引用 slim 双文件 |

无论哪种，需同步：

- `scripts/deploy_and_verify.sh` → slim 为默认或拆成 `deploy_full.sh`
- 在 cursor-1 实测后再评估 `sentiment-data` 512m → 384m
- `docs/DEPLOY.md`、`SFP-TWO-HOST-DEPLOY.md` 云主机章节
