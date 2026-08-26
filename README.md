# Smart Finance Platform - 智慧金融分析平台

## 项目概述

Smart Finance Platform 是一套面向二级市场研究与交易辅助的本地/私有化一体化平台。底座是 **RuoYi-Vue3 + FastAPI**，业务覆盖 **行情、舆情、量化、交易、AI 研判**。列表浏览走 Influx / MySQL，长桥只用于交易台实时报价和下单；调度与长任务从 API 进程拆出，避免 Grok / 采集把 HTTP 打满。

本仓库 2026-07-23 首次公开，默认分支 `main`。贡献走功能分支 + Pull Request，禁止直接推 `main`。详见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## 🌟 核心功能一览

- 📈 **行情中心**：三市场热度与 Top50、全部股票（全市场分页）、智能选股（指标 + 舆情 + 开盘指数）、行情台、自选三栏、财经资讯、AI 研判。大盘指数每市场三条（美股标普/纳指/道琼斯，港股恒指/恒科/国企，A 股上证/创业板/科创板）。
- ⭐ **自选按账号隔离**：行情自选只走 `market_watchlist` + `user_id`；量化扫描池继续用 `quant_watchlist`，两套不混。分组先写在 `note`（逗号可多组）。
- 📰 **舆情分析**：中文资讯采集、大盘影响研判、分析历史；列表页不叠长桥实时价。macOS Widget 可通过 Token 拉取只读大盘聚合。
- 🧮 **量化研究**：因子、Alphalens 风格 IC/IR/分层收益、策略信号、扫描台账、策略档位与 8 族权重。
- 💹 **交易中心**：长桥账户 / 持仓 / 委托、盘口深度与分时、持仓叠实时价自算盈亏、纸面自动交易（默认不实盘下单）、风控规则与事件、通知中心。
- 🔐 **长桥按登录账户**：每人一行 App Key / Secret / Token；交易与实时报价用当前用户；jobs 无登录上下文时回退 admin。
- 🤖 **AI 研判**：单标的研判、批量扫描、需求沟通群（Grok 入 `llm` 队列，不堵 API）、模型管理。智能选股默认 Grok 4.6。
- 🧵 **任务拆分**：`sentiment-jobs` 只跑 APScheduler；market / quant / llm 三个消费组；交易实时单独进程。
- 🖥️ **桌面端（过渡）**：Electron 启动先配前端网关再登录，本机 Docker 与云上域名可切换。
- 📱 **Flutter 客户端**：`lib/` 四端共用。宽屏桌面登录后 WebView 打开网关 Web 控制台（与 Docker Web 同一份前端）；手机走原生五栏（舆情 / 选股 / 热度 / 持仓 / 我的）。Debug 默认本机 Docker（`127.0.0.1:12580`，Android 模拟器 `10.0.2.2:12580`）；Release 默认线上 `https://sfp.luapi.top`。
- 📡 **监控（可选）**：Prometheus + Grafana，后端 `/metrics`。

## 🚀 0826 V11 迭代更新日志（手机原生五栏、桌面 WebView 壳、实时持仓）

### 1. 📱 Flutter 手机：反重力五栏
- 底栏：**舆情 / 选股 / 热度 / 持仓 / 我的**。量化研究、需求沟通、网关探测改到「我的」。
- 智能选股：评分 / 立场 / 建议 / 摘要，点行进 K 线。
- 持仓：长桥现价自算涨跌与浮动盈亏，总资产港元 / 美元切换；底部抽屉极速下单（限价、仓位比例）。
- 个股详情对齐设计稿图 01：大字报价、指标格、周期、十档、AI 研判、买卖栏。
- 登录页复用网页赛博网格；macOS 沉浸式标题栏，控件避开红黄绿灯。

### 2. 🖥️ Flutter 桌面：登录后即 Web 控制台
- macOS / Windows 宽屏不再走 Flutter 精简页，`WebView` 打开网关 `/portal`，页面、路由、样式与 Docker Web 同一份。
- JWT 写入 `Admin-Token` Cookie；macOS 开发签名下 JWT 改存 SharedPreferences，避免反复弹钥匙串。
- Debug 默认本机 Docker；Release 默认线上 `https://sfp.luapi.top`。模拟器环回 `10.0.2.2` 不再被改写成线上地址。

