# Smart Finance Platform · 智慧金融分析平台

基于 **RuoYi-Vue3 + FastAPI** 的一体化智能金融平台，覆盖 **行情 · 舆情 · 量化 · 交易 · AI 研判**。

> 本仓库为独立公开项目，仅发布 `smart-finance-platform` 代码。  
> **贡献请走功能分支 + Pull Request，禁止直接推送到 `main`。** 详见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

<p align="center">
  <img alt="python" src="https://img.shields.io/badge/Python-≥3.10-blue">
  <img alt="node" src="https://img.shields.io/badge/Node-≥18-blue">
  <img alt="vue" src="https://img.shields.io/badge/Vue-3-brightgreen">
  <img alt="fastapi" src="https://img.shields.io/badge/FastAPI-async-009688">
  <img alt="influx" src="https://img.shields.io/badge/InfluxDB-2.x-purple">
  <img alt="mysql" src="https://img.shields.io/badge/MySQL-8-orange">
  <img alt="license" src="https://img.shields.io/badge/License-MIT-lightgrey">
</p>

---

## 平台简介

Smart Finance Platform 在 RuoYi 权限体系之上，扩展了面向二级市场研究与交易辅助的业务子系统：

| 子系统 | 能力概要 |
|--------|----------|
| **行情中心** | InfluxDB 主路径 K 线 / 指标 / 标的池 / 分市场看板 / 历史覆盖率 / 高级图表 |
| **舆情分析** | 财经资讯、情感分析、研报摘要、配置调度 |
| **量化研究** | 因子、策略信号、自选池、扫描台账、策略配置档位 |
| **交易中心** | 长桥账户/持仓/委托、交易台、回测、风控规则与事件、通知中心 |
| **AI 研判** | 单标的研判、批量扫描任务、AI 交易台账、模型管理 |
| **系统底座** | 用户 / 角色 / 菜单 / 字典 / 定时任务 / 监控 / 代码生成 |

技术栈：

- **前端**：Vue3 · Element Plus · Vite · ECharts · Pinia
- **后端**：FastAPI · SQLAlchemy(async) · OAuth2/JWT · APScheduler
- **数据**：MySQL（业务）· Redis（缓存/会话）· InfluxDB（行情时序）
- **券商**：Longbridge OpenAPI（可选，交易实盘/模拟）

---

## 功能亮点

### 行情与研究
- 目标标的 **Influx 历史覆盖率检测**（HistoryCoverage）
- **高级图表**工作区：K 线 + MA5/20/60 + 成交量联动缩放
- 多市场（US / HK / CN）标的与看板
- 财经资讯站内阅读，减少外跳

### 量化与策略
- 策略信号扫描与历史台账
- **策略配置档位**（保守 / 均衡 / 进取）：买卖阈值与因子权重可持久化

### 交易与风控
- 交易台：报价 · 下单 · 持仓快照 · 今日/历史委托
- **风控管理**：规则 CRUD、一键扫描、事件落库
- 通知中心：内存通知 + 持久化通知合并展示

### AI
- 单标的深度研判（支撑/压力/建议/风险）
- **批量 AI 扫描** + 批次历史明细
- 模型与对话能力继承自 RuoYi-AI 模块

### 体验
- 全局深色主题与门户入口（Cyber / Glass 风格）
- Docker 一键编排（前端 / 后端 / MySQL / Redis / InfluxDB）

---

## 目录结构

```text
smart-finance-platform/
├── docker-compose.sentiment.yml   # 推荐：完整业务栈编排
├── docker-compose.my.yml          # 官方 MySQL 示例
├── docker-compose.pg.yml          # 官方 PostgreSQL 示例
├── docs/                          # 迁移与设计说明
├── scripts/page_smoke.mjs         # 全菜单页面冒烟（Playwright）
├── ruoyi-fastapi-backend/         # FastAPI 后端
│   ├── module_market/             # 行情
│   ├── module_sentiment/          # 舆情
│   ├── module_quant/              # 量化 + 长桥
│   ├── module_trade/              # 交易 / 风控 / 回测 / 批量 AI
│   └── sql/                       # 菜单与业务 SQL
├── ruoyi-fastapi-frontend/        # Vue3 管理端
│   └── src/views/{market,quant,trade,sentiment,portal}/
├── ruoyi-fastapi-app/             # 移动端（RuoYi-App 基线）
└── desktop/                       # Electron 桌面端（先配网关再登录）
```

