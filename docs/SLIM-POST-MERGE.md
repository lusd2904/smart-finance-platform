# Slim 合并后运维说明（cursor-1）

本文件描述 **PR #64（slim overlay）合并之后** 在 16 GiB 生产机上的固定做法，以及 **下一 PR** 如何去掉冗余拆分容器。

---

## 合并后：cursor-1 只用 slim

生产命令（Coordinator 合并后由主机管理员执行，**Agent 不自行 merge**）：

```bash
git fetch origin && git checkout main && git pull --ff-only origin main
source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data

sudo docker compose \
  -f docker-compose.sentiment.yml \
  -f docker-compose.sentiment.slim.yml \
  up -d --build
```

- 数据：`/workspace/sfp-data`（Influx 已有数据；MySQL 待上传后首次 init）
- 内存：Influx **冷开** `mem_limit` **4g**；全栈 **稳态**（healthy 后 `influx-steady` 叠加）RSS 目标 **4–5 GiB**
- 功能：登录、热度、舆情、选股、交易、自选、H5 `/m`、任务中心 jobs **路径与行为不变**
- `sentiment-trade` **仍独立**；LLM/采集不与交易共进程

### 从旧 full 栈迁移到 slim

1. **不要** `compose down -v`。
2. 确认 Influx 数据已在 `$SFP_DATA_ROOT/influx/`（含 `engine/`、`influxd.bolt` 等）。
3. 用双文件 `up -d --build`；overlay 的 `profiles: [full-split]` 会停掉拆分 API/worker。
4. 若仍有旧容器名：`sudo docker rm -f sentiment-market sentiment-quant sentiment-news sentiment-ai sentiment-jobs-market sentiment-jobs-quant sentiment-jobs-llm`（仅当已停且确认无依赖）。

---

## 下一 PR（计划，本 PR 不实施）

目标：**删除**默认 compose 中的冗余拆分服务，避免新人误起 full 栈导致 OOM。

可选方案（二选一，由 Coordinator 定）：

| 方案 | 做法 |
|------|------|
| **A. Slim 为默认** | 将 `docker-compose.sentiment.slim.yml` 内容并入 `docker-compose.sentiment.yml`；删除 `sentiment-market` 等 7 个服务定义；`full-split` 移至 `docker-compose.sentiment.full.yml` 可选 overlay |
| **B. 仅删 dead 代码** | 保留 base 中 `profiles: [full-split]` 的拆分服务定义但文档标明 deprecated；cursor-1 文档只引用 slim 双文件 |

无论哪种，需同步：

- `scripts/deploy_and_verify.sh` → slim 为默认或拆成 `deploy_full.sh`
- `ruoyi-fastapi-frontend/bin/nginx.dockersentiment.conf` → 仅保留 slim 上游或按 profile 切换
- `docs/DEPLOY.md`、`SFP-TWO-HOST-DEPLOY.md` 云主机章节

---

## 验证清单（主机 retest，合并后）

```bash
source scripts/docker_host.sh
export SFP_DATA_ROOT=/workspace/sfp-data

# 1. 配置合法
sudo docker compose -f docker-compose.sentiment.yml -f docker-compose.sentiment.slim.yml config >/dev/null

# 2. 起栈（或 deploy 脚本）
bash scripts/deploy_and_verify_slim.sh

# 3. 健康
sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | rg 'sentiment-(backend|trade|data|intel|jobs|frontend|influx)'

# 4. 内存（Influx healthy 后空闲 5 分钟；冷开阶段 Influx 允许 4g）
sudo docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}'
# 稳态：整栈 RSS ~4–5 GiB。若仍用冷开 4g，healthy 后跑: bash scripts/influx_slim_steady.sh

# 5. 功能冒烟
curl -sf http://127.0.0.1:19099/health
curl -sf http://127.0.0.1:12580/ -o /dev/null -w '%{http_code}\n'
# 浏览器：登录、/m 热度、舆情、选股、交易台、任务中心 jobs 在线

### Influx-only 阶段（MySQL 未就绪）

```bash
bash scripts/sfp_data_init.sh --influx-only
bash scripts/up_slim_influx_phase.sh
# 仅验证 sentiment-data 热度/分钟 K 线读路径；登录与舆情需全栈
```
