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
  return {
    availableCash: 326800,
    currency: 'HKD',
    netAssets: 1284500,
    marketValue: 957700,
    todayPnl: 12480,
    todayPnlPct: 1.32,
    totalUnrealizedPnl: 48620,
    totalUnrealizedPnlPct: 5.35,
    positionRatio: 0.746,
    accountName: 'HKD 主账户'
  }
}

export function stubOrders() {
  return [
    { id: 'o-1', orderId: 'ORD-700-093112', symbol: '00700', stockName: '腾讯控股', name: '腾讯控股', market: 'HK', side: 'BUY', quantity: 100, price: 410.2, status: 'pending', statusLabel: '待成交', orderType: 'LO', submittedAt: '09:31:12', open: true },
    { id: 'o-2', orderId: 'ORD-AAPL-092845', symbol: 'AAPL', stockName: '苹果', name: '苹果', market: 'US', side: 'SELL', quantity: 20, price: 229.0, status: 'filled', statusLabel: '已成交', orderType: 'LO', submittedAt: '09:28:45', executedQuantity: 20, executedPrice: 229.0, open: false },
    { id: 'o-3', orderId: 'ORD-300750-091502', symbol: '300750', stockName: '宁德时代', name: '宁德时代', market: 'CN', side: 'BUY', quantity: 100, price: 196.5, status: 'partial_filled', statusLabel: '部分成交', orderType: 'LO', submittedAt: '09:15:02', executedQuantity: 40, executedPrice: 196.5, open: true },
    { id: 'o-4', orderId: 'ORD-9988-090802', symbol: '09988', stockName: '阿里巴巴-SW', name: '阿里巴巴-SW', market: 'HK', side: 'SELL', quantity: 200, price: 86.15, status: 'filled', statusLabel: '已成交', orderType: 'LO', submittedAt: '09:08:02', executedQuantity: 200, executedPrice: 86.15, open: false },
    { id: 'o-5', orderId: 'ORD-TSLA-085512', symbol: 'TSLA', stockName: '特斯拉', name: '特斯拉', market: 'US', side: 'BUY', quantity: 10, price: 248.4, status: 'rejected', statusLabel: '已拒绝', orderType: 'LO', submittedAt: '08:55:12', remark: '资金不足', open: false },
    { id: 'o-6', orderId: 'ORD-3888-084410', symbol: '03888', stockName: '金山软件', name: '金山软件', market: 'HK', side: 'BUY', quantity: 500, price: 32.8, status: 'cancelled', statusLabel: '已撤销', orderType: 'LO', submittedAt: '08:44:10', open: false },
    { id: 'o-7', orderId: 'ORD-5-083302', symbol: '00005', stockName: '汇丰控股', name: '汇丰控股', market: 'HK', side: 'SELL', quantity: 400, price: 68.45, status: 'filled', statusLabel: '已成交', orderType: 'MO', submittedAt: '08:33:02', executedQuantity: 400, executedPrice: 68.45, open: false },
    { id: 'o-8', orderId: 'ORD-600519-082118', symbol: '600519', stockName: '贵州茅台', name: '贵州茅台', market: 'CN', side: 'BUY', quantity: 10, price: 1482.0, status: 'filled', statusLabel: '已成交', orderType: 'LO', submittedAt: '08:21:18', executedQuantity: 10, executedPrice: 1482.0, open: false }
  ]
}

export function stubRiskAlerts() {
  return [
    { id: 'ra-1', level: 'warn', title: '单票集中度接近上限', body: '00700 腾讯控股 市值占比 32.4% · 单票上限 30%', time: '10:21:08', createTime: '10:21:08' },
    { id: 'ra-2', level: 'info', title: '日亏监控正常', body: '今日盈亏 +1.32% · 日亏限额 −5.00%', time: '09:45:00', createTime: '09:45:00' },
    { id: 'ra-3', level: 'danger', title: '杠杆偏高', body: '仓位 74.6% · 建议控制新增开仓', time: '09:12:33', createTime: '09:12:33' }
  ]
}

export function stubNotifications() {
  return [
    { id: 'n-1', title: '委托已提交', content: '00700 腾讯控股 买入 100 股 @ 410.20 已报入', level: 'info', category: 'trade', read: false, createTime: '09:31:12' },
    { id: 'n-2', title: '部分成交', content: '300750 宁德时代 已成交 40 / 100 @ 196.50', level: 'success', category: 'trade', read: false, createTime: '09:16:40' },
    { id: 'n-3', title: '单票集中度预警', content: '00700 市值占比接近 30% 上限，请关注风控规则 v0.2', level: 'warning', category: 'risk', read: false, createTime: '10:21:08' },
    { id: 'n-4', title: '系统维护', content: '行情快照通道将于 16:00 进行例行巡检，终端不受影响', level: 'info', category: 'system', read: true, createTime: '08:05:00' },
    { id: 'n-5', title: '卖出已成交', content: 'AAPL 苹果 卖出 20 股 @ 229.00 全部成交', level: 'success', category: 'trade', read: true, createTime: '09:28:51' }
  ]
}

export function stubPositions() {
  return [
    { symbol: '00700', symbolName: '腾讯控股', name: '腾讯控股', market: 'HK', quantity: 400, costPrice: 406, currentPrice: 412.6, last: 412.6, pnl: 2640, pnlRate: 1.62, pnlPct: 1.62, currency: 'HKD' },
    { symbol: '300750', symbolName: '宁德时代', name: '宁德时代', market: 'CN', quantity: 200, costPrice: 194.16, currentPrice: 198.32, last: 198.32, pnl: 832, pnlRate: 2.14, pnlPct: 2.14, currency: 'CNY' },
    { symbol: 'AAPL', symbolName: '苹果', name: '苹果', market: 'US', quantity: 20, costPrice: 229.24, currentPrice: 228.14, last: 228.14, pnl: -22, pnlRate: -0.48, pnlPct: -0.48, currency: 'USD' }
  ]
}
