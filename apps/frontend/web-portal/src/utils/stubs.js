import { getToken } from './auth'
import { currencyOf } from './format'

export const useStubs = () => String(import.meta.env.VITE_USE_STUBS || '').toLowerCase() === 'true'

const DEMO_TOKEN = 'demo-stub-token'

/** Demo / VITE_USE_STUBS / demo-stub-token. Live login must never treat empty APIs as stub-ok. */
export function isDemoSession(userStore) {
  if (useStubs()) return true
  if (userStore?.usingStub) return true
  const token = userStore?.token || getToken()
  if (token === DEMO_TOKEN) return true
  try {
    if (typeof sessionStorage !== 'undefined' && sessionStorage.getItem('sfp-demo-session') === '1') return true
  } catch {
    /* ignore */
  }
  return false
}

/** Token present, not demo-stub-token, not demo mode. */
export function isLiveSession(userStore) {
  const token = userStore?.token || getToken()
  return Boolean(token && token !== DEMO_TOKEN && !isDemoSession(userStore))
}

export function errorText(err, fallback = '加载失败') {
  return err?.message || err?.msg || fallback
}

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
    { symbol: 'AAPL', name: '苹果', market: 'US', category: '科技', price: 316.29, last: 316.29, change: -3.68, changeRate: -1.15, open: 318.4, high: 321.1, low: 312.55, prevClose: 319.97, volume: 4.8e7, turnover: 4.82e10, groups: ['核心持仓'], stance: 'wait', recommendation: '观望', aiVerdict: '观望', aiSummary: '近期波动收窄，量能中性；建议等待突破确认后再调仓。可一键跳转分析/回测。', sparkline: spark(2) },
    { symbol: 'NVDA', name: '英伟达', market: 'US', category: '科技', price: 178.42, last: 178.42, change: 4.12, changeRate: 2.36, open: 175.1, high: 179.8, low: 174.2, prevClose: 174.3, volume: 3.6e7, turnover: 6.4e10, groups: ['美股'], stance: 'bull', recommendation: '看多', aiVerdict: '看多', aiSummary: '量价齐升，突破前高后回踩确认，可持有观察。', sparkline: spark(5) },
    { symbol: 'TSLA', name: '特斯拉', market: 'US', category: '汽车', price: 246.1, last: 246.1, change: -4.5, changeRate: -1.8, open: 249.2, high: 251.0, low: 244.8, prevClose: 250.6, volume: 2.1e7, turnover: 5.2e9, groups: ['美股'], stance: 'bear', recommendation: '看空', aiVerdict: '看空', aiSummary: '高位回落，成交放大，短线规避追空。', sparkline: spark(6) },
    { symbol: '00700', name: '腾讯控股', market: 'HK', category: '互联网', price: 412.6, last: 412.6, change: 6.6, changeRate: 1.62, open: 407.2, high: 414.8, low: 406.4, prevClose: 406, volume: 1.8e7, turnover: 7.4e9, groups: ['核心持仓'], stance: 'bull', recommendation: '看多', aiVerdict: '看多', aiSummary: '量价配合良好，舆情偏多，建议控制仓位分批。', sparkline: spark(1) },
    { symbol: '03690', name: '美团-W', market: 'HK', category: '互联网', price: 161.75, last: 161.75, change: -6.45, changeRate: -3.84, open: 166.2, high: 167.1, low: 160.4, prevClose: 168.2, volume: 2.8e7, turnover: 4.5e9, groups: ['核心持仓'], stance: 'bear', recommendation: '看空', aiVerdict: '看空', aiSummary: '浮亏扩大，等待止跌信号。', sparkline: spark(7) },
    { symbol: '300750', name: '宁德时代', market: 'CN', category: '新能源', price: 198.32, last: 198.32, change: 4.16, changeRate: 2.14, open: 195.1, high: 199.8, low: 194.6, prevClose: 194.16, volume: 2.4e7, turnover: 4.7e9, groups: ['核心持仓'], stance: 'bull', recommendation: '看多', aiVerdict: '看多', aiSummary: '板块回流，量能配合，回踩可加。', sparkline: spark(3) },
    { symbol: '09988', name: '阿里巴巴-SW', market: 'HK', category: '互联网', price: 86.15, last: 86.15, change: -0.95, changeRate: -1.09, open: 86.8, high: 87.2, low: 85.6, prevClose: 87.1, volume: 3.1e7, turnover: 2.6e9, groups: ['核心持仓'], stance: 'bear', recommendation: '看空', aiVerdict: '看空', aiSummary: '反弹乏力，等待成交缩量后再议。', sparkline: spark(4) }
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
    aiVerdict: s.aiVerdict || '逢低关注',
    aiSummary: s.aiSummary || '量价配合良好，舆情偏多，建议控制仓位分批。',
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
    { id: 'ra-1', level: 'warn', title: '集中度接近阈值', body: '港股互联网敞口 32%，距 40% 上限 8pp。', time: '10:42' },
    { id: 'ra-2', level: 'info', title: '日亏限额正常', body: '今日浮动亏损占用限额 24.9%，无需干预。', time: '10:15' },
    { id: 'ra-3', level: 'danger', title: '美团浮亏超 3%', body: '03690 持仓浮亏 -3.84%，触发关注阈值。', time: '09:58' },
    { id: 'ra-4', level: 'ok', title: '账户健康度良好', body: '杠杆 1.0×，可用现金充足，无强平风险。', time: '09:30' },
    { id: 'ra-5', level: 'warn', title: '隔夜持仓数提醒', body: '当前 6 只隔夜持仓，建议复核止损。', time: '昨日 16:05' }
  ]
}