### 3. 💹 行情指数与持仓实时价
- 大盘指数一次拉三市场各三条，始终返回最近有效报价，由客户端按当前市场筛选。缓存键 `market:index:quotes:v3`。
- 持仓接口叠长桥 `last` / `prevClose`（`AAPL.US` / `00700.HK` / `700` 等写法归一）。
- 新增 `GET /trade/quote/realtime`：批量 `QuoteContext.quote`，不走重量级 snapshot。

### 4. 🚪 Web 门户按菜单权限
- 门户六组卡片按当前用户 `getRouters` 过滤；系统 / 监控 / 工具 / 分析对无权限账号隐藏。
- `/trade/terminal` 与 `/market/terminal` 两条直达路由都保留。

---

## 🚀 0825 V10 迭代更新日志（交易台、北京时间、四端 Flutter 原生壳）

### 1. 💹 Web 交易台 / 行情台
- 自选下拉按分组；打开默认第一只标的。
- K 线按市场时段：盘中长桥实时（`TradeSessions.All`，美股含 4:00 ET 盘前）；日/周/月走 Influx；港/A 休市回当天日 K。
- 顶栏全市场代码搜索；交易台旁量化自动交易开关（无长桥密钥时灰显）。
- 单票仓位上限按净值百分比（默认 10%，夹 5%–30%）；同日已提交/成交的买单跳过。

### 2. ⏰ 北京时间
- 长桥 / Influx 的 UTC 时间戳展示转北京时间（`format_utc_as_beijing`）。
- **舆情 naive `pub_time` 仍按北京墙钟，不再 +8**（既有契约未改）。
- 会话判定继续用各市场本地时区（美股 ET / 港股 HKT / A 股 CST）。

### 3. 🔄 生产 → 本地同步
- `POST /open/sync/token` + `POST /open/sync/pull`：RSA-OAEP + AES-GCM 加密用户名密码换短期令牌，不再写死固定 token。
- 传输加密仅挂在 `/open/sync/*`。脚本：`scripts/sync_from_prod.py`。

### 4. 🖥️ Flutter
- macOS：交易台、盘前/夜盘时段、北京时间轴；本机已打 `智慧金融.app`。窗口 1440×900，最小 1100×700；ATS 允许本机/局域网 HTTP 网关。
- **当晚补回三端原生壳**（从清空前的工程还原并对齐今日 macOS）：
  - Android：明文 HTTP 网关（`network_security_config` + `usesCleartextTraffic`）、预测性返回；本机 debug/release APK 已编过。
  - iOS：ATS `NSAllowsLocalNetworking`、局域网用途说明、`ITSAppUsesNonExemptEncryption=false`；`--no-codesign` 已编出 `Runner.app`。
  - Windows：默认窗口 1440×900、最小 1100×700、标题「智慧金融分析平台」、主屏居中；NSIS 开始菜单/桌面快捷方式同名。本机不能交叉编译，CI `windows-latest` 出包。
- CI：`flutter.yml` 恢复 apk / ios / macos / windows 四 job；push 仍只跑 `main` / tag / PR，避免功能分支狂跑发邮件。

---

## 🚀 0824 V8 迭代更新日志（四端 Flutter 客户端、墨蓝设计系统、全量优化）

