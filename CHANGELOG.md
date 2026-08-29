# 更新日志 (Changelog)

所有项目的重要更改都将记录在此文件中。


## [Unreleased]

### 📱 手机行情对照券商 App
- 底栏改为 **自选 / 行情 / 选股 / 持仓 / 我的**（舆情进「我的」）
- 行情、自选、选股去掉圆角卡片和分段按钮，改成下划线档 + 密排报价行（最新价 + 涨跌幅色块）
- 个股详情盘口 / AI / 资讯不再套卡片；大字现价旁同时给出涨跌额和涨跌幅

### 🎯 量化策略按登录账户绑定
- 每个账户可选一个生效档位（保守 / 均衡 / 进取），写入 `plat_user_strategy_bind`；权重覆盖仍是本账户自己的
- 定时策略运行、自动交易扫描、次日清单、因子计算、回测默认用该账户绑定档；页面显式选档仍可单次覆盖
- 策略历史 / 扫描台账只看当前账户；未指定用户不再把所有自选混在一起跑
- 策略配置页「设为生效」；Vue / Flutter 自动交易与次日清单不再写死 balanced
- 增量 SQL：`ruoyi-fastapi-backend/sql/user-strategy-bind.sql`（`python3 scripts/sql_migrate.py apply`）

### ⚡ 实时价短路与批量路径
- 行情 hub 已覆盖全部订阅标的时，`get_quotes` 不再打 Redis / 长桥 / 腾讯
- 自选 overview 先填实时价；热度报价改走同一 LiveQuotes 路径
- 自动交易一批拉实时价；重型 snapshot 有 hub 价则跳过 `ctx.quote`
- 因子日扫快照与 Alpha 明细改为批量 upsert / delete+insert
- 交易台用 quotes WS 补最后一根；看板/热度订阅 TopN，REST 拉长到 60s
- Flutter 手机指数条优先行情 WS；通知未读 5s / 已读 30s 轮询

### 📡 实时价铺开 + 资讯按标的过滤
- Vue K 线 / 标的详情 / 持仓订阅现有行情 WS，最后一根和现价随 LIVE 更新；委托/持仓空表有提示
- Flutter 终端、手机自选、自选 tab 发送 `{type:subscribe}` 并吃 `channel=quotes`；个股详情显示 LIVE 价和相关资讯
- 财经简报支持 `?symbol=` 过滤

### 📡 长桥订阅进行情 WS + 标的绑定新闻
- 行情 WS `{type:subscribe}` 把标的并入进程内 `QuoteContext.subscribe`；推送覆盖内存最新价，腾讯仍补缺口；有推送时提前唤醒 quotes 通道
- 标的资讯（`type=news`）叠加财经简报 / 舆情里提到该代码或名称的条目；简报列表带 `symbols`

### 🔐 通知 / 风控 / 回测按账号隔离
- `plat_notification` / `plat_risk_event` / `plat_backtest_run` 增加 `user_id`；列表、已读、复核、扫描只看当前登录账户，缺 user 时空列表
- 止损监控、自选分析通知、队列 `user_notice` 写入时带所属用户；别人的信号不会再被扫进本账户风控
- 回测信号改走现有 8 族因子 + 策略档位阈值（`factor-8family:{profile}`），不再用 MA5/MA20 金叉

### 🛡 手工下单护栏与紧急停机
- `POST /trade/order` 买入走与自动交易相同的日内名义本金 / 单票仓位 / 总敞口 / 可用现金检查；卖出校验可用持仓；拦截不打长桥
- `GET/PUT /trade/halt` 紧急停机：拦住手工单、自动扫描、次日清单；撤单不受影响
- 策略配置页与手机「我的」可开停机和自动交易；手机持仓当日委托可撤在途单

### 🧭 平台测评后补齐（对照 KLineChart / OpenBB 日历 / QuantStats）
- 行情中心「资金与日历」：A 股板块资金 treemap、涨停池、龙虎榜（东财公开接口）+ Nasdaq 宏观/财报日历；失败空列表不 502
- 自选清单「相关热力」：当前账号自选日收益 Pearson 矩阵（Influx 日 K，最多 16 只）
- 风控页组合指标：Sharpe / Sortino / 最大回撤 / VaR95 / CVaR（持仓加权，不引入 QuantStats 依赖）
- 高级图表改 KLineChart（Apache-2.0）：趋势线 / 水平线 / 射线 / 矩形 / 斐波那契，最后一根仍走行情 WS
- 顶栏菜单搜索支持 ⌘K / Ctrl+K（Bloomberg 命令栏习惯）

### ⚡ 本轮（GitHub 对照后的剩余项）
- 盘中个股优先长桥实时价，腾讯只补缺口/收盘；因子日扫按市场 `query_klines_many` 再内存计算
- 策略/自动交易用户池改读 `market_watchlist`；任务进度 `WS /ws/jobs`（platform），行情 WS 核 Redis 会话
- 委托/通知/任务自适应轮询；交易台收盘拉长间隔；高级图表订阅最新价并补最后一根
- nginx gzip；DEPLOY Redis 512mb；`sfp-backup` 日备循环

### 🛠 备份与 Redis 文档
- 自动备份循环 `sfp-backup` / `scripts/backup_loop.sh`：启动即备份，随后每 86400s；`SKIP_CD=1` 供容器内执行
- `docs/DEPLOY.md` Redis `maxmemory` 与 compose 对齐 512mb；备份只走 `bash scripts/backup_data.sh` 与上述循环
- 量化读写已走 `market_watchlist`，旧表 `quant_watchlist` 保留只读历史（不 DROP）

### 📡 行情推送（对照 Open-Terminal / Gloomberg）
- 一条行情 WS：登录顶栏共用连接；自选/交易台 `{type:subscribe}` 后推个股最新价（腾讯批量，Redis 5s）
- 个股价走 `channel=quotes`，不用 `data.items`，避免 Flutter 把股票当成指数
- 自选页不再 8 秒打 overview；看板/热度 30 秒读 Redis 缓存
- 分析任务忙时 3 秒、空闲 30 秒轮询；`pollMarketJob` 指数退避
- 财经资讯基准指数一次 `query_klines_many`

