# 智慧金融 Flutter 客户端 · 手机端现状（给设计用）

平台：iOS / Android 手机竖屏（逻辑宽约 390）。桌面 macOS 继续用侧栏，不在本次范围。

## 已落地的壳

- 登录后宽度 < 900：顶栏汉堡 + 抽屉菜单（RuoYi 全量菜单），门户卡片竖排。
- 宽度 ≥ 900：网页同款侧栏 + 页签。
- 登录页已做窄屏顶栏缩放；Android 模拟器网关默认 `10.0.2.2:12580`。
- 交易台窄屏拆成「自选 / K线 / 交易」三段 + 底部盘口。

## 设计稿约束（必须遵守）

来源 `设计稿.md`：

- iOS 底栏 4 Tab：**工作台、行情、自选、我的**（Cupertino 半透明 TabBar）。
- 进出页横向 Push，支持边缘左滑返回。
- 弹窗一律底部抽屉（Grabber 36×4），禁止桌面居中 Dialog。
- 触感：下单 medium、撤单 light、风控 heavy、Segment selectionClick。
- 墨蓝令牌：品牌蓝 `#409EFF`，涨红 `#E5484D`，跌绿 `#30A46C`，深色一等公民。

## 需要逐页出手机布局的页面（按优先级）

1. 底栏信息架构（4 Tab 与抽屉/更多菜单如何分工）
2. 工作台 / 门户 `/portal` `/index`
3. 行情热度 `/market/heat`、行情台 `/market/board`
4. 自选 `/market/watchlist`
5. 标的 K 线 `/market/kline`、全部股票 `/market/stocks`
6. 交易终端 `/trade/terminal`（盘口、下单、量化开关）
7. 持仓/委托 `/trade/positions` `/trade/orders`
8. 舆情大盘 `/sentiment/dashboard`、资讯 `/market/finance-news`
9. 量化策略 `/quant/strategy`、每日清单 `/quant/daily-list`
10. 我的：个人中心、网关、长桥、退出

系统管理 / 监控页手机端可降级为只读列表，不作为首批。

## 现状问题

- 多数业务页仍是桌面 Row + 固定宽表格，在 390 宽会溢出或字号过大。
- 没有 4 Tab 底栏，只有汉堡抽屉。
- 门户标题「量化交易与 AI 研判综合指挥中心」在手机上偏长。
- 交易台顶栏指数条 + 搜索 + LIVE/量化 在窄屏仍挤。

请按页给出：结构草图（从上到下模块）、主手势、必留字段、可收进「更多」的字段、与设计稿 4 Tab 的归属。
