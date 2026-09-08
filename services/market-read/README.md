# market-read (Go)

低内存行情 **热读 + 行情 WS** 微服务，承接 nginx 热路径，与 Python `sentiment-data`（slim）/ `sentiment-market`（full）写路径/量化并存。

## 职责

| 路径 | 数据源 | 说明 |
|------|--------|------|
| `GET /market/kline` | Influx | 日/周/月/分时/分钟 K，与 Python `kline_period` 对齐 |
| `GET /market/board/quotes` | Redis → scheduled 降级 | 看板批量报价 |
| `GET /market/heat/daily` | MySQL + Redis 补 last | 热度 + Top50 |
| `GET /market/heat/trend` | MySQL | 近 N 日热度趋势 |
| `GET /market/heat/dates` | MySQL | 可选交易日 |
| `GET /market/heat/config` | Redis sys_config | 权重与市场元数据 |
| `GET /market/index/quotes` | Redis 30s → 未命中则腾讯 qt.gtimg.cn | 三市场指数条；本服务自己回填缓存 |
| `GET /market/symbols/{symbol}/history` | Influx | 历史日 K 快捷接口 |
| `GET /market/quotes/live` | 腾讯 + Redis 5s | 个股快照，最多 80 只；FE 契约与 Python 相同 |
| `WS /ws/market/quotes` | 同上 | Cookie `Admin-Token` 或开帧 `{type:auth,token}`；`channel=index` / `channel=quotes` |

**不在本服务**：自选 CRUD、AI SSE、同步入队、`/quant/`、长桥 `QuoteContext` 推送。详见 [SENTIMENT-DATA-OFFLOAD.md](../../docs/SENTIMENT-DATA-OFFLOAD.md)。

Go WS **不接长桥 SDK**（P1 范围）。个股推送间隔与 FE `interval`（默认 15s）对齐，腾讯补价；没有 Python `QuoteSubscribeHub` 的推送提前唤醒。

## 运行

```bash
cd services/market-read
go test ./...
go run ./cmd/market-read
```

环境变量与 `ruoyi-fastapi-backend/.env.dockersentiment` 一致（`JWT_*`、`DB_*`、`REDIS_*`、`INFLUX_*`）。

Docker（compose 服务名 `sentiment-market-read`）：

```bash
docker compose -f docker-compose.sentiment.yml up -d --no-deps --build sentiment-market-read
```

## 路由开关

nginx（`nginx.dockersentiment.conf` 与 slim 的 `nginx.dockersentiment.slim.conf`）将上表路径 **默认** 代理到 `:8080`。

回退 Python：把对应 `proxy_pass` 改回 `http://sentiment-market:9099/...`（full）或 `http://sentiment-data:9099/...`（slim）并 reload 前端容器。`/ws/` catch-all 仍指向 Python，只改 `/ws/market/quotes` 即可回退行情通道。

## 验证清单

- [ ] `curl -sf http://127.0.0.1:8080/health`（容器内）
- [ ] 登录后 `GET /prod-api/market/kline?symbol=AAPL&period=daily` 返回 `{code:200, data.klines:[...]}`
- [ ] `GET /prod-api/market/heat/daily?market=US` Top50 非空（有采集数据时）
- [ ] `GET /prod-api/market/board/quotes` 命中 Redis 或 scheduled 降级
- [ ] `GET /prod-api/market/index/quotes` 与迁移前 JSON 形状一致（`items[].symbol` 为腾讯代码）
- [ ] `GET /prod-api/market/quotes/live?symbols=AAPL:US` 返回 `{items, asOf, source}`
- [ ] 浏览器顶栏指数条 / 自选 WS：`channel=index` 与 `channel=quotes` 仍工作
- [ ] 无 token 返回 `code:401`（HTTP 200 信封）；WS 失败关 `4401`
- [ ] `docker stats sentiment-market-read` RSS 低于 320m `mem_limit`

## 内存目标

静态链接二进制 + compose `mem_limit` **320m**（WS + 腾讯 HTTP）；无 pandas / FastAPI。