### 1. 📱 Flutter 四端工程地基（M0）与行情域（M1 先行）
- **单工程四平台**：`flutter_client/` 覆盖 iOS / Android / macOS / Windows；规划基线见 `docs/四端客户端规划.md`。Electron `desktop/` 过渡期继续服务，Flutter 桌面对齐后下线。
- **首启网关探测**：复刻桌面端语义——未配置网关强制进入配置页，探测健康接口通过才落盘并放行登录。填前端地址（本机默认 `http://127.0.0.1:12580`），业务 API 走 `{网关}/docker-api`；后端端口不能当网关。HTTPS 失败可手动改 http，绝不自动降级。
- **登录 / 注册 / 会话**：JWT 安全存储；macOS 钥匙串补齐 entitlements，修复 `errSecMissingEntitlement`。根 `.gitignore` 误吞的 Dart 源码树已补齐入库。
- **CI 矩阵**：`.github/workflows/flutter.yml` 分析 + 单测 + 四平台产物（apk / ipa / macos / windows）。
- **自适应壳**：手机底部 NavigationBar；桌面品牌侧栏（≥900 桌面壳，≥1200 展开）；工作台 / 行情 / 自选 / 我的，IndexedStack 保活。

### 2. 🎨 「墨蓝金融终端」设计系统
- **令牌集中**：`AppColors` / `AppDimens` / `AppNum` 为唯一取色与密度来源。品牌蓝 `#409EFF` 对齐 Web 端；涨红跌绿、平灰、警示琥珀；深色为一等公民，层次靠背景分层 + 1px 细描边。
- **共享组件**：`PageHeader`、`SectionCard`、`StatGrid`、`BrandMark`、`StatusDot`、`AuthScaffold`；登录 / 注册 / 网关共用左右分栏品牌面板。
- **数字排版**：报价与金额一律 tabular figures；详情页大价格走 `quoteDisplay`。
- **活规范**：调试构建访问 `/gallery` 一屏预览全部令牌与组件；壳层 golden（桌面 / 手机）纳入 `flutter test`。

### 3. 📈 客户端行情 / 自选 / K 线
- **行情 tab**：市场切换、盘中指数条、统计卡、热度摘要、Top50 列表，下拉刷新。
- **自选 tab**：概览卡 + 分组筛选 + 标的列表；宽屏左侧固定分组栏，窄屏顶部 chip。
- **全部股票**：工作台入口进入全市场分页，行点击进标的详情。
- **标的详情**：日 / 周 / 月 K 线 + 分时自绘。

### 4. 🔒 安全加固、依赖与容器
- 清除误提交的真实 admin 初始密码（代码 + git 历史已重写）。**在此前部署的环境请立即修改 admin 密码。**
- 监控栈与 jobs / backend 管理端口改绑 `127.0.0.1`。
- compose 显式透传 `DB_PASSWORD` / `REDIS_PASSWORD`，消除与 MySQL / Redis 初始化密码的双源漂移。
- fastapi 0.141 / starlette 1.3.1 / Pillow 12.3 / PyJWT 2.13；CI 新增 pip-audit 门禁 + 双镜像构建冒烟。
- 后端多阶段构建（体积约 -23%，运行时无编译链）；前端 `node:20` + `nginx-unprivileged`（容器内 8080）。

### 5. 🛠️ 可靠性、SQL 治理与架构拆分
- Redis 任务队列改为认领-确认语义（可见性超时回收、失败重试、死信队列）。
- Influx `latest_date` 渐进窗口替代十年全扫；IP 归属地 httpx 补超时；Excel 导入移入线程池。
- 28 个手工增量脚本纳入 `schema_version` 登记制（`scripts/sql_migrate.py`）。
- `get_scheduler`、`longbridge_service`、`transport_crypto_util` 拆为子包 + facade；公共层反向依赖业务模块的 import 全部倒置或下沉。
- 前端 Element Plus 按需引入（静态资产约 -23%）；transportCrypto 监控页拆分；Electron 网关取消静默降级 http、启用沙箱桥接白名单。
- 生产构建后左侧菜单消失已修复。

### 6. 📰 舆情 Widget、北京时间与工作台超时
- **只读 Widget API**：`GET /sentiment/widget/dashboard`，`X-Widget-Token` 鉴权（`SENTIMENT_WIDGET_TOKEN`，空则关闭）。文档见 `docs/sentiment-widget-api.md`。
- 舆情大盘 / 资讯 / 分析历史统一北京时间展示与落库；naive `pub_time` 按北京墙钟处理。
- `GET /dashboard/summary` 各段 5 秒超时，读模型缺失时返回空载荷提示而非回退长桥实时。