export function stubNotifications() {
  return [
    { id: 'n-1', title: '00700 买入委托已挂单', content: '限价 410.20 × 100 股，状态待成交。', category: 'trade', tag: '委托', read: false, createTime: '10:31' },
    { id: 'n-2', title: '美团浮亏超关注阈值', content: '03690 浮亏 -3.84%，已写入风控预警。', category: 'risk', tag: '风控', read: false, createTime: '09:58' },
    { id: 'n-3', title: '长桥行情通道恢复', content: 'HK 实时行情延迟已恢复至 <200ms。', category: 'system', tag: '系统', read: false, createTime: '09:40' },
    { id: 'n-4', title: 'AAPL 卖出已成交', content: '229.00 × 20 股，成交金额 USD 4,580。', category: 'trade', tag: '成交', read: true, createTime: '09:12' },
    { id: 'n-5', title: 'NVDA 买入已成交', content: '市价 15 股已写入持仓。', category: 'trade', tag: '成交', read: true, createTime: '09:05' },
    { id: 'n-6', title: '行业集中度提醒', content: '港股互联网敞口 32%，距 40% 上限 8pp。', category: 'risk', tag: '风控', read: true, createTime: '10:42' },
    { id: 'n-7', title: '日终结算完成', content: '净资产 HKD 1,284,500，账户核对无差异。', category: 'system', tag: '系统', read: true, createTime: '昨日 16:20' }
  ]
}

export function stubPositions() {
  return [
    { symbol: '00700', symbolName: '腾讯控股', name: '腾讯控股', market: 'HK', category: '互联网', quantity: 400, costPrice: 406, currentPrice: 412.6, last: 412.6, pnl: 2640, pnlRate: 1.62, pnlPct: 1.62, currency: 'HKD' },
    { symbol: '03690', symbolName: '美团-W', name: '美团-W', market: 'HK', category: '互联网', quantity: 800, costPrice: 168.2, currentPrice: 161.75, last: 161.75, pnl: -5160, pnlRate: -3.84, pnlPct: -3.84, currency: 'HKD' },
    { symbol: '300750', symbolName: '宁德时代', name: '宁德时代', market: 'CN', category: '新能源', quantity: 200, costPrice: 194.16, currentPrice: 198.32, last: 198.32, pnl: 832, pnlRate: 2.14, pnlPct: 2.14, currency: 'CNY' },
    { symbol: 'AAPL', symbolName: '苹果', name: '苹果', market: 'US', category: '科技', quantity: 20, costPrice: 229.24, currentPrice: 228.14, last: 228.14, pnl: -22, pnlRate: -0.48, pnlPct: -0.48, currency: 'USD' },
    { symbol: '09988', symbolName: '阿里巴巴-SW', name: '阿里巴巴-SW', market: 'HK', category: '互联网', quantity: 200, costPrice: 85.1, currentPrice: 86.15, last: 86.15, pnl: 210, pnlRate: 1.23, pnlPct: 1.23, currency: 'HKD' },
    { symbol: 'TSLA', symbolName: '特斯拉', name: '特斯拉', market: 'US', category: '汽车', quantity: 8, costPrice: 248.4, currentPrice: 246.1, last: 246.1, pnl: -18, pnlRate: -0.93, pnlPct: -0.93, currency: 'USD' }
  ]
}