---

## 快速开始

### 1. 准备环境变量（不要提交真实密钥）

```bash
# 后端
cp ruoyi-fastapi-backend/.env.dockersentiment.example \
   ruoyi-fastapi-backend/.env.dockersentiment

# 前端
cp ruoyi-fastapi-frontend/.env.docker.example \
   ruoyi-fastapi-frontend/.env.docker
```

按需修改 MySQL / Redis / InfluxDB / JWT / 长桥凭证等。

### 2. Docker 启动（推荐）

```bash
docker compose -f docker-compose.sentiment.yml up -d --build
```

默认端口：

| 服务 | 端口 |
|------|------|
| 前端 | http://127.0.0.1:12580 |
| 后端 | http://127.0.0.1:19099 |
| MySQL | 13306 |
| Redis | 16379 |
| InfluxDB | 18086 |

默认账号（首次初始化后）：`admin` / `admin123`（请及时修改）。

### 3. 菜单 SQL（若库为空）

后端 `sql/` 下提供：

- `sentiment-menu.sql` / `market-menu.sql` / `quant-menu.sql`
- `full-feature-menu.sql` / `deep-feature-menu.sql`
- `risk-alpha-routes-menu.sql`（`/trade/risk-review`、`/quant/alpha-snapshot`）

可按需导入以挂载业务菜单。

### 4. 页面冒烟（可选）

```bash
npm install
npm run smoke:pages
```

### 5. 桌面端（本机 / 云上网关）

```bash
cd desktop
npm install
npm start
```

启动后先填写前端网关再登录：本机 Docker 为 `http://127.0.0.1:12580`，云上填已部署域名。不要填后端 `19099`。详见 [desktop/README.md](./desktop/README.md)。

---

## 主要业务 API（节选）

| 前缀 | 说明 |
|------|------|
| `/market/*` | K 线、指标、标的、AI 研判、资讯 |
| `/trade/account` `positions` `orders` | 长桥账户与委托 |
| `/trade/coverage` | 行情历史覆盖 |
| `/trade/strategy-profiles` | 策略配置档位 |
| `/trade/risk/*` | 风控规则 / 事件 / 扫描 |
| `/trade/ai/batch*` | 批量 AI 任务 |
| `/trade/notifications` | 通知（持久化 + 运行时） |

完整文档：启动后访问 `http://127.0.0.1:19099/docs`

---

## 贡献与分支策略

- 默认分支：`main`（受保护）
- **禁止直接 push `main`**（含 force-push）
- 请从 `main` 拉取功能分支：`feature/*` · `fix/*` · `docs/*`
- 通过 **Pull Request** 合并

详见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

---

## 安全说明

- 仓库内仅提供 `.env.*.example` 模板，**不包含真实生产密钥**
- 请勿将 `DB_PASSWORD` / `JWT_SECRET` / `INFLUX_TOKEN` / 长桥 Token / RSA 私钥提交到 Git
- 公开演示环境请使用独立弱权限账号与可轮换密钥

---

## 致谢与基线

- 管理端底座：[RuoYi-Vue3-FastAPI](https://github.com/insistence/RuoYi-Vue3-FastAPI)
- 前端参考：[RuoYi-Vue3](https://github.com/yangzongzhuan/RuoYi-Vue3)
- 行情/交易能力参考 Longbridge 开放平台生态

---

## License

MIT（以本仓库 `LICENSE` 为准；上游组件请遵循其各自许可证）
