# market-read (Go)

低内存行情 **只读** 微服务，承接 nginx 热路径，与 Python `sentiment-market` 写路径/复杂业务并存。

## 职责

| 路径 | 数据源 | 说明 |
|------|--------|------|
| `GET /market/kline` | Influx | 日/周/月/分时/分钟 K，与 Python `kline_period` 对齐 |
| `GET /market/board/quotes` | Redis → scheduled 降级 | 看板批量报价 |
| `GET /market/heat/daily` | MySQL + Redis 补 last | 热度 + Top50 |
| `GET /market/heat/trend` | MySQL | 近 N 日热度趋势 |
| `GET /market/heat/dates` | MySQL | 可选交易日 |
| `GET /market/heat/config` | Redis sys_config | 权重与市场元数据 |
| `GET /market/index/quotes` | Redis | 三市场指数条（由 Python jobs 写入缓存） |
| `GET /market/symbols/{symbol}/history` | Influx | 历史日 K 快捷接口 |

**不在本服务**：`POST /market/heat/collect`、自选/AI/同步/WS 等仍走 `sentiment-market`。

## 运行

```bash
cd services/market-read
go run ./cmd/market-read
```

环境变量与 `ruoyi-fastapi-backend/.env.dockersentiment` 一致（`JWT_*`、`DB_*`、`REDIS_*`、`INFLUX_*`）。

Docker（compose 服务名 `sentiment-market-read`）：

```bash
docker compose -f docker-compose.sentiment.yml up -d --no-deps --build sentiment-market-read
```

## 路由开关

nginx（`ruoyi-fastapi-frontend/bin/nginx.dockersentiment.conf`）将上表路径 **默认** 代理到 `:8080`。
回退 Python：把对应 `proxy_pass` 改回 `http://sentiment-market:9099/...` 并 reload 前端容器。

## 验证清单

- [ ] `curl -sf http://127.0.0.1:8080/health`（容器内）
- [ ] 登录后 `GET /prod-api/market/kline?symbol=AAPL&period=daily` 返回 `{code:200, data.klines:[...]}`
- [ ] `GET /prod-api/market/heat/daily?market=US` Top50 非空（有采集数据时）
- [ ] `GET /prod-api/market/board/quotes` 命中 Redis 或 scheduled 降级
- [ ] `GET /prod-api/market/index/quotes` 与迁移前 JSON 形状一致
- [ ] 无 token 返回 `code:401`（HTTP 200 信封）
- [ ] `docker stats sentiment-market-read` RSS 明显低于 `sentiment-market`

## 内存目标

静态链接二进制 + 256MB compose `mem_limit`；典型 RSS 数十～百余 MB（无 pandas/FastAPI worker）。
