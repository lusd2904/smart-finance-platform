# SFP 本地 AI 改版 backlog（2026-09-09）

> **受众**：Ulisses 本机本地 AI（pull main 后本地编辑再提 PR）。
> **用途**：前端 `apps/frontend/web-portal` 对照设计资产改版；**不走 Cloud Agent**。
> **标注根目录**：`/workspace/sfp-annotated/`

## 硬约束

| 项 | 要求 |
|----|------|
| Cloud Agent | **禁止**再拉起新的 Cloud Agent |
| 仓库 | `smart-finance-platform` · 基于 **main** |
| 前端路径 | **`apps/frontend/web-portal`**（唯一目标） |
| 标注 | `/workspace/sfp-annotated/` 的 annotate / specs / html / ref-live / gen_*.py |
| 禁止 | 生产 dist；`ruoyi-fastapi-frontend`；新建 Cloud Agent；容器整栈 recreate |
| 切流 | preview / gray / 生产 **一律等 Ulisses** |

---

## 0. 本机开干

本机流程：同步仓库 main 分支 → 进入 apps/frontend/web-portal → 安装 Node 依赖 → 配置环境后启动开发服务器（端口 5180）。

必配环境：

- 关闭 stubs：VITE_USE_STUBS=false（验收必须走真接口）
- 代理目标：VITE_PROXY_TARGET 指向线上或本机 live gateway
- 开发端口：VITE_DEV_PORT=5180

验收时 glass-dark 与 glass-light 双侧对照 annotate 与 specs。接口 401 或空表先查第 4 节，勿用假数据充数。

---

## 1. 设计资产表（annotate + specs）

图例：DONE = dark/light 标注图 + specs 齐全；PRIMARY = 默认落地（禁止回退）；MISSING = 缺图或缺 spec。

### P1 行情（market）— 全部有 annotate + specs

| 路由 | 标题 | 资产 | PRIMARY / 备注 |
|------|------|------|----------------|
| /market/board | 行情看板 | DONE | KPI + 多市场摘要 |
| /market/stocks | 标的浏览 | DONE | 列表筛选对齐 live |
| /market/heat | 市场热度 | DONE | **PRIMARY=单市场深潜**（A/HK/US + Top50）；三列对照仅 secondary |
| /market/watchlist | 自选清单 | DONE | **PRIMARY=三栏**（左列表/中K/右详情）；扫描表仅 secondary |
| /market/flow | 资金流向 | DONE | |
| /market/review | 复盘 | DONE | |
| /market/recommendations | 精选推荐 | DONE | |
| /market/finance-news | 财经资讯 | DONE | |

ref-live 实机图（非 annotate）：ref-live/live-board(.png|-desktop.png)、live-heat、live-watchlist；另有 live-refs/live-market-board.png、live-market-heat.png。

生成器：gen_market_pages.py；heat/watchlist 另见 gen_heat_v2.py、gen_watchlist_v2.py。

### P2 交易 — 全部 DONE

positions / orders / risk / notifications（annotate + specs/trade-*.md；gen_trade_pages.py）。

### P3 量化 — 全部 DONE

factor / strategy / longbridge（密钥须脱敏；gen_quant_pages.py）。

### P4 舆情 — 全部 DONE

dashboard / news / analysis（情绪分 0–100；gen_sentiment_pages.py）。

### 缺口

| 路由 | 状态 |
|------|------|
| /analysis/jobs | **MISSING** annotate 与 spec；`menus.js` **待补侧栏**（现仅工作台快捷有入口；勿盲扩 UI） |
| /ai/model | **MISSING** png/spec（仅有 gen_ai_pages.py 草稿） |
| /ai/chat | **MISSING** png/spec（同上） |
| /system/user | **MISSING** |
| /system/role | **MISSING** |
| /system/menu | **MISSING** |

P5/P6：前端只做薄 CRUD / 薄壳，等设计包，禁止按想象加复杂工作台。

---

## 2. 前端怎么改（逐页 / 全局）

### 2.0 全局验收清单

| 检查项 | 标准 |
|--------|------|
| 数字等宽 | font-variant-numeric: tabular-nums |
| 涨跌色 | **涨红跌绿**（dark #f87171/#34d399；light #dc2626/#059669；零为中性） |
| 强调色 | CSS 变量 **--accent**（dark #6366f1 / light #4f46e5） |
| 玻璃 | glass-panel：blur + 半透明 + 细边框；对齐 experience.scss / theme.scss |
| Shell | 现有 Sidebar + Header（智慧金融）；禁止另起 ruoyi 白底壳 |
| Badge | 页顶文案对齐对应 spec |
| 主题 | 仅 glass-dark / glass-light |
| Stub | 验收时 VITE_USE_STUBS=false |

### 2.1 heat / watchlist PRIMARY（禁止回退）

**/market/heat — PRIMARY = 单市场深潜**

- 默认：市场 tab（A股/港股/美股）+ 指数 mini 卡 + KPI×4 + 热度摘要与近5日趋势 + Top50。
- 禁止把三列 US/HK/CN 对照做成默认落地（仅可 secondary）。
- 菜单文案对齐 live「市场热度」；勿因旧文案「三市场热度」改回三列默认。
- 对照：annotate-market-heat-{dark,light}.png、specs/market-heat.md、ref-live/live-heat*。

