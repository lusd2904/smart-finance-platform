# 舆情大盘 Widget API

只读聚合接口，供 macOS Widget、Scriptable、Swift 等本地客户端拉取 `/sentiment/dashboard` 页面所需的全部数据。

## 端点

| 项 | 值 |
|---|---|
| 生产 URL | `https://sfp.luapi.top/prod-api/sentiment/widget/dashboard` |
| 方法 | `GET` |
| 鉴权 Header | `X-Widget-Token: <token>` |
| 环境变量 | `SENTIMENT_WIDGET_TOKEN`（部署在 `sentiment-news` 容器；空则接口关闭） |

可选查询参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `trendLimit` | `24` | 趋势点数，最大 `100` |

## 示例

```bash
curl -sS \
  -H "X-Widget-Token: $SENTIMENT_WIDGET_TOKEN" \
  "https://sfp.luapi.top/prod-api/sentiment/widget/dashboard?trendLimit=24"
```

成功时返回 RuoYi 标准信封 `{ "code": 200, "msg": "...", "data": { ... } }`，`data` 为 camelCase。

## 响应字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `updatedAt` | string | 最新分析北京时间；无数据时为当前北京时间 |
| `stats.total` | int | 舆情资讯总数 |
| `stats.today` | int | 今日新增资讯数 |
| `stats.unanalyzed` | int | 待分析资讯数 |
| `markets` | array | 三大市场卡片，顺序：美股 / 港股 / A股 |
| `markets[].key` | string | `us` / `hk` / `a` |
| `markets[].name` | string | 展示名称 |
| `markets[].direction` | string | 原始方向文案（如「利多」） |
| `markets[].directionNorm` | string | 归一化方向：`up` / `down` / `flat` |
| `markets[].score` | number \| null | 影响分数 |
| `markets[].reason` | string | 影响理由 |
| `summary` | string | 最新分析摘要 |
| `riskEvents` | string[] | 风险事件列表（已按页面逻辑解析） |
| `latest` | object | 最新成功分析记录（调试用，含 `analysisId`、`createTime`、各市场分数/方向/理由、`modelName` 等） |
| `trend` | array | 最近 N 次分析分数趋势，**由旧到新** |
| `trend[].createTime` | string | 分析时间（北京时间 `YYYY-MM-DD HH:MM:SS`） |
| `trend[].usScore` | number \| null | 美股分数 |
| `trend[].hkScore` | number \| null | 港股分数 |
| `trend[].aScore` | number \| null | A股分数 |
| `indexes` | array | 盘中大盘指数条（与 `/market/index/quotes` 的 `items` 一致）；**空数组时客户端应隐藏指数条** |
| `indexes[].market` | string | 市场：`US` / `HK` / `CN` |
| `indexes[].symbol` | string | 腾讯行情代码（如 `usINX`、`sh000001`） |
| `indexes[].name` | string | 指数名称 |
| `indexes[].last` | number \| null | 最新价 |
| `indexes[].prevClose` | number \| null | 昨收 |
| `indexes[].changePct` | number \| null | 涨跌幅（%） |
| `indexes[].quoteTime` | string | 行情时间戳（上游原始格式） |
| `indexesAsOf` | string | 指数数据快照时间（`YYYY-MM-DD HH:MM:SS`） |
| `indexesCached` | boolean | 是否来自 Redis 缓存（后端 30s TTL） |
| `sessions` | object | 三市场开盘状态，键为 `US` / `HK` / `CN` |
| `sessions.<M>.market` | string | 市场代码 |
| `sessions.<M>.open` | boolean | 是否处于交易时段 |
| `sessions.<M>.localTime` | string | 当地当前时间 |
| `sessions.<M>.timezone` | string | IANA 时区名 |

## 错误

| 场景 | `msg` 示例 |
|---|---|
| 未配置 token | `未配置 SENTIMENT_WIDGET_TOKEN，舆情大盘 Widget 接口未开启` |
| token 错误 | `Widget 令牌无效` |

## 部署

1. 在仓库根目录 `.env` 或 `ruoyi-fastapi-backend/.env.dockersentiment` 中设置：

   ```env
   SENTIMENT_WIDGET_TOKEN=openssl_rand_hex_32
   ```

2. 重启 `sentiment-news` 服务（`APP_MODULE=sentiment` 已包含本路由，**无需改 nginx**）。

## CORS

浏览器类 Widget 若遇跨域，可在服务端配置 `APP_CORS_ORIGINS`；本接口成功响应额外携带 `Access-Control-Allow-Origin: *`。Scriptable / 原生 macOS 网络请求通常不受浏览器 CORS 限制。