---

## 🚀 0823 V7 迭代更新日志（智能选股、收盘 K 线与全市场分页）

### 1. 🧠 全市场智能选股
- 侧栏入口。候选来自各市场 Top50 + 精选池，用日 K 因子打分，叠三市场舆情。
- **仅开盘市场带实时指数**，休市自动去掉指数仍可手动出单。
- 选股 AI 在 **AI 管理 → 模型管理** 配置：适用范围选 **行情中心 (market)**，默认 **Grok 4.6**（OpenRouter 编码 `x-ai/grok-4.6`，直连 xAI 填 `grok-4.6`）。未配行情模型时回退全局 / 助手。
- 入选标的全部走 AI 研判；单标的研判统一到 `StockPickService.analyze_symbol`。
- 限流重试，避免长调用后 ORM 过期写库失败。
- 手动「刷新情绪 / 生成选股单」；支持按日期浏览历史选股单。
- 定时在 **任务中心 → 自动分析任务** 改 cron（默认北京时间 15:50 / 16:50 / 05:50）。
- 增量 SQL：`sql/market-stock-pick.sql`。

### 2. ⏰ 三市场收盘拉日 K + 分时
- 容器 cron 为 UTC，对齐现有热度任务：A 股 15:25、港股 16:25、美股约 05:25 北京时间。
- 日 K 缺当日才拉；分时写入 Influx `minute_kline`（精选 + Top50）。

### 3. 📚 行情中心「全部股票」
- 美 / 港 / A 股全市场代码分页浏览，搜索、加自选、点入 K 线与详情。
- `GET /market/instrument/universe` 强制分页（默认 50、最大 200），当前页附带本地日 K 最新价。
- 增量 SQL：`sql/market-universe-menu.sql`。

### 4. 🧾 交易、需求沟通与 CI
- 自动交易按用户隔离；rebalance 卖出护栏。
- 需求沟通多 AI、次日模拟清单、飞书推送；冒烟修复 scope 列、飞书保存与重复模型校验。
- ruff ratchet 路径与新增文件告警清零。

---

## 🚀 0822 V6 迭代更新日志（自选隔离、行情综合化与全市场回填）

### 1. ⭐ 行情自选只走 `market_watchlist`
- 列表 / 新增 / 删除 / 概览 / 分析 / 回测 / 小时任务全部带当前 `user_id`，不再误走全局 `quant_watchlist`。
- 热度 Top50「已在自选」按当前用户判断。
- 自选页三栏：左分组（`note` 逗号分隔）+ 列表，中日 / 周 / 月 K 线，右报价 / 分组 / 备注 / 综合分析。

### 2. 🔑 长桥凭据按登录账户
- `GET/PUT /quant/longbridge/config` 与连通性测试只读写当前用户行。
- 请求级 `ContextVar` 注入凭据；jobs 无用户上下文时回退 `user_id=1`，再 env。
- 保存时掩码 `****` 不覆盖原密钥。增量 SQL：`sql/quant-longbridge-user.sql`。

### 3. 🧭 行情中心侧栏压平与视觉综合化
- 只留五个入口：市场热度、行情台、自选清单、财经资讯、AI 研判。
- 行情中心综合化 + 实时感 + 对标工作台视觉；舆情大盘叠加大盘指数条（盘中动态显示）。
- 资产四卡按券商凭据动态隐藏；工作台聚合 summary API。

### 4. 📥 全市场代码与慢速日 K 回填
- `scripts/sync_market_listings.py` / `scripts/sync_klines_slow.py`，限流慢拉，`logs/kline_sync.stop` 优雅退出。
- 舆情/全局模型 Base URL 在「AI 管理」配置（占位 `https://your-openai-compatible-endpoint/v1`），不要写死临时隧道主机。

