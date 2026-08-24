# Smart Finance Platform · 全面优化意见

> 审查范围：后端约 9.3 万行 Python、前端 Vue3 全部 views/utils、Docker 编排、CI 配置。
> 已知且已有专项清单的事项（调度微服务拆分，见《自动分析任务优化清单.md》）不在本文重复展开。

---

## 一、安全问题（P0，建议立即处理）

### 1. JWT secret 硬编码在源码里 —— 最高危

`config/env.py:68` 的 `jwt_secret_key` 默认值是写死的字符串（RuoYi 模板的公开值）。只要部署时漏配 `.env`，任何看过公开模板的人都能伪造任意用户（包括 admin）的 token。更糟的是 `utils/crypto_util.py` 用同一个 secret 派生 Fernet 密钥加密库里的长桥券商凭据——secret 一旦泄露，等于交易账户凭据一起泄露。

建议：默认值改为空字符串，启动时检测到缺失/仍为模板值直接拒绝启动；JWT secret 与凭据加密密钥拆成两个独立配置，支持独立轮换。

### 2. 前端"记住密码"用的是仓库内公开的 RSA 私钥

`ruoyi-fastapi-frontend/src/utils/jsencrypt.js:5-15` 同时硬编码了公钥和**私钥**（RuoYi 示例密钥对，全网皆知），512 位强度。登录页把明文密码用它加密后存 Cookie 30 天（`login.vue:167-227`）——这个"加密"对任何知道私钥的人等于明文。

建议：直接移除该文件和记住密码功能。若产品上必须保留，改用服务端签发的会话级一次性密钥方案，绝不能把私钥放进前端包。

### 3. CORS 全开 + 允许凭证

`middlewares/cors_middleware.py:13` 是 `allow_origins=['*']` 且 `allow_credentials=True`。Starlette 在这种组合下会回显任意 Origin，意味着任意恶意网站都能携带用户凭证跨域调用 API——对一个能下真实订单的交易平台来说不可接受。

建议：改为从环境变量读取的域名白名单；生产环境禁止 `*`。

### 4. Docker 弱口令与数据层端口对外暴露

`docker-compose.my.yml:40`（MySQL root/root）、`:59-60`（Redis 无密码且映射 16379 到宿主）、`docker-compose.pg.yml` 同样问题；`docker-compose.sentiment.yml:248,280` 把 13306/16379 绑到 `0.0.0.0`；Grafana 默认 admin 账号未强制改密（`docker-compose.monitor.yml:29`）；InfluxDB 占位符 `CHANGE_ME_*` 若忘改即生效。

另外 `docker-compose.sentiment.yml:259` 把测试用的 `disable_captcha.sql` 挂进了生产库初始化，同时种子数据里有 admin/admin123——等于生产环境关闭验证码 + 已知默认密码。

建议：所有口令走 `${VAR}` 注入并在启动脚本校验强度；数据层端口只绑 `127.0.0.1` 或干脆去掉 ports 走内部网络；从生产 compose 移除 disable_captcha.sql，首次登录强制改密。

### 5. 其他安全项

- **容器以 root 运行**：三个后端 Dockerfile 均无 USER 指令，建议创建非 root 用户。
- **token 有效期过长**：24 小时 + 每次请求滑动续期（`login_service.py:232-244`）。涉及真金白银的系统建议缩到 2 小时以内，下单等敏感操作加二次确认/重新验密。
- **传输加密实际是关闭状态**：`.env.dockersentiment:145-147` 显式关闭了 transport crypto。既然已经实现了完整机制（RSA-OAEP + AES-GCM + 防重放，实现质量不错），生产应设为 `required`。
- **健康检查命令行带密码**：compose 里 `-p<密码>` 会出现在进程列表，建议改 `--defaults-extra-file`。

---

## 二、后端架构与性能（P1）

### 1. 同步阻塞调用混进 async 路由

事件循环被卡住会让整个 API 进程所有请求排队，这是 FastAPI 服务最常见的隐性性能杀手：