### ✅ 全量测试（2026-08-28）
- 后端产品测试 354、CLI 218、Flutter 90、WS URL 2、desktop gateway、Playwright 14 页全部通过
- CLI 帮助用例隔离 `FORCE_COLOR`；Flutter 桌面 golden 随品牌色更新
- `scripts/web_e2e.mjs` 支持 `E2E_TOKEN`，断言对齐现文案（行情台 / 市场分析）

### 🔧 Influx 批量查询
- 单标的仍 8s 超时；质检/策略/回测走 45s 批量客户端
- Flux 不用 `contains()`（1 只约 30s），改等值 `or`；分片 10，瞬时失败才重试
- 线上质检 75 只约 3 秒完成并落库（asOf 2026-08-25，21 条）

### 🔧 测试后优化（续）
- 因子质检 HTTP 入队；K 线改 `query_klines_many`
- 自选回测按市场批量拉 K
- 登录后 `CurrentUser` 进 Redis，改用户/角色/菜单时失效
- 业务表校对统一 `utf8mb4_general_ci`；隐藏量化自选侧栏
- Flutter 交易终端指数走 WS；`IndexedStack` 后台停定时器
- 行情 WS 不再接受 query `token=`

### 🔧 测试后优化
- Vue 行情 WS 开帧 `{type:auth,token}`，与 Flutter 一致；URL 仍不带 token
- JWT / Cookie / Redis 会话统一 8 小时（idle 不再 30 分钟 401）
- `/market/terminal` 移出登录白名单；快捷导航/资产条/持仓/风控入口并到 `/trade/terminal`
- 次日清单「加入量化」写入 `market_watchlist`；终端去掉与 WS 重复的 15s 指数 REST
- 需求沟通 keep-alive 离开页签停 2.5s 轮询

### 🧭 交易台 / 自选合一
- `/trade/trading`、`/trade/desk` 重定向到 `/trade/terminal`；侧栏隐藏旧入口
- 量化自选读写行情 `market_watchlist`；存量 `quant_watchlist` 迁入
- 策略空池不再扫全市场精选池；Influx 按市场批量拉 K，并发上限 8
- Electron 归档；客户端版本空 URL 指向 GitHub Releases

### 💹 交易台只走真实行情
- 去掉前端随机假价模拟器（`mockData` + `Math.random` 跳价）；拉不到自选/K 线显示空态，右上角 `LIVE` / `无数据`
- 指数条与交易台顶栏接 `WS /ws/market/quotes`（Cookie 鉴权，断线 REST 回退）
- 行情/自选/委托等页签 `onDeactivated` 停轮询，不再只看浏览器 tab

### 🔐 隔离与入队
- 工作台 `dashboard:summary` 缓存按用户 + 权限指纹隔离
- 工作台各块改为顺序使用同一 AsyncSession
- `POST /quant/scan/daily`、`POST /market/sync/mysql-to-influx` 入队立即回 ticket
- 舆情 Widget CORS 回显白名单 Origin，不再 `*`

### 📱 客户端
- iPad/Android 宽屏不再进桌面 WebView，继续原生五栏
- 桌面 WebView 不再用 JS 写入 JWT Cookie
- Cookie 有效期与 JWT 8 小时对齐
- 「我的」挂上自选 / 资讯 / 通知 / AI 研判
- 品牌色对齐 Web indigo `#6366f1`

### 🗂 自选与自动交易
- `market_watchlist.groups` 独立列；表单分组与备注分开
- 自动交易扫描叠加行情自选（不再只扫量化池后回落到精选池）

### 🛠 运维
- 版本检查 SQL 纳入 `sql_migrate.py`；Prometheus 刮齐 API/jobs；调度默认 `coalesce`
- Electron 标明过渡归档；DEPLOY 补充 MySQL/Influx 备份；前后端 `.dockerignore`

### 📖 部署
- `docs/DEPLOY.md` 增加「云主机怎么部署」：拉 `main`、只滚业务容器、不要 down、不要动 grok2api / Influx 卷

### ⚡ 项目性能（不是按云主机砍 Docker 上限）
- **撤回**按 16G 云主机下调 MySQL/调度/Influx 查询内存的编排改动；那会拖慢资源更大的本机
- 操作日志 Redis Stream **只由 platform API 消费**；trade/market/quant/news/ai 不再每人一份 `XREADGROUP`
- K 线 / 指标 / 历史把 `limit` 下推到 Influx `tail`，避免默认拉两年再在 Python 里切片
- Docker 示例关闭容器内文件日志（stdout 即可）；云上 `.env.dockersentiment` 可设 `LOG_FILE_ENABLED=false`

### 💹 去掉平台纸账户层
- 下单 / 撤单不再看 `longport_trading_enabled` 或 `allow_sim`；配了长桥模拟账户就是模拟，配了真实账户就是真实
- 删除服务端「只读/模拟模式」拦截和客户端 `requirePaper` / `paperAccount` 标记
- 自动交易是否委托仍由该账户 `auto_trade_enabled` 决定，不是纸账户开关

### 💹 美股盘前 / 盘后 / 夜盘下单
- 长桥**实盘**支持美股延长时段：盘前 04:00–09:30 ET、盘后 16:00–20:00 ET（`OutsideRTH.AnyTime`），夜盘周日～周四 20:00–次日 03:50 ET（`OutsideRTH.Overnight`）
- 此前 `submit_order` 未传 `outside_rth`，默认只走常规盘；现美股手动/自动/清单下单均按当前时段设置
- 行情 Config 打开 `enable_overnight`，夜盘报价与 K 线不再被 SDK 默认关掉
- 港股 / A 股不传该参数；周日 20:00 ET 起客户端标「夜盘」而不再显示「休市」
- 长桥**模拟账户**不撮合美股盘前、盘后、夜盘，只在常规盘（09:30–16:00 ET）模拟成交

### 💹 自动交易默认策略
- 扫描池改为美/港行情热度 Top50（可叠加该账户美/港自选），**A 股不扫描、不下单**
- 已持仓或当日已买入的标的不再加仓
- 总持仓市值达到或超过净资产、或可用现金不足时停止买入
- 定时扫描覆盖已配置长桥的账户，不只是有量化自选的账户