export function stubFactors() {
  return [
    { name: '动量 20D', category: '动量', ic: 0.042, ir: 0.86, coverage: 0.92, returns: [1.2, 0.8, -0.3, 1.5, 0.6] },
    { name: '反转 5D', category: '反转', ic: -0.031, ir: -0.54, coverage: 0.88, returns: [-0.4, 0.2, -0.8, 0.1, -0.3] },
    { name: '估值 EP', category: '估值', ic: 0.018, ir: 0.41, coverage: 0.95, returns: [0.3, 0.5, 0.2, 0.4, 0.1] },
    { name: '质量 ROE', category: '质量', ic: 0.027, ir: 0.62, coverage: 0.81, returns: [0.6, 0.4, 0.7, 0.2, 0.5] },
    { name: '波动率 20D', category: '风险', ic: -0.022, ir: -0.38, coverage: 0.97, returns: [-0.2, -0.1, 0.3, -0.4, -0.2] }
  ]
}

export function stubStrategies() {
  return [
    { id: 'st-1', name: '多因子动量', status: 'running', profile: 'momentum', symbolsCount: 24, signalCount: 6, winRate: 0.58, note: '中证+港股通' },
    { id: 'st-2', name: '均值回归', status: 'paused', profile: 'reversion', symbolsCount: 18, signalCount: 2, winRate: 0.51, note: '低波动篮子' },
    { id: 'st-3', name: '事件驱动', status: 'running', profile: 'event', symbolsCount: 12, signalCount: 4, winRate: 0.63, note: '财报窗口' }
  ]
}

export function stubStrategySignals() {
  return [
    { id: 'sg-1', symbol: 'NVDA', name: '英伟达', signal: 'BUY', strength: 0.86, score: 82, createdAt: '10:21' },
    { id: 'sg-2', symbol: '00700', name: '腾讯控股', signal: 'BUY', strength: 0.74, score: 76, createdAt: '10:18' },
    { id: 'sg-3', symbol: 'TSLA', name: '特斯拉', signal: 'SELL', strength: 0.69, score: 41, createdAt: '10:12' },
    { id: 'sg-4', symbol: 'AAPL', name: '苹果', signal: 'HOLD', strength: 0.45, score: 55, createdAt: '10:05' },
    { id: 'sg-5', symbol: '03690', name: '美团-W', signal: 'SELL', strength: 0.81, score: 38, createdAt: '09:58' }
  ]
}

export function stubModels() {
  return [
    { modelId: 'stub-1', modelName: 'Grok-4 Fast', modelCode: 'grok-4-fast', provider: 'xAI', scope: 'chat', status: '0', isDefault: true, latencyMs: 420, quotaPct: 82, health: 'ok' },
    { modelId: 'stub-2', modelName: 'GPT-4.1 Mini', modelCode: 'gpt-4.1-mini', provider: 'OpenAI', scope: 'chat', status: '0', latencyMs: 680, quotaPct: 61, health: 'ok' },
    { modelId: 'stub-3', modelName: 'DeepSeek-V3', modelCode: 'deepseek-v3', provider: 'DeepSeek', scope: 'chat', status: '0', latencyMs: 510, quotaPct: 74, health: 'ok' },
    { modelId: 'stub-4', modelName: 'Claude Sonnet', modelCode: 'claude-sonnet-5', provider: 'Anthropic', scope: 'global', status: '0', latencyMs: 560, quotaPct: 48, health: 'ok' },
    { modelId: 'stub-5', modelName: 'Qwen Plus', modelCode: 'qwen-plus', provider: 'DashScope', scope: 'market', status: '1', latencyMs: 0, quotaPct: 12, health: 'down' },
    { modelId: 'stub-6', modelName: 'Local Echo', modelCode: 'echo', provider: 'local', scope: 'quant', status: '1', latencyMs: 0, quotaPct: 0, health: 'down' }
  ]
}