**/market/watchlist — PRIMARY = 三栏**

- 默认：左自选列表 + 中 K 线（日/周/月）+ 右详情/立场；KPI=数量/看多/看空/中性。
- 操作：新增自选、立即分析全部、建议回测、刷新。
- 禁止把旧扫描大表做成默认落地（仅 secondary）。
- 相关热力可占位（完整 Pearson 依赖 Influx 批量）。
- 对照：annotate-market-watchlist-{dark,light}.png、specs/market-watchlist.md、ref-live/live-watchlist*。

### 2.2 其余 P1

按各自 specs/market-*.md + annotate 对齐。优先 board/stocks/heat/watchlist 与 live 一致；其余做玻璃化与列对齐。

### 2.3 analysis/jobs 与 menus.js

路由 meta 已有「自动分析」。**`menus.js` 的 `menuTree` 还没挂 `/analysis/jobs`**（只有工作台快捷入口）——待补侧栏，或文档写明「仅工作台入口」。缺设计包：可留入口 + 极简空态，勿发明复杂调度 UI。改菜单只动 apps/frontend/web-portal/src/config/menus.js（及 router），path 保持稳定。

### 2.4 P2 + Longbridge 401 友好

对齐 positions/orders/risk/notifications。长桥凭证失效、熔断、401（含 401004）：须友好 banner（引导去量化·长桥配置），禁止白屏或仅 raw 报错；可展示缓存数据避免误判空仓。

### 2.5 P3 longbridge 脱敏

secret/token/app_key 掩码（星号 + 末四位或长度提示）。复制、导出、日志、toast、测试连接错误均禁止明文。

### 2.6 P4 舆情

对齐 annotate；情绪分 0–100。不新增 RSS 源管理入口（见 §4）；旧 RSS 残骸隐藏或只读。

### 2.7 P5 / P6 薄 CRUD

/ai/model、/ai/chat：gen_ai_pages.py 可预览，但 png/spec 未入库 → 薄壳即可，禁止盲扩。system user/role/menu：标准表格 CRUD，等设计再视觉升级。

---

## 3. 设计 backlog（待补标注）

优先级（高→低）：

1. **P5 AI**：补 /ai/model、/ai/chat 的 dark/light annotate 与 specs/ai-*.md（可从 gen_ai_pages.py 出稿后人工修订）。
2. **P6 系统**：/system/user、/system/role、/system/menu 全套 annotate + spec。
3. **/analysis/jobs**：补 annotate + spec（任务列表、启用开关、上次运行、手动触发、日志抽屉等需与后端字段对齐后再画）。

截图规范：Chrome headless 视口 **1440×900**（window-size 或 Playwright viewport 同尺寸）。每页至少 glass-dark + glass-light 各一张；命名 annotate-area-page-{dark|light}.png；同步 html/ 与 specs/ 后回填 §1。

---

## 4. 后端 / 运维（可执行明细 · 本地 AI）

本地 AI **以前端为主**；若顺带碰后端，严格按下列做。影响联调的写进 PR 说明。非 Ulisses 点名 **禁止** 生产编排 recreate。

### 4.1 前端联调需知（只读依赖）

| 项 | 说明 | 前端动作 |
|----|------|----------|
| Longbridge token | `quant_longbridge_config` access token 过期 → 交易/行情 **401004**（admin / lustone / 乐文 账号都要刷） | 401 友好 banner → 引导 `/quant/longbridge`；可展示缓存仓位，禁止白屏 |
| preview / gray | `#100` web-portal 已合 main，**产线仍旧 ruoyi dist** | 切流 **等 Ulisses**；勿自改 nginx / 生产静态 |
| sentiment-trade-api mem | 现网曾顶满约 **510/512MiB** + swap 紧（#99 WS 重连放大） | OOM/502 记日志；前端降级提示，勿假装下单成功 |
| job 109 `watchlist_analyze` | Influx **401**（token / org / bucket）→ 自选分析失败 | 「立即分析全部」展示可读错误，勿假造成功 |
| PR **#103** `sfp-notify-worker` | 已合 main：failover / max_tokens / reclaim / analyze 默认 | notifications / 舆情大盘区分「无数据」vs「worker 未滚动到新镜像」 |
| 舆情采集 | Go `sentiment_collect` **无 RSS**；新闻靠 **X ingest**（`x_monitor`）+ 偶发补源；`auto_analyze=1`，主模型 xixiapi `claude-sonnet-5` | 不新增 RSS 配置入口；dashboard 读 `/prod-api/sentiment/*` |

### 4.2 后端本机改法（若 Ulisses 让本地 AI 改 Go）

仓库：`smart-finance-platform` · `main`（`#100/#102/#103` 已合）。**禁止** Cloud Agent；**禁止** `docker compose down` / 删卷 / 动 `grok2api` / `:8000`。