### ⚡ 启动、队列与内存
- 登录/交易/AI/舆情 API 不再 `depends_on` Influx healthy；前端也不再等行情/量化进程
- Redis 钉 `7-alpine`，AOF + 256mb `noeviction` + 数据卷；jobs worker 补 `/health`
- 部署脚本先起 API 再起前端
- Grok 单标的 / 批量研判 / 自选单票分析入 `llm` 队列，HTTP 立即回 ticket；SSE 流式仍走市场 API
- 调度入队失败不再在 scheduler 内联跑重任务；`api/scheduler/worker` 跳过 `create_all`
- 慢速 K 线 / 全市场代码同步入 `market` 队列
- pandas、`MarketService` 在用户导入/交易快照路径懒加载
- 热度采集 Influx 指数 K 失败时回退行情，不整单失败
- 任务重试中 ticket 为 `retrying`，避免前端当失败停轮询
- HTTP 自选「分析全部」只跑当前用户；收盘复盘 / 选股 / 热度采集入队失败不再内联
- `excel_util` 不再顶层导入 pandas

### 🖥️ 前端轮询
- 自选/看板/首页/委托/通知等后台标签暂停轮询；需求沟通仅在有 job 时轮询
- `/trade/ai/` nginx 超时 180s；指数 WS 默认间隔 15s（对齐 30s 缓存）
- 自选 overview Redis 缓存 10s

### 📱 Flutter
- Debug 默认本机 Docker，保留 `10.0.2.2`；Release 仍把模拟器环回改回线上
- 手机持仓极速交易去掉纸面保护拦截，直接提交 `/trade/order`
- 舆情仪表盘将后端 [-10,10] 影响分映射为 0–100（-10→0、0→50、10→100）

### 🔐 对外接口
- 舆情 Widget、需求清单导出不再使用环境变量固定 Token；先加密 `POST` 用户名密码换 60 分钟 JWT，再 `Authorization: Bearer` 访问
- `/open/token`、`/sentiment/widget/token` 与 `/open/sync/token` 一样强制 RSA-OAEP + AES-256-GCM 信封，明文密码拒绝

### ⚠️ 注意事项
- 禁止 `compose down` 整栈、禁止删 Influx 命名卷；滚动业务容器用 `--no-deps`
- Redis 新镜像/AOF/`noeviction` 要单独 `up ruoyi-redis` 才生效；第一次挂新卷会清空会话和任务队列（库表和行情时序不受影响），用户需重新登录
- Influx 未就绪时登录应可用，行情/量化可能 502；`market`/`quant` 重建仍会等 Influx healthy
- 研判/复盘/选股 HTTP 只回 ticket，前端轮询 `/market/jobs/{id}`；重试中是 `retrying` 不是 `failed`
- 调度入队失败本轮跳过、不内联；窗口型任务（收盘 K、开盘送单）失败后要手动补跑
- 拆分角色跳过 `create_all`，新环境必须跑 `sql_migrate.py`
- SSE 流式研判仍走市场 API；自动交易是否下单看账户 `auto_trade_enabled`，下单目标就是该账户长桥凭据对应的模拟或真实账户
- 完整说明见 `docs/DEPLOY.md`「2.1 本次改动注意事项」

### 🐛 调度与内存
- 修复「立即执行」：ORM 行转 JobModel 保留 snake_case `invoke_target`
- 调度日志只记 JobExecutionEvent；配置同步不再因 `update_time` 为空每 30 秒删加任务
- 自动交易扫描入 `quant` 队列，不再占 scheduler 进程
- Influx 超时 8s、容器内存上限；平台 API `APP_MODULE=platform`；pandas 改为按需导入
- 示例库连接池 8+4（约 10 进程 ×12 ≈ 120，低于 MySQL 300）

### 🧹 仓库清理
- 移除根目录与 `docs/` 下的设计稿、反重力图片、NotebookLM/反重力逐页规范、`todos.md`、`ox意见.md`

---

## [v1.8.0] - 2026-08-26 - 手机原生五栏、桌面 WebView 壳、实时持仓 (0826 V11)

### 📱 Flutter 手机
- 底栏改为舆情 / 选股 / 热度 / 持仓 / 我的；量化、需求沟通、网关放到「我的」
- 智能选股结论优先（评分 / 立场 / 建议 / 摘要），点行进 K 线
- 持仓用长桥现价自算涨跌幅与浮动盈亏；总资产港元 / 美元切换
- 个股详情对齐反重力设计稿图 01：大字报价、指标格、周期、十档、AI 研判、买卖栏
- 底部抽屉极速下单（`showFastTicket`）：限价、25%/50%/75%/全仓
- 需求沟通改为对话气泡（`AiReqChatPage`），轮询 `jobId`，不再用消息表格
- 登录页接入 `CyberBackground`；macOS 沉浸式标题栏 + 交通灯避让

### 🖥️ Flutter 桌面
- 宽屏登录后 `DesktopWebShell` 用 WebView 打开网关 `/portal`，与 Docker Web 同一份前端
- JWT 写入 `Admin-Token` Cookie；macOS JWT 改存 SharedPreferences（开发签名不再弹钥匙串）
- 默认网关 `https://sfp.luapi.top`；`10.0.2.2` / `10.0.3.2` 视为未配置并回落线上
- 依赖 `webview_flutter`；macOS 窗口 `fullSizeContentView`、标题「智慧金融」

### 💹 后端行情 / 交易
- 指数批量：美股补道琼斯、港股补恒生国企、A 股补创业板/科创板；休市也返回最近报价；缓存 `market:index:quotes:v3`
- `GET /trade/positions` 叠长桥 realtime `last`/`prevClose`，港股代码去前导零互认
- 新增 `GET /trade/quote/realtime`（权限 `trade:position:list`）

### 🚪 Web
- 门户卡片按 `permissionStore.addRoutes` 过滤；无权限不展示系统/监控/工具/分析
- `/trade/terminal` 与 `/market/terminal` 两条直达路由都保留

### 🧪 测试
- 指数规格、持仓行情合并、默认网关单测；壳层 golden 更新