- `module_market/service/heat_eod.py:349-357`：`async def collect_market` 里用 **urllib.urlopen 同步拉多页 HTTP**；
- `module_market/service/tradingview_service.py:156-165`：async 函数里直接调同步 InfluxDB 查询；
- `market_service.py` 中 6 处仍在用废弃的 `asyncio.get_event_loop().run_in_executor` 写法（:262、330、354、367、434、633），与其他地方 `asyncio.to_thread` 风格不一致。

建议：统一用 `asyncio.to_thread()` 或 httpx.AsyncClient 包裹所有同步 IO；顺手清理废弃 API。

### 2. N+1 与串行循环查询

- `market_dao.py:76-87`：upsert 循环逐条 execute，应合并批量；
- `finance_news_service.py:368、409`：每条新闻一次 DB 往返查重；
- `watchlist_service.py:666-679`：批量 AI 分析对每只标的**串行**执行（Influx + 抓取 + LLM），10 只标的就是 10 倍延迟，用 `asyncio.gather` + 信号量限流可显著提速。

### 3. 异常吞没：全仓 324 处 `except Exception`

其中大量是捕获后返回默认值继续跑（如 `factor_service.py:206`、`trade_service.py:394、421`）。最危险的是 `utils/influx_util.py:151-153、263-265`：查询失败一律返回空列表——"行情库挂了"和"确实没数据"不可区分，AI 研判和回测会静默基于空数据输出结论。对金融平台这是会产生错误决策建议的问题。

建议：Influx 层失败必须抛异常或返回明确的错误标记，让上层区分处理；其余吞异常点至少加 loguru 记录并收敛为自定义异常体系。

### 4. 缓存策略缺陷

- **无负缓存**：`longbridge_service.py:1122` 只在结果非空时写缓存，券商返回空时每次请求穿透到 Longbridge API（有触发限频的风险）；
- quote 缓存 key 把全部 symbol 排序拼接（`:1107`），不同组合各生成 key 无法复用，建议按 symbol 粒度缓存再聚合；
- `BOARD_QUOTES_TTL_SECONDS = 24h`（market_service.py:39）：看板行情缓存一天，盘中看板滞后一天不可接受，建议盘中 30-60 秒、盘后放宽。

### 5. 数据库连接余量不足

API 引擎池 pool_size=50 + overflow=10，调度器又自建一套 engine（`get_scheduler.py:521-524`），同进程理论上限约 120 连接，已逼近 MySQL 默认 max_connections=151。叠加《自动分析任务优化清单》里计划拆出的调度进程，连接数还要翻倍。

建议：调高 MySQL max_connections 的同时给两个引擎池降容（比如 20+10），或引入连接池中间件；另外 service 层散落的 `query_db.commit()`（trade_service.py:222 等）事务边界不清，下单流程中的通知提交可能连带提交未预期变更，建议收敛事务边界。

### 6. InfluxDB 查询习惯

客户端已是全局单例（好），但 `latest_date` 用 `range(start: 0)` 全历史扫描只为取最新一条（influx_util.py:274-281），`query_klines` 默认拉两年数据无 limit。建议 `latest_date` 改用 `last()` 或反向 range + limit 1；kline 查询统一加合理 limit。

### 7. 核心业务零测试覆盖

tests/ 有 58 个文件但其中 40 个测的是 CLI 工具；**trade_service（下单/撤单/回测，822 行）和 market_service 主体没有任何测试**。对一个会碰实盘交易的系统，风控规则、下单链路、止损监控这些恰恰是最该有单元测试的地方。建议优先补：下单前置校验、风控规则匹配、止损计算、AI 分析对空数据的容错行为。同时在 pyproject.toml 加 pytest-cov 并把覆盖率门槛加进 CI。

### 8. 重复代码收敛

`market_service.py:720-742` 与 `trade_service.py:141-163` 有逐行相同的报价构造函数；标的代码规范化逻辑散落 4 处实现 + 30 多处裸 `.strip().upper()`；HTTP 拉取有 urllib/httpx 双实现。建议抽公共模块（symbol 规范化、quote 构造、HTTP client），这类重复在金融场景里容易演化成"两处逻辑不一致"的事故。

---

## 三、前端优化（P1~P2）

