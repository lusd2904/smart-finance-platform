/**
 * Local mock for /m H5 self-test when the FastAPI stack is not running.
 * Mirrors the existing camelCase contract. Not used in production.
 *
 *   node scripts/mobile-h5-mock.mjs
 *   npm run dev -- --port 5173 --host
 *   open http://127.0.0.1:5173/?m=1   (login admin / admin123)
 */
import http from 'node:http'

const PORT = Number(process.env.MOBILE_MOCK_PORT || 9099)

function send(res, body, status = 200) {
  const json = JSON.stringify(body)
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type, repeatSubmit, isToken, encrypt, encryptResponse',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
  })
  res.end(json)
}

function readBody(req) {
  return new Promise((resolve) => {
    const chunks = []
    req.on('data', (c) => chunks.push(c))
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')))
  })
}

function parseUrl(req) {
  const u = new URL(req.url, 'http://127.0.0.1')
  return { path: u.pathname, query: Object.fromEntries(u.searchParams) }
}

const heatRow = (rankNo, symbol, name, last, changePct, inWatchlist = false) => ({
  rankNo, symbol, name, last, changePct, inWatchlist, marketCap: last * 1e8, turnover: last * 1e7
})

const klines = (n, base, intra = false) => {
  const out = []
  let close = base
  for (let i = 0; i < n; i++) {
    const open = close
    close = +(open + (i % 3 === 0 ? 0.4 : -0.25)).toFixed(2)
    const high = Math.max(open, close) + 0.3
    const low = Math.min(open, close) - 0.3
    const volume = 1000000 + i * 1000
    const date = intra
      ? `09:${String(30 + (i % 30)).padStart(2, '0')}`
      : `2026-08-${String((i % 28) + 1).padStart(2, '0')}`
    out.push({ date, open, high, low, close, volume, turnover: +(volume * close).toFixed(2) })
  }
  return out
}

const UNIVERSE = [
  { symbol: 'AAPL', name: '苹果', market: 'US' },
  { symbol: 'NVDA', name: '英伟达', market: 'US' },
  { symbol: 'TSLA', name: '特斯拉', market: 'US' },
  { symbol: 'MSFT', name: '微软', market: 'US' },
  { symbol: '0700', name: '腾讯控股', market: 'HK' },
  { symbol: '9988', name: '阿里巴巴', market: 'HK' },
  { symbol: '600519', name: '贵州茅台', market: 'CN' },
  { symbol: '000858', name: '五粮液', market: 'CN' }
]

let nextWatchId = 4
let watchItems = [
  { id: 1, symbol: 'AAPL', name: '苹果', market: 'US', last: 226.4, changeRate: 1.35, groups: ['科技'], note: '科技', stance: '偏多' },
  { id: 2, symbol: '0700', name: '腾讯控股', market: 'HK', last: 382.6, changeRate: 0.8, groups: ['科技'], note: '科技', stance: '中性' },
  { id: 3, symbol: '600519', name: '贵州茅台', market: 'CN', last: 1488.2, changeRate: -0.6, groups: ['消费'], note: '消费', stance: '偏空' }
]

function parseNoteGroups(note) {
  return String(note || '').split(/[,，]/).map((s) => s.trim()).filter(Boolean)
}

function watchOverview() {
  const groupCounts = {}
  let bullish = 0
  let bearish = 0
  let neutral = 0
  for (const row of watchItems) {
    for (const g of row.groups || []) groupCounts[g] = (groupCounts[g] || 0) + 1
    if (row.stance === '偏多') bullish += 1
    else if (row.stance === '偏空') bearish += 1
    else neutral += 1
  }
  return {
    count: watchItems.length,
    bullish,
    bearish,
    neutral,
    groups: Object.entries(groupCounts).map(([name, count]) => ({ name, count })),
    items: watchItems
  }
}

