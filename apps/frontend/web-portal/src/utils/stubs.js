import { currencyOf } from './format'

export const useStubs = () => String(import.meta.env.VITE_USE_STUBS || '').toLowerCase() === 'true'

function envBool(name) {
  const raw = import.meta.env[name]
  if (raw === undefined || raw === '') return null
  const v = String(raw).toLowerCase()
  if (['false', '0', 'no', 'off'].includes(v)) return false
  if (['true', '1', 'yes', 'on'].includes(v)) return true
  return null
}

/** Demo/stub chrome. Off unless stub/demo mode. 联调: VITE_SHOW_STUB_BANNER=false */
export function showStubBanner() {
  const show = envBool('VITE_SHOW_STUB_BANNER')
  if (show !== null) return show
  if (envBool('VITE_HIDE_STUB_BANNER') === true) return false
  return true
}

export const hideStubBanner = () => !showStubBanner()

export function stubDashboard() {
  return {
    generatedAt: new Date().toISOString().slice(0, 16).replace('T', ' '),
    cached: true,
    sessions: [
      { market: 'US', status: 'closed', label: '美股', localTime: '22:30', timezone: 'ET' },
      { market: 'HK', status: 'open', label: '港股', localTime: '10:30', timezone: 'HKT' },
      { market: 'CN', status: 'open', label: 'A股', localTime: '10:30', timezone: 'CST' }
    ],
    asset: {
      ok: true,
      data: {
        configured: true,
        currency: 'HKD',
        netAssets: 1284500,
        availableCash: 326800,
        positionCount: 6,
        totalUnrealizedPnl: 18420
      }
    },
    sentiment: {
      ok: true,
      data: {
        latestAnalysis: {
          modelName: 'Grok 4.6',
          createTime: '09:12',
          summary: '港股科技偏强，美股隔夜震荡，A 股情绪中性偏多。注意外盘波动对开盘溢价的传导。',
          usDirection: '中性',
          usScore: 52,
          hkDirection: '偏多',
          hkScore: 68,
          aDirection: '偏多',
          aScore: 61,
          riskEvents: '美债收益率上行可能压制成长股估值。'
        }
      }
    },
    briefings: {
      ok: true,
      data: {
        items: [
          { id: 1, title: '港股通净流入延续，科技权重获配置', time: '09:05', source: '财经简报' },
          { id: 2, title: '美股期货小幅高开，纳指夜盘回吐部分涨幅', time: '08:40', source: '外盘' },
          { id: 3, title: 'A 股成交额回升，北向资金早盘净买', time: '09:20', source: '市场' }
        ]
      }
    },
    heat: {
      ok: true,
      data: {
        US: { tradeDate: '2026-09-05', indexName: '纳指', indexChangePct: 0.42, advanceCount: 312, flatCount: 40, declineCount: 198, totalTurnover: 4.2e11, currency: 'USD', heatScore: 61 },
        HK: { tradeDate: '2026-09-08', indexName: '恒指', indexChangePct: 1.18, advanceCount: 96, flatCount: 12, declineCount: 54, totalTurnover: 1.1e11, currency: 'HKD', heatScore: 74 },
        CN: { tradeDate: '2026-09-08', indexName: '上证', indexChangePct: 0.36, advanceCount: 2100, flatCount: 180, declineCount: 1600, totalTurnover: 8.8e11, currency: 'CNY', heatScore: 58 }
      }
    },
    watchSignals: {
      ok: true,
      data: {
        items: [
          { symbol: '00700', name: '腾讯控股', market: 'HK', changeRate: 1.62, signal: '突破' },
          { symbol: 'AAPL', name: '苹果', market: 'US', changeRate: -0.48, signal: '回踩' },
          { symbol: '300750', name: '宁德时代', market: 'CN', changeRate: 2.14, signal: '放量' }
        ]
      }
    },
    quotes: {
      ok: true,
      data: {
        source: 'cache',
        indices: [
          { symbol: 'HSI', name: '恒生指数', price: 17842.3, changeRate: 1.18 },
          { symbol: 'IXIC', name: '纳斯达克', price: 17620.1, changeRate: 0.42 }
        ],
        quotes: [
          { symbol: '00700', name: '腾讯控股', market: 'HK', price: 412.6, changeRate: 1.62 },
          { symbol: 'AAPL', name: '苹果', market: 'US', price: 228.14, changeRate: -0.48 }
        ]
      }
    },
    health: {
      ok: true,
      data: {
        coverage: { coveragePct: 94, covered: 1880, total: 2000 },
        jobs: { success: 18, fail: 1, lastName: '行情同步', lastTime: '05:32' }
      }
    }
  }
}

export function stubReviews() {
  return [
    { market: 'US', marketLabel: '美股', stance: '中性', tradeDate: '2026-09-05', score: 52, summary: '科技分化，指数窄幅震荡，等待通胀数据。' },
    { market: 'HK', marketLabel: '港股', stance: '偏多', tradeDate: '2026-09-08', score: 71, summary: '南向持续流入，互联网权重带动恒指回升。' },
    { market: 'CN', marketLabel: 'A股', stance: '偏多', tradeDate: '2026-09-08', score: 63, summary: '成交回暖，成长与周期轮动，情绪修复中。' }
  ]
}