---

## [v1.7.1] - 2026-08-25 - Android / iOS / Windows 原生壳补回 (0825 晚)

### 🖥️ Flutter 三端
- 从清空前的平台工程还原，并对齐今日 macOS：HTTP 网关、显示名「智慧金融」、桌面窗 1440×900 / 最小 1100×700
- Android：`network_security_config` 明文网关、预测性返回；本机 debug + release APK 已构建（无 keystore 时 debug 签名）
- iOS：ATS 本地网络、`NSLocalNetworkUsageDescription`、出口合规标记；`flutter build ios --debug --no-codesign` 已通过。`ios/scripts/xcrun` 仅在 `xcode-select` 指向 CommandLineTools 时帮 Dart native-asset 找到完整 Xcode
- Windows：居中、最小尺寸 `WM_GETMINMAXINFO`、NSIS 快捷方式中文名；本机不交叉编译，CI `windows-latest` 出 zip + setup.exe
- `flutter.yml` 恢复四平台 job；push 触发仍仅 `main` / tag / PR

---

## [v1.7.0] - 2026-08-25 - 交易台时段 K 线、北京时间、macOS 客户端 (0825 V10)

### 💹 交易台 / 行情台
- 自选分组下拉，打开默认第一只标的；顶栏全市场代码搜索
- 盘中 K 线走长桥 `TradeSessions.All`（美股 4:00 ET 盘前可见 1 分钟线）；日/周/月走 Influx；港/A 休市回当天日 K
- 长桥 LV1 无美股隔夜（20:00–04:00 ET）分钟线，不捏造
- 交易台量化自动交易开关（无密钥灰显）；单票仓位占净值上限；同日买单去重

### ⏰ 时间
- 长桥 / Influx UTC → 北京时间展示
- 舆情 naive `pub_time` 仍按北京墙钟，**不二次 +8**
- 信封响应 `time` 按北京编码

### 🔄 同步与量化
- 生产→本地：加密用户名密码换 `/open/sync` 短期令牌（`scripts/sync_from_prod.py`）
- `max_symbol_position_pct` 默认 0.10；增量 SQL `sql/quant-symbol-position-pct.sql`

### 🖥️ Flutter / CI
- 当日先只改 macOS 原生壳；三端曾清空为占位（当晚已在 v1.7.1 补回）
- push 触发收窄到 `main` + tag + PR，减轻邮件风暴
- 舆情 ruff：429 命名常量、isort、过长分支 noqa，避免 ratchet 在 PR 上失败
---

## [v1.6.0] - 2026-08-24 - 四端客户端 M2–M5 全量落地与行情实时通道 (0824 V9)

### 📱 Flutter 四端客户端（功能全量对齐 Web）
- M2：财经资讯简报流、舆情只读仪表盘、AI 研判查看（单标的+批次明细）、通知中心轮询已读
- M3：量化研究只读链路——策略信号、8 族权重雷达、因子 IC·IR·五分位、扫描台账；严格避开一切触发计算/写库端点
- M4：交易台只读终端——账户资产、长桥绑定态与连通性测试、持仓委托、盘口十档+逐笔、纸面护栏用量、风控事件；
  后端暂无 paper 订单簿端点，客户端不接下单写端点并常驻「纸面保护态」徽标（偏差见四端规划 M4 记录，待后端补端点）
- M5 发布工程：启动版本检查+强制更新弹窗、Android release 签名 APK、CI v* tag 三平台产物自动发 GitHub Release、
  macOS dmg 打包、macOS 真窗口集成测试闭环、Windows NSIS 安装包（CI 内 choco 装 NSIS 构建 setup.exe）

### 📡 后端配套
- `WS /ws/market/quotes`：JWT 鉴权行情推送，nginx 升级头透传
- `GET /app/version` 版本检查服务：基线存 sys_config，管理员改参数即生效（种子 `sql/app-version-config.sql`）
- 残缺 `Bearer` 头归一返回 401（此前 IndexError 兜底成 code:500）

### 🔧 部署与运维
- Redis 密码改为可选（留空=无密码，设置则 requirepass），与运行栈现状一致
- 中间件兼容核查关闭：Dart UA / 无 Referer 登录实测正常，审计与限流按 IP 维度正常

### ⏳ 遗留待办
- iOS TestFlight 上传与 macOS 公证（账号已具备，待 App Store Connect API 凭据配置，暂缓）
- 官网直装页（待分发域名）；sys_config android.url 占位替换

### 🧪 质量线
- 壳层 golden 基线仅在 macOS 强制（跨平台字体光栅差 1~3%），Linux/Windows 显式跳过；
  四平台 CI 构建矩阵首次全绿（含 Windows 安装包）
---

## [v1.5.0] - 2026-08-24 - 四端 Flutter、全量优化与舆情 Widget (0824 V8)

### 📱 Flutter 四端客户端
- 新增 `flutter_client/`：iOS / Android / macOS / Windows 单工程
- M0：网关探测、登录/注册/会话、CI 四平台构建矩阵
- M1 先行：行情热度 Top50、自选分组、全部股票、标的 K 线详情
- 「墨蓝金融终端」设计令牌与共享组件；调试 `/gallery`；壳层 golden
- 修复 macOS 钥匙串 `errSecMissingEntitlement`；补齐被根 `.gitignore` 误吞的 Dart 源码

### 🔒 安全与容器
- 清除误提交的真实 admin 初始密码（代码 + git 历史已重写）
- 监控栈与 jobs/backend 管理端口改绑 `127.0.0.1`
- compose 显式透传 `DB_PASSWORD` / `REDIS_PASSWORD`
- fastapi / starlette / Pillow / PyJWT 升级；CI pip-audit + 双镜像冒烟
- 后端多阶段构建（体积约 -23%）；前端 nginx-unprivileged

### 🛠️ 可靠性与架构
- Redis 队列认领-确认（可见性超时、重试、死信）
- Influx `latest_date` 渐进窗口；SQL `schema_version` 登记制
- scheduler / longbridge / transport_crypto 拆分子包；公共层依赖倒置
- 生产构建后左侧菜单消失已修复