function parseJson(body) {
  try {
    return JSON.parse(body || '{}')
  } catch {
    return {}
  }
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') {
    send(res, { code: 200 })
    return
  }
  const { path, query } = parseUrl(req)
  const body = req.method === 'POST' || req.method === 'PUT' ? await readBody(req) : ''

  if (path === '/captchaImage') {
    send(res, { code: 200, captchaEnabled: false, registerEnabled: false, img: '', uuid: 'mock-uuid' })
    return
  }
  if (path === '/login') {
    const params = new URLSearchParams(body)
    const username = params.get('username') || ''
    if (!username) {
      send(res, { code: 500, msg: '请输入账号' })
      return
    }
    send(res, { code: 200, token: 'mock-admin-token', msg: '登录成功' })
    return
  }
  if (path === '/logout') {
    send(res, { code: 200, msg: '退出成功' })
    return
  }
  if (path === '/getInfo') {
    send(res, {
      code: 200,
      user: { userId: 1, userName: 'admin', nickName: '管理员' },
      roles: ['admin'],
      permissions: ['*:*:*']
    })
    return
  }
  if (path === '/getRouters') {
    send(res, { code: 200, data: [] })
    return
  }
  if (path === '/market/index/quotes') {
    send(res, {
      code: 200,
      data: {
        items: [
          { symbol: 'usINX', name: '标普500', market: 'US', last: 5621.3, changePct: 0.42, indexName: '标普500', indexChangePct: 0.42 },
          { symbol: 'usIXIC', name: '纳斯达克', market: 'US', last: 17802.1, changePct: -0.18, indexName: '纳斯达克', indexChangePct: -0.18 },
          { symbol: 'r_hkHSI', name: '恒生指数', market: 'HK', last: 17620.4, changePct: 1.02, indexName: '恒生指数', indexChangePct: 1.02 },
          { symbol: 'sh000001', name: '上证指数', market: 'CN', last: 3128.5, changePct: -0.33, indexName: '上证指数', indexChangePct: -0.33 }
        ]
      }
    })
    return
  }
  if (path === '/market/heat/daily') {
    const market = (query.market || 'US').toUpperCase()
    const rows = market === 'CN'
      ? [heatRow(1, '600519', '贵州茅台', 1488.2, 1.2, true), heatRow(2, '000858', '五粮液', 128.4, -0.6)]
      : market === 'HK'
        ? [heatRow(1, '0700', '腾讯控股', 382.6, 0.8), heatRow(2, '9988', '阿里巴巴', 88.1, -1.1, true)]
        : [heatRow(1, 'AAPL', '苹果', 226.4, 1.35, true), heatRow(2, 'NVDA', '英伟达', 118.2, -0.42), heatRow(3, 'TSLA', '特斯拉', 241.0, 2.1)]
    send(res, {
      code: 200,
      data: {
        heat: {
          heatScore: 72,
          advanceCount: 312,
          declineCount: 188,
          totalTurnover: 1.28e12,
          asOfTime: '2026-09-05 12:00:00',
          indexName: market === 'CN' ? '上证指数' : market === 'HK' ? '恒生指数' : '标普500',
          indexChangePct: 0.42
        },
        top50: rows
      }
    })
    return
  }
  if (path === '/market/watchlist/overview') {
    send(res, { code: 200, data: watchOverview() })
    return
  }
  if (path === '/market/watchlist/list') {
    send(res, { code: 200, rows: watchItems, total: watchItems.length })
    return
  }
  if (path === '/market/instrument/universe') {
    const kw = String(query.keyword || '').trim().toLowerCase()
    const rows = UNIVERSE.filter((r) => {
      if (!kw) return true
      return `${r.symbol} ${r.name}`.toLowerCase().includes(kw)
    }).map((r) => ({ ...r, last: r.symbol === 'AAPL' ? 226.4 : 100, changeRate: 0.5 }))
    send(res, { code: 200, rows, total: rows.length })
    return
  }
  if (path === '/market/watchlist' && req.method === 'POST') {
    const payload = parseJson(body)
    const symbol = String(payload.symbol || '').toUpperCase()
    const market = String(payload.market || 'US').toUpperCase()
    const note = payload.note || ''
    const groups = parseNoteGroups(note)
    const hit = watchItems.find((r) => r.symbol === symbol && r.market === market)
    if (!hit && symbol) {
      const meta = UNIVERSE.find((r) => r.symbol === symbol) || { name: symbol }
      watchItems.push({
        id: nextWatchId++,
        symbol,
        name: meta.name || symbol,
        market,
        last: 100,
        changeRate: 0,
        groups,
        note,
        stance: '中性'
      })
    }
    send(res, { code: 200, msg: '已加入自选' })
    return
  }
  if (path.startsWith('/market/watchlist/') && req.method === 'DELETE') {
    const ids = decodeURIComponent(path.slice('/market/watchlist/'.length)).split(',').filter(Boolean)
    watchItems = watchItems.filter((r) => !ids.includes(String(r.id)))
    send(res, { code: 200, msg: '已删除' })
    return
  }
  if (path.startsWith('/market/symbols/') && path.endsWith('/overview')) {
    const symbol = decodeURIComponent(path.split('/')[3] || 'AAPL')
    const meta = UNIVERSE.find((r) => r.symbol === symbol)
    send(res, {
      code: 200,
      data: {
        symbol,
        name: meta ? meta.name : symbol,
        market: query.market || (meta && meta.market) || 'US',
        quote: {
          last: 226.4,
          changePct: 1.35,
          changeRate: 1.35,
          open: 224.1,
          high: 227.8,
          low: 223.5,
          close: 226.4,
          prevClose: 223.4,
          volume: 5.2e7
        }
      }
    })
    return
  }
  if (path === '/trade/quote/snapshot') {
    send(res, {
      code: 200,
      data: {
        symbol: query.symbol || 'AAPL',
        market: query.market || 'US',
        last: 226.4,
        open: 224.1,
        high: 227.8,
        low: 223.5,
        prevClose: 223.4,
        volume: 5.2e7,
        turnover: 1.17e10,
        marketCap: 3.4e12,
        peTtm: 34.2,
        pb: 52.1,
        turnoverRate: 0.42,
        amplitude: 1.92,
        avgPrice: 225.1,
        volumeRatio: 0.88,
        high52: 260.1,
        low52: 169.2,
        beta: 1.12,
        dividendYield: 0.45
      }
    })
    return
  }
  if (path === '/market/kline') {
    const period = query.period || 'daily'
    const intra = period === 'intraday'
    const n = period === 'monthly' ? 16 : period === 'weekly' ? 24 : intra ? 60 : 40
    send(res, { code: 200, data: { symbol: query.symbol, market: query.market, period, klines: klines(n, 220, intra) } })
    return
  }
  if (path === '/sentiment/analysis/list') {
    send(res, {
      code: 200,
      rows: [{
        analysisId: 1,
        summary: '美股风险偏好回升，港股跟随科技反弹，A股成交偏弱。',
        usDirection: '利多',
        usScore: 4.2,
        hkDirection: '中性',
        hkScore: 0.6,
        aDirection: '利空',
        aScore: -2.1,
        riskEvents: '["地缘扰动","利率预期反复","汇率波动"]'
      }],
      total: 1
    })
    return
  }
  if (path === '/market/finance/briefings') {
    send(res, {
      code: 200,
      data: {
        data: [
          { id: 1, headline: '美联储官员释放谨慎信号', summary: '市场消化降息节奏，纳指高位震荡，科技股分化明显，短线仍看美债收益率与美元指数。', sourceName: '财经社', generatedAt: '2026-09-05 10:20:00', market: 'US', symbols: ['AAPL'], payload: { symbol: 'AAPL' } },
          { id: 2, headline: '港股科技股获资金回流', summary: '南向资金净流入，腾讯阿里走强。', sourceName: '港交所快讯', generatedAt: '2026-09-05 09:10:00', market: 'HK', symbols: ['0700'], payload: { symbol: '0700' } }
        ],
        meta: { count: 2 }
      }
    })
    return
  }
  if (path === '/market/picks/latest') {
    const market = (query.market || '').toUpperCase()
    const all = [
      { symbol: 'AAPL', name: '苹果', market: 'US', pickScore: 0.86, stance: '偏多', recommendation: '买入', summary: '业绩与回购支撑', last: 226.4, changePct: 1.35 },
      { symbol: '0700', name: '腾讯控股', market: 'HK', pickScore: 0.71, stance: '中性', recommendation: '观望', summary: '游戏与广告稳健', last: 382.6, changePct: 0.8 },
      { symbol: '600519', name: '贵州茅台', market: 'CN', pickScore: 0.64, stance: '谨慎', recommendation: '减持', summary: '估值偏高', last: 1488.2, changePct: -0.6 }
    ]
    const items = market ? all.filter((r) => r.market === market) : all
    send(res, { code: 200, data: { items, tradeDate: '2026-09-04', empty: items.length === 0 } })
    return
  }
  if (path === '/trade/account') {
    send(res, {
      code: 200,
      data: {
        configured: true,
        currency: 'USD',
        netAssets: 125000,
        availableCash: 32000,
        balances: [
          { currency: 'USD', netAssets: 80000, availableCash: 20000, totalCash: 22000 },
          { currency: 'HKD', netAssets: 351000, availableCash: 93600, totalCash: 94000 }
        ]
      }
    })
    return
  }
  if (path === '/trade/positions') {
    send(res, {
      code: 200,
      data: {
        configured: true,
        positions: [
          { symbol: 'AAPL.US', symbolName: '苹果', quantity: 50, availableQuantity: 50, costPrice: 210.2, last: 226.4, prevClose: 223.4, currency: 'USD' },
          { symbol: '0700.HK', symbolName: '腾讯控股', quantity: 200, availableQuantity: 200, costPrice: 360, last: 382.6, prevClose: 379.4, currency: 'HKD' }
        ]
      }
    })
    return
  }
  if (path === '/trade/order' && req.method === 'POST') {
    send(res, { code: 200, data: { ok: true, orderId: 'M-1001', message: '已提交委托' } })
    return
  }

  send(res, { code: 404, msg: `mock miss ${req.method} ${path}` }, 404)
})

server.listen(PORT, '127.0.0.1', () => {
  console.log(`mobile H5 mock listening on http://127.0.0.1:${PORT}`)
})