export function stubIndices() {
  return [
    { symbol: 'HSI.HK', name: '恒生指数', market: 'HK', price: 17842.3, changeRate: 1.18, sessionStatus: { label: '开市', sessionName: '港股盘中', sessionTag: 'open' } },
    { symbol: 'HSCEI.HK', name: '国企指数', market: 'HK', price: 6421.8, changeRate: 0.92, sessionStatus: { label: '开市', sessionName: '港股盘中', sessionTag: 'open' } },
    { symbol: '000001.SH', name: '上证指数', market: 'CN', price: 3128.4, changeRate: 0.36, sessionStatus: { label: '开市', sessionName: 'A股盘中', sessionTag: 'open' } },
    { symbol: 'IXIC.US', name: '纳斯达克', market: 'US', price: 17620.1, changeRate: 0.42, sessionStatus: { label: '已收盘', sessionName: '美股收盘', sessionTag: 'closed' } }
  ]
}

function spark(seed) {
  return Array.from({ length: 12 }, (_, i) => 100 + Math.sin(seed + i / 2) * 4 + i * 0.3)
}

export function stubWatchlist() {
  return [
    { symbol: '00700', name: '腾讯控股', market: 'HK', category: '互联网', price: 412.6, change: 6.6, changeRate: 1.62, open: 407.2, high: 414.8, low: 406.4, prevClose: 406, volume: 1.8e7, turnover: 7.4e9, groups: ['核心'], sparkline: spark(1) },
    { symbol: 'AAPL', name: '苹果', market: 'US', category: '科技', price: 228.14, change: -1.1, changeRate: -0.48, open: 229.4, high: 230.1, low: 227.6, prevClose: 229.24, volume: 4.2e7, turnover: 9.6e9, groups: ['美股'], sparkline: spark(2) },
    { symbol: '300750', name: '宁德时代', market: 'CN', category: '新能源', price: 198.32, change: 4.16, changeRate: 2.14, open: 195.1, high: 199.8, low: 194.6, prevClose: 194.16, volume: 2.4e7, turnover: 4.7e9, groups: ['核心'], sparkline: spark(3) },
    { symbol: '09988', name: '阿里巴巴-SW', market: 'HK', category: '互联网', price: 86.15, change: 1.05, changeRate: 1.23, open: 85.4, high: 86.7, low: 85.1, prevClose: 85.1, volume: 3.1e7, turnover: 2.6e9, groups: ['核心'], sparkline: spark(4) }
  ].map((s) => ({
    ...s,
    currency: currencyOf(s.market),
    peTTM: 18.4,
    pb: 3.2,
    marketCap: '3.8万亿',
    turnoverRate: '1.2%',
    amplitude: '2.1%',
    volumeRatio: 1.08,
    aiScore: 78,
    aiVerdict: '逢低关注',
    aiSummary: '量价配合良好，舆情偏多，建议控制仓位分批。',
    factors: [
      { name: '动量', score: 82 },
      { name: '估值', score: 71 },
      { name: '舆情', score: 76 }
    ],
    news: [
      { id: 1, title: `${s.name} 获机构上调目标价`, sentiment: 'bull', source: '路透', time: '09:18' },
      { id: 2, title: '板块成交活跃，资金回流成长', sentiment: 'neutral', source: '财经', time: '08:55' }
    ],
    capitalFlow: { superIn: 120, superOut: 80, largeIn: 90, largeOut: 70, midIn: 40, midOut: 55, netInflow: 45 },
    asks: [10, 9, 8, 7, 6, 5, 4, 3, 2, 1].map((level) => ({ level, price: s.price + level * 0.05, volume: 800 + level * 120, percent: 30 + level * 4 })),
    bids: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((level) => ({ level, price: s.price - level * 0.05, volume: 900 + level * 80, percent: 28 + level * 5 })),
    trades: [
      { time: '10:21:03', price: s.price, volume: 200, side: 'buy' },
      { time: '10:20:51', price: s.price - 0.05, volume: 500, side: 'sell' },
      { time: '10:20:40', price: s.price, volume: 100, side: 'buy' }
    ],
    high52: s.price * 1.28,
    low52: s.price * 0.72,
    beta: 1.12,
    dividendYield: '0.8%',
    quoteTime: '10:21:08'
  }))
}

export function stubKline(price = 400) {
  const bars = []
  let p = price * 0.94
  for (let i = 0; i < 80; i++) {
    const open = p
    const close = open + (Math.sin(i / 6) * 2 + (i % 5) - 2)
    const high = Math.max(open, close) + 1.2
    const low = Math.min(open, close) - 1.1
    bars.push({
      time: `09:${String(i).padStart(2, '0')}`,
      open,
      high,
      low,
      close,
      volume: 800000 + i * 12000
    })
    p = close
  }
  return bars
}

export function stubAccount() {
  return { availableCash: 326800, currency: 'HKD', netAssets: 1284500 }
}

export function stubOrders() {
  return [
    { id: 'o-1', symbol: '00700', side: 'BUY', quantity: 100, price: 410.2, status: '待成交', open: true },
    { id: 'o-2', symbol: 'AAPL', side: 'SELL', quantity: 20, price: 229.0, status: '已成交', open: false }
  ]
}

export function stubPositions() {
  return [
    { symbol: '00700', quantity: 400, currentPrice: 412.6, pnl: 2640, pnlRate: 1.62 },
    { symbol: '300750', quantity: 200, currentPrice: 198.32, pnl: 832, pnlRate: 2.14 }
  ]
}
