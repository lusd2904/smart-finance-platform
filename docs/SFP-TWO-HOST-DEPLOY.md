# 双机 / 云主机部署（SFP + grok2api）

适用：**生产云主机（cursor-1，16 GiB）** 与 **大内存开发机** 共用同一仓库，编排分 **slim** / **full** 两档。

运维速查（内存预算、迁移路线）：[MEMORY-SLIM-AND-MIGRATION.md](./MEMORY-SLIM-AND-MIGRATION.md)。  
行情 WS / live quotes 离开 `sentiment-data`：[SENTIMENT-DATA-OFFLOAD.md](./SENTIMENT-DATA-OFFLOAD.md)。  
Slim overlay 与 compose 定义：**PR #64**；合并后见 [SLIM-POST-MERGE.md](./SLIM-POST-MERGE.md)。

---

## cursor-1（生产，~15 GiB RAM）

与 **grok2api** 同机。**full-split 禁止用于 cursor-1 生产。** slim 栈长期稳态 RSS 目标 **4–5 GiB**（Influx 降至 3g 之后）。

### Influx 冷打开 — cursor-1 已验证（18G / ~2992 shard）

| 配置 | 结果 |
|------|------|
| 6g / 8g / 10g（无 swap） | OOM；10g 在 72.8% shard ~10.3GiB anon RSS |
| **12g + `GOMEMLIMIT: 10GiB` + 4G loop swap** | **healthy**，峰值 **~11.7GiB** |

`GOMEMLIMIT` 必须为整数 MiB/GiB（`5.2GiB` → `malformed GOMEMLIMIT` fatal）。

**冷开三要素：**

1. **vfs 服务级 bind**（`docker-compose.sentiment.slim.yml` 内 `volumes: !override`）  
2. **`mem_limit` ≥12g** + **`GOMEMLIMIT: 10GiB`**  
3. **4G loop swap** + 暂停 **grok2api**

验收 bind：

```bash
sudo docker inspect sentiment-influxdb --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
# 期望: /workspace/sfp-data/influx -> /var/lib/influxdb2
```

#### 4G loop swap（cursor-1 实测）

```bash
sudo dd if=/dev/zero of=/swapfile-influx bs=1M count=4096 status=progress
sudo chmod 600 /swapfile-influx
sudo mkswap /swapfile-influx
sudo swapon /swapfile-influx
# 验证: free -h | grep -i swap
# 全栈稳定后可 swapoff；下次冷开前再 swapon
```

### Influx 内存阶段

| 阶段 | compose 文件 | Influx `mem_limit` | `GOMEMLIMIT` | 说明 |
|------|----------------|-------------------|--------------|------|
| **COLD_OPEN**（默认 slim） | `docker-compose.sentiment.slim.yml` | **12g** | **10GiB** | 冷开 + 全栈验收期间保持 |
| **STEADY**（可选，日后） | `+ docker-compose.sentiment.slim.influx-steady.yml` | **3g** | **2560MiB** | **勿冷开后立即应用** |

```bash
# 1) 冷打开（首次恢复 / 大库）— 先 swapon + 停 grok2api
sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d sentiment-influxdb
# 等待 healthy（可能 10+ 分钟）

# 2) 长期稳态降内存（可选 — 全栈 idle 数日后，非冷开刚完成时）
# bash scripts/influx_slim_steady.sh
```

### 数据目录

```text
/workspace/sfp-data/
  mysql/              # → /var/lib/mysql（可为空，待 shard 上传）
  redis/              # → Redis AOF
  influx/             # → /var/lib/influxdb2（influxd.bolt, influxd.sqlite, engine/，约 18 GiB）
  influx-config/      # → /etc/influxdb2
```

**不要使用** `influx/data` 或 `influx/config` 子路径 — 会 bind 到空目录并遮住已恢复的 18G 时序库。

```bash
export SFP_DATA_ROOT=/workspace/sfp-data
mkdir -p "$SFP_DATA_ROOT"/{mysql,redis,influx,influx-config}
```

slim overlay **默认**用 **服务级 bind**（非 named volume `driver_opts`）挂到上述路径——cursor-1 **vfs** 存储驱动下 `driver_opts` bind 无效（`_data` 为空）。

### Docker

- Socket：`/var/run/docker.sock`（`root:docker`）→ 使用 **`sudo docker`** / **`sudo docker compose`**
- 数据根：`/workspace/docker`（**vfs** storage driver — 必须用服务级 bind，见 `docker-compose.sentiment.slim.yml`）
- Agent 沙箱内无 socket 时：`source scripts/docker_host.sh` → `DOCKER_HOST=tcp://127.0.0.1:2375`

### 启动（PR #64 合并后 **仅 slim**）

```bash
cd /path/to/smart-finance-platform
git fetch origin && git checkout main && git pull --ff-only origin main

source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data

sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --build
```

日常滚动：

```bash
bash scripts/sfp_data_init.sh
bash scripts/deploy_and_verify_slim.sh
```

**MySQL 分片尚未上传时**（仅验证 Influx 热度/分钟 K 线）：

```bash
bash scripts/sfp_data_init.sh --influx-only
bash scripts/up_slim_influx_phase.sh
# 只起 ruoyi-redis + sentiment-influxdb；登录/热度/任务需 Phase B（Go）
bash scripts/sfp_data_init.sh   # 创建 mysql/
sudo docker compose -f docker-compose.sentiment.yml -f docker-compose.sentiment.slim.yml up -d --build
```

`mysql/` **空目录合法**：首次 `up` 时 MySQL 容器会跑 init SQL；若从 Mac 上传 datadir，先停 MySQL 再替换目录内容。

### 验收

```bash
sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
sudo docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}'
curl -sf http://127.0.0.1:19099/health && echo
curl -sf http://127.0.0.1:12580/ -o /dev/null -w '%{http_code}\n'
```

应看到：`sfp-backend`、`sentiment-trade-api`、`sentiment-data-api`、`sfp-intel`、`sfp-scheduler`、`sentiment-frontend` 为 healthy；**不应**再跑 Python fat（`sentiment-backend` / `sentiment-data` / `sentiment-intel` / `sentiment-trade`）或 `sentiment-market` / `sentiment-ai` / `jobs-market` 等拆分容器。

### 禁止

| 不要 | 原因 |
|------|------|
| `compose down` / `down -v` | Influx 冷启动慢；`-v` 丢 18G 时序 |
| 无 overlay 的全量拆分栈 | 10+ Python 进程，16G 主机易 OOM |
| 改 grok2api | 独立服务 |

备份（slim 默认不启 `sfp-backup` 容器）：宿主机 cron 跑 `bash scripts/backup_data.sh`。

---

## 开发机 / 大内存（full split）

内存充裕时用 **单文件** 全量拆分（6 API + 4 jobs），便于隔离 profiling：

```bash
docker compose -f docker-compose.sentiment.yml up -d --build
bash scripts/deploy_and_verify.sh
```

PR #64 合并后若仍要临时起拆分容器：`--profile full-split`。**不要在 cursor-1 上使用。**

---

## 合并后路线

1. **Slim 固定 cursor-1 生产** — 见 [SLIM-POST-MERGE.md](./SLIM-POST-MERGE.md)（PR #64 合并后；Go workers 见 PR #67）。
2. **Go-only slim（已落地）** — 热读 + 行情 WS → `sentiment-market-read`；其余 `/market/` + `/quant/` → `sentiment-data-api`。Python fat 默认不启动（`--profile legacy-python` 紧急回退）。