export function stubChatSessions() {
  return [
    { sessionId: 'stub-s1', sessionTitle: 'NVDA 全景研判', title: 'NVDA 全景研判', modelName: 'Grok-4 Fast', createdAt: '今天 09:38', updatedAt: '今天 09:38' },
    { sessionId: 'stub-s2', sessionTitle: '港股互联网提问', title: '港股互联网提问', modelName: 'Grok-4 Fast', createdAt: '今天 09:05', updatedAt: '今天 09:05' },
    { sessionId: 'stub-s3', sessionTitle: '美债收益率情景', title: '美债收益率情景', modelName: 'Grok-4 Fast', createdAt: '昨天 21:14', updatedAt: '昨天 21:14' }
  ]
}

export function stubChatMessages(symbol = 'NVDA') {
  return [
    {
      role: 'user',
      content: `请对 ${symbol} 做一次全景研判，结合技术与最新舆情，给出备多/偏空立场与关键关注点。`
    },
    {
      role: 'assistant',
      content: '这是标注示意稿，不是实盘结论。工具引用仅作版式对照：日线量能中性，舆情分数待接入。请用「一键研判」走真实 oneshot。',
      stance: '观望',
      tools: ['chat', '日线', '舆情'],
      stub: true
    }
  ]
}

export function stubUsers() {
  return [
    { userId: 1, userName: 'admin', nickName: '超级管理员', roleName: '超级管理员', status: '0', loginDate: '2026-09-10 09:12', lockFlag: '0' },
    { userId: 2, userName: 'analyst_wangang', nickName: '分析岗', roleName: '分析', status: '0', loginDate: '2026-09-09 18:40', lockFlag: '0' },
    { userId: 3, userName: 'quant_zhao', nickName: '量化研究员', roleName: '量化', status: '0', loginDate: '2026-09-08 14:22', lockFlag: '0' },
    { userId: 4, userName: 'trader_chen', nickName: '交易员', roleName: '交易', status: '0', loginDate: '2026-09-10 08:55', lockFlag: '0' },
    { userId: 5, userName: 'guest_demo', nickName: '演示', roleName: '只读', status: '1', loginDate: '2026-07-15 10:00', lockFlag: '0' },
    { userId: 6, userName: 'locked_xu', nickName: '风控见习', roleName: '风控', status: '0', loginDate: '2026-08-28 16:33', lockFlag: '1' }
  ]
}

export function stubJobs() {
  return [
    { jobId: 'j-1', title: '自选批量分析', cron: '0 5 16 * * ?', status: '0', runState: 'idle', lastRunAt: '2026-09-10 16:00', retryCount: 0, lastOk: true },
    { jobId: 'j-2', title: '市场热度快照', cron: '0 10 16 * * ?', status: '0', runState: 'idle', lastRunAt: '2026-09-10 16:15', retryCount: 0, lastOk: true },
    { jobId: 'j-3', title: '舆情聚合', cron: '0 0/30 * * * ?', status: '0', runState: 'running', lastRunAt: '2026-09-10 08:30', retryCount: 0 },
    { jobId: 'j-4', title: '长桥行情同步', cron: '0 0/5 * * * ?', status: '0', runState: 'idle', lastRunAt: '2026-09-10 09:00', retryCount: 2 },
    { jobId: 'j-5', title: '日终推送', cron: '0 0 17 * * ?', status: '0', runState: 'failed', lastRunAt: '2026-09-10 15:55', retryCount: 1, lastError: 'notify worker timeout' },
    { jobId: 'j-6', title: '因子回测', cron: '0 55 21 * * ?', status: '1', runState: 'idle', lastRunAt: '2026-09-09 18:00', retryCount: 3 },
    { jobId: 'j-7', title: 'watchlist_analyze', cron: '0 20 16 * * ?', status: '0', runState: 'idle', lastRunAt: '2026-09-10 02:00', retryCount: 0, lastOk: true },
    { jobId: 'j-8', title: '手动补数', cron: '-', status: '1', runState: 'idle', lastRunAt: '2026-09-10 14:22', retryCount: 0 }
  ]
}