### 📰 舆情与工作台
- `GET /sentiment/widget/dashboard` Token 门禁只读聚合（macOS Widget）
- 舆情时间统一北京时间展示与落库
- `GET /dashboard/summary` 分段 5 秒超时，读模型缺失不再回退长桥实时

### ⚠️ 破坏性变更 (Breaking Changes)
- 历史误提交的 admin 初始密码已从 git 历史清除；此前部署环境必须立即改密
- 管理端口仅本机回环，云上需走网关反代
- Flutter 客户端替代 Electron / uni-app 原生职责（Electron 与 H5 双轨保留至对齐后下线）

---

## [v1.4.0] - 2026-08-23 - 智能选股、全市场分页与收盘 K 线 (0823 V7)

### ✨ 智能选股
- 候选：各市场 Top50 + 精选池，日 K 因子打分叠加三市场舆情
- 仅开盘市场带实时指数；默认 Grok 4.6，在 AI 模型管理配置适用范围「行情中心」
- 入选标的全部走 AI 研判；单标的研判统一到 `StockPickService.analyze_symbol`
- 按日期浏览历史选股单；限流重试避免 ORM 过期写库失败
- 增量 SQL：`sql/market-stock-pick.sql`

### 📚 全部股票
- `GET /market/instrument/universe` 强制分页（默认 50、最大 200）
- 增量 SQL：`sql/market-universe-menu.sql`

### ⏰ 收盘同步
- A 股 15:25、港股 16:25、美股约 05:25 北京时间拉日 K + 分时
- 分时写入 Influx `minute_kline`（精选 + Top50）

### 💹 交易与沟通
- 自动交易按用户隔离 + rebalance 卖出护栏
- 需求沟通多 AI、次日模拟清单、飞书推送

### 🧪 CI
- ruff ratchet 路径修正；新增文件 lint 债务归零

---

## [v1.3.0] - 2026-08-22 - 自选隔离、行情综合化与全市场回填 (0822 V6)

### ⭐ 自选与菜单
- 行情自选全面带 `user_id`，与量化 `quant_watchlist` 分离
- 自选三栏（分组 / K 线 / 综合）；侧栏压平为五个入口
- 增量 SQL：`sql/market-menu-unify.sql`、`sql/quant-longbridge-user.sql`

### 🔑 长桥按账户
- 凭据按登录用户读写；请求级 `ContextVar`；jobs 回退 admin
- 保存掩码不覆盖原密钥

### 📈 体验与数据
- 行情中心综合化视觉；舆情大盘叠加大盘指数条
- 工作台聚合 summary；资产四卡按券商凭据隐藏
- `sync_market_listings.py` / `sync_klines_slow.py` 全市场回填

### ⚙️ 性能与安全
- 前端按需 echarts、manual chunks、请求去重
- 后端批量 roundtrip、同步 IO 卸载
- 密钥 / CORS / 传输错误 / 容器默认值加固

---

## [v1.2.0] - 2026-08-21 - 热度看板、任务拆分与长桥熔断 (0821 V5)

### 🔥 市场热度
- 三市场收盘采集写入 `market_heat_daily` / `market_top50_snapshot`
- 市值过滤与权重走 `sys_config`

### 🧵 进程拆分
- APScheduler 只在 `sentiment-jobs`；market / quant / llm 三消费组
- 交易实时单独进程；需求沟通入 `llm` 队列，Grok 不堵 API

### 📚 浏览行情只走库
- 列表报价不再 overlay 长桥实时价；无效 Token 不再打挂列表页
- 长桥 401004 / 超时共享熔断器

### 🧮 量化与风控
- Alphalens 风格 IC / IR / 五分位收益
- 风险事件审批；Alpha101 / 158 快照与 ReadModel

---

## [v1.1.0] - 2026-08-20 - 交易台、门户与纸面自动交易 (0820 V4)

### 💹 交易台
- 深度、逐笔、周期 K 线叠在盘口与成交明细上方
- 空 K 线不再留白块；持仓跳转跟路由 query

### 🚪 门户与登录
- 门户入口收成六组卡片，去掉「若依官网」
- 登录浅色 / 深色与系统 chrome 持久化同一套键

### 🤖 自动交易
- 默认纸面、服务端拦截实盘
- 真源 K 线 seeder（新浪 / 腾讯 + 熔断），禁止合成 OHLCV
- Prometheus / Grafana 监控栈

---

## [v1.0.0] - 2026-07-23 - 初始公开发布

### ✨ 核心功能
- 行情 / 舆情 / 量化 / 交易 / AI 工作台一体化
- 配置只留 `.env.*.example`，贡献要求 PR 进 `main`

### 🛠 技术栈
- 前端：Vue 3, Element Plus, Vite, ECharts, Pinia
- 后端：Python FastAPI, SQLAlchemy async, JWT
- 数据：MySQL 8, Redis, InfluxDB 2.x

---

## 版本规范

遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范：

- **主版本号**：不兼容的 API 修改
- **次版本号**：向后兼容的功能性新增
- **修订号**：向后兼容的问题修正

---

_最后更新：2026-08-24_

---

## 上游 RuoYi-Vue3-FastAPI 历史

下列为上游框架发布记录，供对照依赖与底座能力；本仓库业务迭代见上方版本。

## RuoYi-Vue3-FastAPI v1.9.0

### 项目依赖

前后端依赖均有升级，请升级依赖或重新创建环境。

### 新增功能