### 5. ⚙️ 性能、安全与工具链
- 前端按需 echarts、manual chunks、请求去重。
- 后端批量 DB roundtrip、同步 IO 卸载、共享 quote builder。
- 密钥 / CORS / 传输错误 / 容器默认值加固。
- 可选 LLM 依赖拆分；ruff / eslint / prettier 门禁。

---

## 🚀 0821 V5 迭代更新日志（热度看板、API 与长任务拆开、长桥熔断）

### 1. 🔥 市场热度与 Top50
- 美 / 港 / A 股收盘采集指数涨跌、成交额、涨跌家数，写入 `market_heat_daily` 与 `market_top50_snapshot`。
- 市值过滤、权重走 `sys_config`，任务进 `sentiment-jobs` 队列。

### 2. 🧵 API 与长任务隔离
- APScheduler 只在 `sentiment-jobs`；market / quant / llm 三个消费组分开。
- 交易实时单独进程，禁止和 LLM / 采集共进程。
- 行情台报价读 Redis / SWR；全市场 Influx 扫描进 jobs。
- 需求沟通「发送 / 总结」入 `llm` 队列立即返回 `jobId`，Grok 不再堵 API worker。

### 3. 📚 浏览行情只走库，长桥留给交易台
- 自选概览、行情台、标的详情的列表报价不再 overlay 长桥实时价 / static_info。
- 无效 Token 不再把列表页打挂。交易台分钟 / 分时仍走长桥，失败软降级。

### 4. 🛡️ 熔断与队列
- 长桥 401004 / 超时拉共享熔断器，后续任务路径不再打券商。
- 长任务入 Redis，消费失败可 inline 回退。异步长桥调用限流。

### 5. 🧮 量化、风控与桌面
- Alphalens 风格截面 Spearman IC / IR / 五分位收益。
- 自选小时综合（技术 + 长桥资讯 + 舆情），建议 1/5 日前瞻回测。
- 风险事件审批流；Alpha101 / 158 快照与 ReadModel 定时任务。
- Electron 每次启动先开网关配置窗。

---

## 🚀 0820 V4 迭代更新日志（交易台报价板、门户、登录皮肤、纸面自动交易）

### 1. 💹 交易台
- 当前标的深度、逐笔、周期 K 线；K 线（或分时）叠在盘口与成交明细上方。
- 空 K 线不再留 360px 白块；持仓跳 `/trade/trading?symbol=` 跟路由。

### 2. 🚪 门户与登录
- 门户 16 个入口收成六组卡片，去掉「若依官网」菜单种子。
- 登录浅色 / 深色与门户、系统 chrome 同一套 VueUse 键，刷新不丢。

### 3. 📉 行情与空状态
- 真源 K 线 seeder（新浪 / 腾讯 + 降级，带熔断），禁止合成 OHLCV。
- 看板批量报价；TradingView 港股代码候选。
- 资讯 / 舆情 429 / Druid / 未配券商账户的空状态。

### 4. 🤖 自动交易（默认纸面）
- 扫描默认不提交订单：纸面保护 + 长桥交易开关只在服务端。
- 长桥调用线程卸载 + 短 Redis 缓存；K 线默认不再拉十年窗口。
- Prometheus 指标、`docker-compose.monitor.yml`、AI 工作台 One-Shot / 投研顾问。

---

## 🚀 0723 V1 首次公开发布

独立公开的 RuoYi 行情 / 舆情 / 量化 / 交易 / AI 工作台，配置只留 `.env.*.example`，贡献要求 PR 进 `main`。

---

## 🛠 快速启动与部署指南