export function stubRoles() {
  return [
    { roleId: 1, roleName: '超级管理员', roleKey: 'admin', userCount: 2, remark: '全部', menus: ['用户', '角色', '菜单', '看板', '自选', '任务中心', '持仓', '委托', '风控', '模型', '研判', '因子'] },
    { roleId: 2, roleName: '交易员', roleKey: 'trader', userCount: 12, remark: '交易台', menus: ['看板', '自选', '持仓', '委托', '风控'] },
    { roleId: 3, roleName: '分析师', roleKey: 'analyst', userCount: 8, remark: '行情复盘', menus: ['看板', '自选', '任务中心', '研判'] },
    { roleId: 4, roleName: '量化研究员', roleKey: 'quant', userCount: 10, remark: '因子策略', menus: ['看板', '因子', '模型', '研判'] },
    { roleId: 5, roleName: '风控', roleKey: 'risk', userCount: 6, remark: '限额', menus: ['持仓', '委托', '风控'] },
    { roleId: 6, roleName: '只读', roleKey: 'viewer', userCount: 9, remark: '只看', menus: ['看板'] }
  ]
}

export function stubRecentVerdicts() {
  return [
    { symbol: 'NVDA', market: 'US', stance: '偏多', score: 72, note: '示意 · 非实盘' },
    { symbol: '00700', market: 'HK', stance: '中性', score: 54, note: '示意 · 非实盘' },
    { symbol: 'AAPL', market: 'US', stance: '观望', score: 49, note: '示意 · 非实盘' }
  ]
}

/** Filled sentiment dashboard modules — demo only. Never mask a live empty. */
export function stubSentimentDashboard() {
  const latest = {
    analysisId: 128,
    createTime: '2026-09-11 09:12:00',
    newsCount: 36,
    summary: '港股科技偏强，美股隔夜震荡，A 股情绪中性偏多。注意外盘波动对开盘溢价的传导。',
    usDirection: '中性',
    usScore: 52,
    usReason: '美股三大指数隔夜分化，纳指回吐部分涨幅，整体中性。',
    hkDirection: '利多',
    hkScore: 68,
    hkReason: '南向资金延续流入，互联网权重带动恒指偏强。',
    aDirection: '利多',
    aScore: 61,
    aReason: '成交额回升，成长与周期轮动，情绪修复中。',
    riskEvents: '美债收益率上行可能压制成长股估值。\n外围波动或放大开盘溢价。',
    modelName: 'Grok 4.6',
    status: '0'
  }
  return {
    stats: { total: 1286, today: 42, unanalyzed: 17, latestAnalysis: latest },
    latest,
    history: [
      latest,
      {
        analysisId: 127,
        createTime: '2026-09-11 08:40:00',
        newsCount: 28,
        summary: '隔夜美股期货高开回落，港股科技仍有承接。',
        usDirection: '利空',
        usScore: 41,
        hkDirection: '利多',
        hkScore: 64,
        aDirection: '中性',
        aScore: 50,
        modelName: 'Grok 4.6',
        status: '0'
      },
      {
        analysisId: 126,
        createTime: '2026-09-10 16:05:00',
        newsCount: 31,
        summary: 'A 股量能改善，北向净买，外盘隔夜偏谨慎。',
        usDirection: '中性',
        usScore: 48,
        hkDirection: '利多',
        hkScore: 62,
        aDirection: '利多',
        aScore: 66,
        modelName: 'Grok 4.6',
        status: '0'
      }
    ],
    trend: [
      { createTime: '2026-09-10 10:00:00', usScore: 47, hkScore: 58, aScore: 54 },
      { createTime: '2026-09-10 14:00:00', usScore: 49, hkScore: 60, aScore: 57 },
      { createTime: '2026-09-10 16:05:00', usScore: 48, hkScore: 62, aScore: 66 },
      { createTime: '2026-09-11 08:40:00', usScore: 41, hkScore: 64, aScore: 50 },
      { createTime: '2026-09-11 09:12:00', usScore: 52, hkScore: 68, aScore: 61 }
    ],
    indices: stubIndices()
  }
}