1. **Longbridge 401004（等人）**  
   - 路径：管理端「量化 · 长桥配置」或表 `quant_longbridge_config`（user 对应 admin/lustone/乐文）。  
   - 动作：用 Longbridge 开放平台刷新 **access_token** 写回（密钥脱敏，勿提交明文到 git）。  
   - 验收：`sentiment-trade-api` / data-api 测连或拉仓位不再 401004；前端交易页无熔断 banner。

2. **`sentiment-trade-api` 内存**  
   - 查 slim compose 里该服务 `mem_limit` / `deploy.resources`（曾见 ~512MiB 顶满）。  
   - 优先：复核 #99 后 Longbridge **Quote WS** 重连是否泄漏连接（`trade-exec` quote pool）。  
   - 次选：Ulisses 批准后 **仅**对该服务抬 limit（`--no-deps`），禁止整栈 recreate。  
   - 验收：`docker stats` 该容器稳定 < limit 的 80%；WS 重连风暴消失。

3. **job 109 Influx 401**  
   - 核对 `sfp-notify-worker` / 相关 worker 的 `INFLUX_URL`、`INFLUX_TOKEN`、`INFLUX_ORG`、`INFLUX_BUCKET` 与 `sentiment-influxdb` 一致。  
   - 只改 env / secret 挂载，**勿**删 Influx 数据卷。  
   - 验收：手动或 cron 跑 `watchlist_analyze` ticket → `done`；`market_watchlist_analysis` 有新行；无 dead-letter Influx 401。

4. **#103 现网是否已滚动 `sfp-notify-worker`**  
   - 代码已在 main；现网镜像可能仍是合入前。  
   - Ulisses 点名后：只 build/restart **`sfp-notify-worker`**（`--no-deps`），不要 rename、不要动 mysql/redis。  
   - 验收：坏模型 401/402 会换下一模型；`max_tokens` 有上限；`processing:llm` 孤儿可 reclaim；job100 仍 `analyze=true`。

5. **`sentiment_collect` 无 RSS（产品债）**  
   - 现状：`RunSentimentCollect` 明确「RSS 未迁移」，依赖 X-monitor ingest + `analyze`。  
   - 本地若做 RSS：新 Go 采集器写入 `sentiment_news`，保持 `analyzed='0'`，勿打断 X 路径。  
   - 未授权前：前端/配置页不要加 RSS UI。

### 4.3 运维红线

- 禁止整栈 `down` / `rm` mysql·redis·influx 卷  
- 禁止未批准 recreate `sentiment-mysql` / `sfp-notify-worker` / redis  
- 滚动业务容器须 Ulisses 确认且 `--no-deps`  
- 勿动 `grok2api` / 宿主机 `:8000`

---

## 5. PR 验收清单

### 流程

- [ ] 基于最新 main；未用 Cloud Agent 推本 PR
- [ ] 改动限 apps/frontend/web-portal；未改 ruoyi-fastapi-frontend
- [ ] 未提交生产 dist；无密钥明文与生产秘密文件

### 视觉 / UX

- [ ] 涉及页 dark+light 对照 annotate
- [ ] tabular-nums、涨红跌绿、--accent、glass-panel 通过
- [ ] heat 默认仍为单市场深潜（未回退三列）
- [ ] watchlist 默认仍为三栏（未回退扫描表）
- [ ] 长桥/交易 401 有友好提示；longbridge 密钥掩码

### 联调

- [ ] VITE_USE_STUBS=false，代理指向约定网关
- [ ] 开发服 5180 可登录并打开改动路由
- [ ] P2/P3/P4 错误可恢复无白屏
- [ ] P5/P6/jobs 若薄壳：PR 注明「等设计，未盲扩」

### 文案与切流

- [ ] menus.js 与 live/spec 一致（热度标题尤甚）；`/analysis/jobs` 侧栏已补或文档已说明
- [ ] badge 与 spec 一致
- [ ] PR 注明 preview/gray/生产切流等 Ulisses；未合并前不要求滚动容器

---

## 6. 本文件

| 项 | 值 |
|----|-----|
| 文件名 | LOCAL-AI-BACKLOG-20260909.md |
| 路径 | /workspace/sfp-annotated/LOCAL-AI-BACKLOG-20260909.md |
| 日期 | 2026-09-09（Asia/Shanghai） |
| 维护 | 本地 AI 改版单一事实来源；设计包更新后同步 §1 / §3 |
| 恢复 | 2026-09-09 完整版回写（含 §4 后端明细 + menus 待补侧栏） |

### 附录 A — 资产速查

/workspace/sfp-annotated/ 含 annotate-market|trade|quant|sentiment-*.png、specs/*.md、html/*.html、ref-live/、live-refs/、各 gen_*.py（含 gen_ai_pages.py 草稿）、以及本文件。

### 附录 B — PRIMARY 备忘

- Heat PRIMARY：单市场深潜 + Top50，不是三市场并排。
- Watchlist PRIMARY：左列表 / 中 K / 右详情，不是扫描大表。
- 切流等 Ulisses；本轮禁止新 Cloud Agent。

---

*End of LOCAL-AI-BACKLOG-20260909*
