# Smart Finance Platform · 智慧金融分析平台

## 项目概述

Smart Finance Platform 是一套面向二级市场研究与交易辅助的一体化平台，底座是 **RuoYi-Vue3 + FastAPI**，业务覆盖 **行情、舆情、量化、交易、AI 研判**。列表浏览走 Influx / MySQL，长桥只用于交易台实时报价和下单；调度与长任务从 API 进程拆出，避免 Grok / 采集把 HTTP 打满。

本仓库 2026-07-23 首次公开，默认分支 `main`。贡献走功能分支 + Pull Request，禁止直接推 `main`。详见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 核心功能一览

- **行情中心**：三市场热度与 Top50、全部股票（全市场分页）、行情台（精选报价）、自选三栏（分组 / K 线 / 详情）、财经资讯、AI 研判；K 线、标的详情、高级图从列表点入，不占侧栏。
- **自选按账号隔离**：行情自选只走 `market_watchlist` + `user_id`；量化扫描池继续用 `quant_watchlist`，两套不混。分组先写在 `note`（逗号可多组）。
- **舆情分析**：中文资讯采集、大盘影响研判、分析历史；列表页不叠长桥实时价。
- **量化研究**：因子、Alphalens 风格 IC/IR/分层收益、策略信号、扫描台账、策略档位与 8 族权重。
- **交易中心**：长桥账户 / 持仓 / 委托、盘口深度与分时、纸面自动交易（默认不实盘下单）、风控规则与事件、通知中心。
- **长桥按登录账户**：每人一行 App Key / Secret / Token；交易与实时报价用当前用户；jobs 无登录上下文时回退 admin。
- **AI 研判**：单标的研判、批量扫描、需求沟通群（Grok 入 `llm` 队列，不堵 API）、模型管理。
- **任务拆分**：`sentiment-jobs` 只跑 APScheduler；market / quant / llm 三个消费组；交易实时单独进程。
- **桌面端**：Electron 启动先配前端网关再登录，本机 Docker 与云上域名可切换。
- **监控（可选）**：Prometheus + Grafana，后端 `/metrics`。

## 0823 迭代（行情中心全部股票）

提交 `7f52337`（2026-08-23）。

- 侧栏增加「全部股票」：美 / 港 / A 股全市场代码分页浏览，搜索、加自选、点入 K 线与详情。
- `GET /market/instrument/universe` 强制分页（默认 50、最大 200），当前页附带本地日K最新价；精选接口 `/market/instrument/list` 仍不一次打出 listed。
- 增量 SQL：`sql/market-universe-menu.sql`（也可重跑 `sql/market-menu-unify.sql`）。

## 0822 迭代（自选按用户隔离、行情侧栏压平、长桥按账户）

提交 `b31b08a`（2026-08-22）。

### 1. 行情自选只走 `market_watchlist`
- 列表 / 新增 / 删除 / 概览 / 分析 / 回测 / 小时任务全部带当前 `user_id`，不再误走全局 `quant_watchlist`。
- 量化扫描池仍用 `quant_watchlist`，两套分开。
- 热度 Top50「已在自选」按当前用户判断；加入自选写入当前账号。

### 2. 自选页三栏（分组先用 note）
- 左：从 `note` 解析分组（逗号分隔，一只可多组）+ 标的列表。
- 中：日 / 周 / 月 K 线。
- 右：报价、分组、备注、综合分析。窄屏收起右侧，左 + 中保留。
- 本机 lustone（`user_id=101`）已有 130 只可直接用，不等另做导入。

### 3. 长桥凭据按登录账户（对齐 PR #16）
- `GET/PUT /quant/longbridge/config` 与连通性测试只读写当前用户行。
- 请求级 `ContextVar` 注入凭据，交易 / 实时报价不串号。
- jobs 无用户上下文时回退 `user_id=1`，再 env。
- 保存时掩码 `****` 不覆盖原密钥。增量 SQL：`sql/quant-longbridge-user.sql`。

### 4. 行情中心侧栏
- 只留五个入口：市场热度、行情台、自选清单、财经资讯、AI研判。
- K 线 / 详情 / 高级图 / 覆盖检测从页面点入。增量 SQL：`sql/market-menu-unify.sql`。

## 0821 迭代（热度看板、API 与长任务拆开、长桥熔断）

### 1. 市场热度与 Top50
- 美 / 港 / A 股收盘采集指数涨跌、成交额、涨跌家数，写入 `market_heat_daily` 与 `market_top50_snapshot`。
- 市值过滤、权重走 `sys_config`，任务进 `sentiment-jobs` 队列。

### 2. API 与长任务隔离
- APScheduler 只在 `sentiment-jobs`；market / quant / llm 三个消费组分开。
- 交易实时单独进程，禁止和 LLM / 采集共进程。
- 行情台报价读 Redis / SWR；全市场 Influx 扫描进 jobs。
- 需求沟通「发送 / 总结」入 `llm` 队列立即返回 `jobId`，Grok 不再堵 API worker。

### 3. 浏览行情只走库，长桥留给交易台
- 自选概览、行情台、标的详情的列表报价不再 overlay 长桥实时价 / static_info。
- 无效 Token 不再把列表页打挂。交易台分钟 / 分时仍走长桥，失败软降级。

### 4. 熔断与队列
- 长桥 401004 / 超时拉共享熔断器，后续任务路径不再打券商。
- 长任务入 Redis，消费失败可 inline 回退。异步长桥调用限流。