1.新增AI管理模块 ([#69](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/69))。
2.新增移动端模块 ([#73](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/73))。
3.新增多worker运行支持 ([#76](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/76))。
4.应用新增演示模式 ([#78](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/78))。

### BUG修复

1.修复代码生成controller模板删除接口query_db参数异常的问题 ([#63](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/63))。
2.修复登录接口response_model声明错误 ([#71](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/71))。
3.修复无法直接通过后端地址访问API文档的问题 ([#74](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/74))。
4.修复create_app重复执行的问题 ([#84](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/84))。

### 代码重构

1.移除对python3.9的支持 ([#67](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/67))。

### 代码优化

1.优化alembic处理表模型逻辑，避免无关表影响 ([#68](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/68))。
2.优化代码生成后端模板 ([#72](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/72))。
3.自动注册路由出错时抛出异常以便于调试 ([#79](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/79))。
4.优化部分页面字段tooltip说明 (#80)。
5.优化项目启动速度 ([#82](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/82))。
6.优化暗黑模式切换效果 ([#83](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/83))。
7.优化热重载模式或单worker下scheduler的任务状态同步机制 ([#85](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/85))。
8.优化防重提交间隔时间可自定义 ([#87](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/87))。
9.优化验证码计算结果为非负数 ([#88](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/88))。
10.优化ci测试稳定性 ([#90](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/90))。

## RuoYi-Vue3-FastAPI v1.8.1

### 新增功能

1.新增E2E测试 ([#57](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/57))。

### BUG修复

1.修复DictTag组件渲染异常的问题 ([#59](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/59))。

### 代码优化

1.优化数据权限依赖 ([#55](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/55))。
2.动态导入定时任务函数，移除eval ([#56](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/56))。
3.优化pg版本的docker compose配置文件 ([#61](https://github.com/insistence/RuoYi-Vue3-FastAPI/pull/61))。

## RuoYi-Vue3-FastAPI v1.8.0

### 项目依赖

#### 后端

1.后端依赖升级到最新版本，请升级依赖或重新创建环境。

### 新增功能

1.新增请求上下文管理类。
2.新增`PreAuthDependency`、`CurrentUserDependency`、`DataScopeDependency`、`DBSessionDependency`、`UserInterfaceAuthDependency`和`RoleInterfaceAuthDependency`依赖函数。
3.新增上下文清理中间件。
4.新增公共vo模块。
5.新增配置文档静态资源方法。
6.新增自动注册路由功能。
7.新增docker compose部署方式。
8.菜单导航设置支持纯顶部。

### BUG修复

1.修复单账号登录模式下强退功能失效的问题 [#52](https://github.com/insistence/RuoYi-Vue3-FastAPI/issues/52)。
2.确保ApschedulerJobs字段类型与apscheduler默认创建的表字段类型一致 [#53](https://github.com/insistence/RuoYi-Vue3-FastAPI/issues/53)。
3.修复磁盘存在异常时服务监控无法正常运行的问题。
4.移除代码生成表业务表外键，修复无法删除的问题。
5.修复固定头部时出现的导航栏偏移问题。
6.修复表单构建移除所有控件后切换路由回来空白问题。
7.修复代码生成v3模板时间控件between选择后清空报错问题。

### 代码重构

1.增强ruff规则，完善类型提示。
2.优化项目结构，新增common模块，原annotation、aspect、constant、enums模块移动至common模块下。
3.重构app与server设计。

### 代码优化

1.controller层全部使用新依赖项。
2.当前用户信息使用上下文变量。
3.分页模型改为使用公共vo模块的PageModel。
4.优化API文档的响应模型显示。
5.操作响应模型改为使用公共vo模块的CrudResponseModel。
6.优化API文档的接口描述信息。
7.登录/注册页面底部版权信息修改为读取配置。
8.优化生成代码下载的zip文件名。
9.优化表单构建关闭页签销毁复制插件。
10.行内表单默认设置固定宽度。
11.优化操作日志详细请求参数显示。
12.优化index页面标题读取配置。
13.优化字典组件数字类型值处理逻辑。
14.优化字典组件值宽松匹配。
15.默认固定头部。

## RuoYi-Vue3-FastAPI v1.7.1

### 项目依赖

1.后端依赖移除passlib，直接使用bcrypt。

### BUG修复

1.修复代码生成controller模板编辑接口异常生成字段的问题。
2.移除passlib直接使用bcrypt修复密码校验异常的问题 [#48](https://github.com/insistence/RuoYi-Vue3-FastAPI/issues/48) [#49](https://github.com/insistence/RuoYi-Vue3-FastAPI/issues/49)。

### 代码优化

1.代码生成do模板补充表描述。

## RuoYi-Vue3-FastAPI v1.7.0

### 项目依赖

1.前后端依赖升级，请升级依赖或重新创建环境。

### 新增功能

1.新增alembic支持。
2.文件&图片上传组件支持自定义地址&参数。
3.新增默认打包配置项。
4.显隐列组件支持全选/全不选。
5.添加页签openPage支持传递参数。
6.外链加载时遮罩信息提示。
7.上传组件新增拖动排序属性。
8.图片上传组件新增disabled属性。
9.代码生成列支持拖动排序。
10.新增用户默认初始化密码。
11.新增页签图标显示开关功能。
12.新增底部版权信息及开关。
13.用户归属部门新增清除。
14.用户导入新增验证提示。
15.菜单搜索支持键盘选择&悬浮主题背景。
16.新增apscheduler_jobs表对应sqlalchemy模型类。
17.初始密码支持自定义修改策略。
18.账号密码支持自定义更新周期。
19.注册账号设置默认密码最后更新时间。
20.显示列信息支持对象格式。

### BUG修复

1.修复logout接口未按照app_same_time_login配置项动态判断的问题 [#IBZZ1S](https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI/issues/IBZZ1S)。
2.修复上传组件被多次引用拖动仅对第一个有效的问题。

### 代码优化

1.优化接口耗时计算。
2.优化启动信息显示。
3.优化前端处理路由函数代码。
4.登录页和注册页表头使用VITE_APP_BASE_API配置值。
5.优化角色禁用不允许分配。
6.优化富文本控制台警告异常。
7.优化checkbox废弃API。
8.优化导航栏显示昵称&设置。

### 代码重构

1.重构IP归属区域查询为异步调用。
2.调整do与sql使其相互适配以支持alembic。
3.富文本复制粘贴图片上传至url。

## RuoYi-Vue3-FastAPI v1.6.2

### 新增功能

1.文件上传组件新增disabled属性。
2.文件上传组件新增类型。

### BUG修复

1.修复日志管理时间查询报错 [#27](https://github.com/insistence/RuoYi-Vue3-FastAPI/issues/27)。
2.修复定时任务状态暂停时执行单次任务会触发cron表达式的问题 [#31](https://github.com/insistence/RuoYi-Vue3-FastAPI/issues/31)。
3.修复修改字典类型时获取dict_code异常的问题。
4.修复修改字典类型时字典数据更新时间异常的问题。
5.修复代码生成模板时间查询问题 [#28](https://github.com/insistence/RuoYi-Vue3-FastAPI/issues/28)。
6.修复用户导出缺失部门名称的问题。

### 代码优化

1.优化代码生成新增和编辑字段显示和渲染。
2.pagination更换成flex布局。
3.优化代码生成vue模板 [#23](https://github.com/insistence/RuoYi-Vue3-FastAPI/issues/23)。

## RuoYi-Vue3-FastAPI v1.6.1

### 项目依赖

#### 后端

1.新增sqlglot依赖

```bash
pip install sqlglot[rs]==26.6.0 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### BUG修复

1.引入sqlglot修复sql语句解析异常的问题。
2.修复代码生成字段唯一性校验dao层模板判断异常的问题。
3.引入泛型修复as_query和as_form装饰模型文档丢失的问题。
4.修复代码生成主子表vo模板可能缺失NotBlank的问题。

## RuoYi-Vue3-FastAPI v1.6.0

### 项目依赖

1.后端依赖升级到最新版本，请升级依赖或重新创建环境。

### 新增功能

1.新增代码生成功能，支持配置数据库表信息一键生成和下载前后端代码，需要重新执行sql文件，请先备份数据。
2.新增表单构建功能。
3.用户头像新增支持http(s)链接。
4.新增trace中间件强化日志链路追踪和响应头 [@y1ren](https://gitee.com/y1ren)。
5.用户管理支持分栏拖动。
6.菜单面包屑导航支持多层级显示。
7.白名单支持对通配符路径匹配。
8.支持开启暗黑模式。

### BUG修复

1.修复默认关闭Tags-Views时，内链页面打不开。
2.修复删除当前登录用户拦截失效的问题。
3.修复定时任务目标字符串规则校验不全的问题。
4.修复执行单次任务时会覆盖已启用任务的问题 [#IBEKD2](https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI/issues/IBEKD2)。
5.修复个人中心特殊字符密码修改失败问题。

### 代码优化

1.优化导出方法。
2.参数键值更换为多行文本。
3.优化日志中操作方法显示。
4.优化日志装饰器获取核心参数的方式。
5.用户管理过滤掉已禁用部门。
6.优化TopNav内链菜单点击没有高亮。
7.ResponseUtil补充完整参数。

## RuoYi-Vue3-FastAPI v1.5.1

### 新增功能

1.定时任务新增支持调用异步函数。

### 代码优化

1.优化字典数组条件判断。
2.校检文件名是否包含特殊字符。
3.移除已弃用的log_decorator装饰器。

## RuoYi-Vue3-FastAPI v1.5.0

### 新增功能

1.新增对PostgreSQL数据库的支持。

### BUG修复

1.修复DictTag组件控制台抛异常的问题 [#IAYSVZ](https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI/issues/IAYSVZ)。
2.修复登录日志导出文件名称错误的问题。

### 代码回滚

1.因fastapi查询参数模型底层存在bug，回滚查询参数模型声明方式为as_query。

### 代码优化

1.优化CamelCaseUtil和SnakeCaseUtil以兼容更多转换场景。
2.优化列表查询排序。
3.优化参数设置页面。
4.优化上传图片带域名时不增加前缀。

## RuoYi-Vue3-FastAPI v1.4.0

### 项目依赖

#### 后端

1.更新fastapi版本为0.115.0

```bash
pip install fastapi[all]==0.115.0 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 代码重构

1.基于fastapi 0.115.0版本新特性，直接使用pydantic模型接收查询参数和表单数据，移除原有as_query和as_form使用方式。

### BUG修复

1.修复角色管理service书写错误。

### 代码优化

1.优化前端登录请求方法。

## RuoYi-Vue3-FastAPI v1.3.3

### 项目依赖

#### 后端

1.更新pydantic-validation-decorator版本为0.1.4，修复了一些底层bug。

### BUG修复

1.修复在线用户模块条件查询无效的问题。

### 代码优化

1.优化在线用户模块前后端字段描述一致。
2.日志装饰器异常处理增加logger打印日志。

## RuoYi-Vue3-FastAPI v1.3.2

### 新增功能

1.新增gzip压缩中间件。

### BUG修复

1.修复分页函数计算has_next错误的问题 [#10](https://github.com/insistence/RuoYi-Vue3-FastAPI/issues/10)。
2.修复定时任务监听函数中事件没有job_id报错的问题。

### 代码优化

1.优化添加中间件函数注释。

## RuoYi-Vue3-FastAPI v1.3.1

### BUG修复

1.修复1.3.0版本采用新的异常处理机制后日志装饰器无法记录异常日志的问题。

### 代码优化

1.补充定时任务违规字符串。

## RuoYi-Vue3-FastAPI v1.3.0

### 项目依赖

1.前后端依赖均升级到最新版本，请升级依赖或重新创建环境。
2.使用`PyJWT`替换`python-jose`以解决一些安全性问题。

### 新增功能

1.新增字段校验装饰器，支持手动触发校验，已封装为`pydantic-validation-decorator`库。
2.各模块`service`层新增字段唯一性校验。
3.全局新增`ServiceException`自定义服务异常和`ServiceWarning`自定义服务警告，无需在接口中写大量的异常捕获。
4.菜单管理新增路由名称，请执行以下sql为数据库新增字段：

```sql
ALTER TABLE sys_menu ADD COLUMN route_name varchar(50) DEFAULT '';
```

5.新增`constant`常量配置及`enums`枚举类型配置。
6.新增`StringUtil`、`CronUtil`工具类。

### BUG修复

1.修复用户管理、角色管理、部门管理越权漏洞。
2.修复各模块`dao`层`status`、`del_flag`类型与数据库不一致的问题。
3.修复移动端左侧菜单无法显示的问题。
4.修复其他已知BUG。

### 代码重构

1.重构日志装饰器为`Log`，未来版本将删除`log_decorator`装饰器，请尽快迁移。
2.重构`RedisInitKeyConfig`为枚举类型，现在可通过以下方式获取对应的`key`和`remark`
`RedisInitKeyConfig.ACCESS_TOKEN.key`、`RedisInitKeyConfig.ACCESS_TOKEN.remark`。
3.重构数据权限逻辑，底层进行优化，使用方法与之前相同。

### 代码优化

1.引入`ruff`对后端代码进行格式化及检测修复，优化导入。
2.各模块基于`ServiceException`自定义服务异常和`ServiceWarning`自定义服务警告优化了异常处理逻辑。
3.各模块`vo`层使用`Field`声明字段。
4.优化API文档字段描述显示。

## RuoYi-Vue3-FastAPI v1.2.2

### BUG修复

1.修复删除定时任务时未移除调度中任务的问题。
2.修复菜单生成路由时组件条件判断错误的问题。

## RuoYi-Vue3-FastAPI v1.2.1

### BUG修复

1.修复各模块新增数据时创建时间记录异常的问题。
2.修复菜单挂载到根目录时路由加载异常等一系列相关问题。

### 代码及性能优化

1.修改代理localhost为127.0.0.1以适配部分设备解析localhost异常的问题。

## RuoYi-Vue3-FastAPI v1.2.0

### 重要说明

本次更新为 **_破坏性更新_** ，重构数据库orm为异步，代码改动很大，请谨慎升级。
1.原有的Session类型声明统一变更为AsyncSession。
2.service层和dao层的函数修改为异步函数，请使用await调用。
3.orm查询不再支持query，请使用select、update、delete等语句，具体使用方法请参考[https://docs.sqlalchemy.org/en/20/orm/queryguide/index.html](https://docs.sqlalchemy.org/en/20/orm/queryguide/index.html)。

### 项目依赖

#### 后端

1.增加asyncmy依赖用于支持orm异步操作mysql，请重新安装依赖

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple。
```

### 新增功能

1.新增SnakeCaseUtil工具类，将原CamelCaseUtil工具类的camel_to_snake函数迁移至SnakeCaseUtil工具类。

### BUG修复

1.修复用户管理模块重置用户密码时会异常重置用户岗位和角色的问题。
2.修复清空定时任务日志异常的问题。

## RuoYi-Vue3-FastAPI v1.1.3

### 新增功能

1.用户密码新增非法字符验证。

### BUG修复

1.修复通知公告列表查询前后端字段不一致的问题。
2.修复个人中心修改基本资料后端异常的问题。

## RuoYi-Vue3-FastAPI v1.1.2

### 新增功能

1.配置文件新增数据库连接池相关配置。

### BUG修复

1.修复个人中心修改密码后端异常的问题。

### 代码及性能优化

1.使用@lru_cache缓存ip归属区域查询结果，避免重复调用ip归属区域查询接口以优化性能。

## RuoYi-Vue3-FastAPI v1.1.1

### BUG修复

1.修复编辑定时任务时更新的信息未同步至scheduler的问题 [#I9EK56](https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI/issues/I9EK56)。
2.修复编辑角色数据权限时后端异常的问题 [#I9ENQN](https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI/issues/I9ENQN)。
3.修复菜单配置路由参数不生效的问题。
4.修复获取路由信息时菜单排序不生效的问题。
5.修复添加菜单时是否外链和是否缓存回显异常的问题。

## RuoYi-Vue3-FastAPI v1.1.0

### 新增功能

1.后端配置文件新增sqlalchemy日志开关配置。
2.后端配置文件新增IP归属区域查询开关配置。
3.后端配置文件新增账号同时登录开关配置。

### BUG修复

1.修复token本身过期时退出登录接口异常的问题 [#I9CBWT](https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI/issues/I9CBWT)。
2.修复系统版本号或浏览器版本号无法获取时登录异常的问题 [#I9CYNM](https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI/issues/I9CYNM)。

## RuoYi-Vue3-FastAPI v1.0.3

### 新增功能

1.账号密码登录新增IP黑名单校验。

### BUG修复

1.修复外链菜单无法打开的问题 [#I95KBK](https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI/issues/I95KBK)。
2.修复添加和编辑菜单页面中是否缓存和是否外链字段回显异常的问题 [#I95KBK](https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI/issues/I95KBK)。

## RuoYi-Vue3-FastAPI v1.0.2

### 新增功能

1.用户接口权限校验增加列表接收参数，实现同一接口支持多个权限标识校验。
2.新增按角色校验接口权限依赖

### BUG修复

1.修复用户管理和部门管理模块数据权限异常的问题。

### 代码及性能优化

1.调整参数设置、部门管理、字典管理、定时任务、日志管理、角色管理、菜单管理模块部分接口权限标识。

## RuoYi-Vue3-FastAPI v1.0.1

### 项目依赖

#### 后端

1.更新fastapi版本为0.109.1，修复一些安全性问题，命令：

```bash
pip install fastapi[all]==0.109.1 -i https://mirrors.aliyun.com/pypi/simple/
```

### 新增功能

1.日志管理模块新增字段排序查询。

## RuoYi-Vue3-FastAPI v1.0.0

RuoYi-Vue3-FastAPI第一个版本发布啦！
此版本功能如下：
1.用户管理：用户是系统操作者，该功能主要完成系统用户配置。
2.角色管理：角色菜单权限分配。
3.菜单管理：配置系统菜单，操作权限，按钮权限标识等。
4.部门管理：配置系统组织机构（公司、部门、小组）。
5.岗位管理：配置系统用户所属担任职务。
6.字典管理：对系统中经常使用的一些较为固定的数据进行维护。
7.参数管理：对系统动态配置常用参数。
8.通知公告：系统通知公告信息发布维护。
9.操作日志：系统正常操作日志记录和查询；系统异常信息日志记录和查询。
10.登录日志：系统登录日志记录查询包含登录异常。
11.在线用户：当前系统中活跃用户状态监控。
12.定时任务：在线（添加、修改、删除）任务调度包含执行结果日志。
13.服务监控：监视当前系统CPU、内存、磁盘、堆栈等相关信息。
14.缓存监控：对系统的缓存信息查询，命令统计等。
15.系统接口：根据业务代码自动生成相关的api接口文档。