### 1. 首屏体积：ECharts 全量引入 + 无分包

ECharts 在 12 处 `import * as echarts`（kline、trading、useEChart 等），加上 Element Plus 全量、katex/mermaid/shiki 这些重依赖，首屏 bundle 相当可观。建议：改 `echarts/core` 按需注册图表类型；vite.config.js 加 manualChunks 按 element-plus / echarts / mermaid / monaco 手动分包；删掉 `chunkSizeWarningLimit: 2000` 这个"掩耳盗铃"配置让构建真正暴露大包。

### 2. 千行级组件拆分

`views/ai/chat/index.vue`（1335 行，约 40 个函数）、`monitor/transportCrypto/index.vue`（1034 行）、`tool/build/RightPanel.vue`（905 行）、`system/user/index.vue`（901 行）都是 UI + 业务 + 状态混杂。chat 页可拆 `useChatStream` / `useAutoScroll` composable 和消息子组件。好消息是定时器清理和 ECharts dispose 都做对了，没有泄漏。

### 3. 轮询请求不可取消

request.js 全局没有封装 AbortController（仅 ai/chat 一处局部用了），行情轮询类页面切走后旧请求仍会返回触发 setState。建议在 request 层支持传入 signal，路由离开时 abort。

### 4. 工程规范缺失

整个前端**没有 ESLint/Prettier/.editorconfig**，86 个 view 全是 `<script setup>`（风格统一，很好），但没有 lint 意味着风格靠自觉。建议补 ESLint(flat config) + Prettier + husky pre-commit，CI 加 lint job。另外 katex/mermaid/shiki 用 `>=` 浮动版本号，建议锁定以保证构建可复现。

---

## 四、依赖瘦身（P2）

requirements.txt 里同时装了 **12 个 LLM SDK**（agno、anthropic、cerebras、cohere、google-genai、groq、litellm、llama-api-client、mistralai、ollama、openai、portkey）。每个都是几十 MB 级依赖树，拖慢构建、扩大漏洞面，而且项目已有 litellm 这一层聚合网关。建议评估：保留 litellm 作为唯一出口，其余按需做成 extras（`pip install .[groq]`），基础镜像体积预计能砍掉一大块。

---

## 五、仓库卫生与 CI（P2）

1. **根目录的生产数据备份**：`_mac_influx_bak/`（969 个文件）、`_mac_readmodel.sql`、`_mac_sync.sql` 等 6 个文件共约 10MB 的数据库 dump/备份躺在仓库根目录。目前 git 未跟踪，但它们包含真实业务库结构数据，一次手滑 `git add -A` 就可能进版本库。建议移出仓库目录，或至少立刻加入 .gitignore。
2. **约 30 个文件长期未提交**：git status 显示 market/quant/trade 多个模块改动悬在工作区，时间久了容易丢或和新提交冲突，建议尽快分批提交。
3. **CI 覆盖面太窄**：现在只有后端 pytest 和 desktop 一个 node 内联断言。建议补：前端 build + lint job、ruff check（配置文件已存在但 CI 没跑它）、pytest-cov 覆盖率报告。
4. **Python 版本漂移**：CI 用 3.12，本地 .venv 是 3.14，建议在 pyproject.toml 声明 `requires-python` 并统一 CI 与本地版本，避免"本地好好的上线就炸"。

---

## 六、落地顺序建议

| 阶段 | 内容 | 理由 |
|------|------|------|
| 本周 | 安全五项：JWT secret 启动校验、CORS 白名单、jsencrypt 移除、compose 口令/端口、移除 disable_captcha.sql | 改动小、风险收益比最高 |
| 两周 | 异常吞没治理（先 Influx 层）+ async 阻塞点修复 + 行情缓存 TTL | 直接影响研判/回测正确性和接口延迟 |
| 一个月 | 下单/风控链路补测试 + CI 扩展 + 依赖瘦身 | 为后续迭代兜底 |
| 持续 | 组件拆分、N+1 批量化、重复代码收敛 | 随迭代顺路做 |

---

*审查基于当前工作区代码状态（2026-08-22），行号以当日文件为准。*