### 5. 量化、自选与桌面
- Alphalens 风格截面 Spearman IC / IR / 五分位收益，因子页面板 + 日任务。
- 自选小时综合（技术 + 长桥资讯 + 舆情），建议 1/5 日前瞻回测，报价 8s 轮询。
- 策略 8 族权重入打分与扫描；因子快照 CSV 导出。
- Electron 每次启动先开网关配置窗；订单刷新成交数量。
- GitHub Actions：后端单测 + 网关 URL 检查。

### 6. 风控与 Alpha
- 风险事件审批流。
- Alpha101 / 158 快照与 ReadModel 定时任务。

## 0820 迭代（交易台报价板、门户、登录皮肤、纸面自动交易）

### 1. 交易台
- 当前标的深度、逐笔、周期 K 线；K 线（或分时）叠在盘口与成交明细上方。
- 空 K 线不再留 360px 白块；持仓跳 `/trade/trading?symbol=` 跟路由。

### 2. 门户与登录
- 门户 16 个入口收成六组卡片，去掉「若依官网」菜单种子。
- 登录浅色 / 深色与门户、系统 chrome 同一套 VueUse 键，刷新不丢。

### 3. 行情与空状态
- 真源 K 线 seeder（新浪 / 腾讯 + 降级，带熔断），禁止合成 OHLCV。
- 看板批量报价；TradingView 港股代码候选。
- 资讯 / 舆情 429 / Druid / 未配券商账户的空状态。

### 4. 自动交易（默认纸面）
- 扫描默认不提交订单：纸面保护 + 长桥交易开关只在服务端。
- 长桥调用线程卸载 + 短 Redis 缓存；K 线默认不再拉十年窗口。
- Prometheus 指标、`docker-compose.monitor.yml`、AI 工作台 One-Shot / 投研顾问。

## 0723 首次公开发布

提交 `743b13f`（2026-07-23）。

独立公开的 RuoYi 行情 / 舆情 / 量化 / 交易 / AI 工作台，配置只留 `.env.*.example`，贡献要求 PR 进 `main`。

## 快速开始

### 1. 环境变量（不要提交真实密钥）

```bash
cp ruoyi-fastapi-backend/.env.dockersentiment.example \
   ruoyi-fastapi-backend/.env.dockersentiment
cp ruoyi-fastapi-frontend/.env.docker.example \
   ruoyi-fastapi-frontend/.env.docker
```

至少改 JWT、MySQL 密码（与 compose 一致）、默认 `admin / admin123`。长桥与 AI Key 可选。

### 2. Docker（推荐）

```bash
docker compose -f docker-compose.sentiment.yml up -d --build
```

| 服务 | 地址 |
|------|------|
| 前端 / 网关 | http://127.0.0.1:12580 |
| 平台 API | http://127.0.0.1:19099 （OpenAPI `/docs`） |
| jobs 调度 | http://127.0.0.1:19098/health |
| MySQL | 13306 |
| Redis | 16379 |
| InfluxDB | 18086 |

**禁止 `compose down` 整栈。** 更新单个服务：

```bash
docker compose -f docker-compose.sentiment.yml up -d --no-deps --build sentiment-backend sentiment-frontend
```

已有库增量 SQL 见 [docs/DEPLOY.md](./docs/DEPLOY.md)（含 `market-menu-unify.sql`、`quant-longbridge-user.sql`、`market-universe-menu.sql`）。

补全市场代码与日K（本机 Docker 默认口，限流慢拉）：

```bash
ruoyi-fastapi-backend/.venv/bin/python scripts/sync_market_listings.py
ruoyi-fastapi-backend/.venv/bin/python -u scripts/sync_klines_slow.py
touch logs/kline_sync.stop   # 下一只标的前退出
```

### 3. 桌面端

```bash
cd desktop && npm install && npm start
```

先填前端网关再登录：本机 `http://127.0.0.1:12580`，云上填已部署域名。不要填后端 `19099`。

### 4. 检查（可选）

```bash
cd ruoyi-fastapi-backend && uv run pytest tests/ -q
npm install && npx playwright install chromium && npm run e2e:web
```

监控：`docker compose -f docker-compose.monitor.yml up -d`（Prometheus 19090 · Grafana 13000）。

## 目录与技术栈

```text
smart-finance-platform/
├── docker-compose.sentiment.yml   # 默认业务栈
├── docker-compose.monitor.yml     # Prometheus / Grafana
├── docs/DEPLOY.md
├── ruoyi-fastapi-backend/         # FastAPI
│   ├── module_market/  module_sentiment/  module_quant/
│   ├── module_trade/   module_ai/         module_analysis/
│   └── sql/
├── ruoyi-fastapi-frontend/        # Vue3 管理端
├── ruoyi-fastapi-app/             # 移动端基线
└── desktop/                       # Electron
```

- **前端**：Vue 3 · Element Plus · Vite · ECharts · Pinia
- **后端**：Python ≥3.10 · FastAPI · SQLAlchemy async · JWT
- **数据**：MySQL 8（业务）· Redis（会话 / 队列 / 缓存）· InfluxDB 2.x（K 线）
- **券商**：Longbridge OpenAPI（可选）

## 安全

- 仓库只有 `.env.*.example`，不含生产密钥。
- 不要提交 `DB_PASSWORD` / `JWT_SECRET` / `INFLUX_TOKEN` / 长桥 Token / RSA 私钥。
- 长桥交易开关与纸面保护在服务端，前端关不掉实盘拦截。

## 致谢

- 管理端底座：[RuoYi-Vue3-FastAPI](https://github.com/insistence/RuoYi-Vue3-FastAPI)
- 前端参考：[RuoYi-Vue3](https://github.com/yangzongzhuan/RuoYi-Vue3)

## License

MIT（以本仓库 `LICENSE` 为准；上游组件遵循其各自许可证）