- **方案 1：Docker Compose 一键启动（推荐）**
  ```bash
  cp ruoyi-fastapi-backend/.env.dockersentiment.example \
     ruoyi-fastapi-backend/.env.dockersentiment
  cp ruoyi-fastapi-frontend/.env.docker.example \
     ruoyi-fastapi-frontend/.env.docker

  docker compose -f docker-compose.sentiment.yml up -d --build
  ```

  | 服务 | 地址 |
  |------|------|
  | 前端 / 网关 | http://127.0.0.1:12580 |
  | 平台 API | http://127.0.0.1:19099（OpenAPI `/docs`） |
  | jobs 调度 | http://127.0.0.1:19098/health |
  | MySQL | 13306 |
  | Redis | 16379 |
  | InfluxDB | 18086 |

  **禁止 `compose down` 整栈。** 更新单个服务：

  ```bash
  docker compose -f docker-compose.sentiment.yml up -d --no-deps --build sentiment-backend sentiment-frontend
  ```

  已有库增量 SQL 见 [docs/DEPLOY.md](./docs/DEPLOY.md)。补全市场代码与日 K（本机 Docker 默认口，限流慢拉）：

  ```bash
  ruoyi-fastapi-backend/.venv/bin/python scripts/sync_market_listings.py
  ruoyi-fastapi-backend/.venv/bin/python -u scripts/sync_klines_slow.py
  touch logs/kline_sync.stop   # 下一只标的前退出
  ```

- **方案 2：Electron 桌面端（过渡）**
  ```bash
  cd desktop && npm install && npm start
  ```
  先填前端网关再登录：本机 `http://127.0.0.1:12580`，云上填已部署域名。不要填后端 `19099`。

- **方案 3：Flutter 四端客户端**
  ```bash
  cd flutter_client
  flutter pub get
  flutter run -d macos     # 或 windows / ios / android
  ```
  首启默认连线上网关 `https://sfp.luapi.top`。本机 Docker 在网关页改 `http://127.0.0.1:12580`（Android 模拟器 `http://10.0.2.2:12580`）。详细说明见 `flutter_client/README.md`。

- **方案 4：检查与监控（可选）**
  ```bash
  cd ruoyi-fastapi-backend && uv run pytest tests/ -q
  npm install && npx playwright install chromium && npm run e2e:web
  docker compose -f docker-compose.monitor.yml up -d
  ```
  Prometheus 19090 · Grafana 13000。

## 📦 项目技术栈与依赖清单

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
├── ruoyi-fastapi-app/             # 移动端 H5 / 小程序基线（双轨保留）
├── flutter_client/                # 四端 Flutter（iOS / Android / macOS / Windows）
└── desktop/                       # Electron（过渡）
```

- **Web 前端**：Vue 3 · Element Plus · Vite · ECharts · Pinia
- **后端**：Python ≥3.10 · FastAPI · SQLAlchemy async · JWT
- **数据**：MySQL 8（业务）· Redis（会话 / 队列 / 缓存）· InfluxDB 2.x（K 线）
- **客户端**：Flutter 3.13+（Riverpod · Dio · go_router · flutter_secure_storage）；Electron 34（过渡）
- **券商**：Longbridge OpenAPI（可选）

## 🛡️ 隐私与数据安全说明

- 仓库只有 `.env.*.example`，不含生产密钥。
- 不要提交 `DB_PASSWORD` / `JWT_SECRET` / `INFLUX_TOKEN` / 长桥 Token / RSA 私钥 / `SENTIMENT_WIDGET_TOKEN`。
- 长桥交易开关与纸面保护在服务端，前端关不掉实盘拦截。
- Widget 接口空 token 即关闭；管理端口默认只绑本机回环。

## 💻 常用维护命令

```bash
# 业务栈
docker compose -f docker-compose.sentiment.yml up -d --build
docker compose -f docker-compose.sentiment.yml logs -f sentiment-backend

# 增量 SQL
python3 scripts/sql_migrate.py apply --dry-run
python3 scripts/sql_migrate.py status

# 一键部署并冒烟
./scripts/deploy_and_verify.sh

# 监控
docker compose -f docker-compose.monitor.yml up -d
```

## 致谢

- 管理端底座：[RuoYi-Vue3-FastAPI](https://github.com/insistence/RuoYi-Vue3-FastAPI)
- 前端参考：[RuoYi-Vue3](https://github.com/yangzongzhuan/RuoYi-Vue3)

## License

MIT（以本仓库 `LICENSE` 为准；上游组件遵循其各自许可证）
