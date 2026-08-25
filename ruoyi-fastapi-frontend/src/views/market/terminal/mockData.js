/**
 * 专业证券交易终端 (Pro Trading Terminal) 高保真多市场模拟数据集
 * 涵盖美股 (US)、港股 (HK)、A股 (CN) 主流代表性标的
 */

// 大盘核心指数
export const mockMarketIndices = [
  { symbol: 'IXIC', name: '纳斯达克', price: 18078.65, change: 185.42, changeRate: 1.04, market: 'US' },
  { symbol: 'SPX', name: '标普500', price: 5648.40, change: 36.20, changeRate: 0.65, market: 'US' },
  { symbol: 'DJI', name: '道琼斯', price: 41288.78, change: -75.12, changeRate: -0.18, market: 'US' },
  { symbol: 'HSI', name: '恒生指数', price: 17720.50, change: 168.30, changeRate: 0.96, market: 'HK' },
  { symbol: '000001', name: '上证指数', price: 2854.37, change: 12.85, changeRate: 0.45, market: 'CN' }
]

export { getMarketSessionStatus, shouldShowMarketChip } from './sessionHours'

// 预定义分时 240 个固定时间刻度 (9:30-11:30, 13:00-15:00)
const INTRADAY_TIMES = []
for (let i = 0; i < 120; i++) {
  const h = Math.floor(9 + (30 + i) / 60)
  const m = (30 + i) % 60
  INTRADAY_TIMES.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`)
}
for (let i = 0; i < 120; i++) {
  const h = Math.floor(13 + i / 60)
  const m = i % 60
  INTRADAY_TIMES.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`)
}

// 极速生成分时数据 (基于预定义时间刻度，0ms 瞬时返回)
function generateIntradayData(basePrice, volatility = 0.0025) {
  const len = INTRADAY_TIMES.length
  const points = new Array(len)
  let currentPrice = basePrice
  let sumPriceVol = 0
  let totalVol = 0
  
  for (let i = 0; i < len; i++) {
    const delta = (Math.random() - 0.48) * (basePrice * volatility)
    currentPrice = Math.max(basePrice * 0.90, Math.min(basePrice * 1.10, currentPrice + delta))
    const vol = Math.floor(Math.random() * 6000 + 1000)
    totalVol += vol
    sumPriceVol += currentPrice * vol
    const avgPrice = sumPriceVol / totalVol

    points[i] = {
      time: INTRADAY_TIMES[i],
      price: Number(currentPrice.toFixed(2)),
      avgPrice: Number(avgPrice.toFixed(2)),
      volume: vol
    }
  }
  return points
}

// 极速生成K线历史数据 (按需 0ms 生成)
function generateKlineHistory(basePrice, count = 60, trend = 0.001) {
  const list = new Array(count)
  let lastClose = basePrice * 0.88
  const baseTs = 1787625600000 // 2026-08-25
  const oneDay = 86400000
  
  for (let i = 0; i < count; i++) {
    const d = new Date(baseTs - (count - i) * oneDay)
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const dateStr = `${d.getFullYear()}-${m}-${day}`
    
    const changeFactor = 1 + trend + (Math.random() - 0.48) * 0.03
    const close = Number((lastClose * changeFactor).toFixed(2))
    const open = Number((lastClose * (1 + (Math.random() - 0.5) * 0.012)).toFixed(2))
    const high = Number((Math.max(open, close) * (1 + Math.random() * 0.015)).toFixed(2))
    const low = Number((Math.min(open, close) * (1 - Math.random() * 0.015)).toFixed(2))
    const volume = Math.floor(Math.random() * 400000 + 100000)
    
    list[i] = { date: dateStr, open, close, low, high, volume }
    lastClose = close
  }
  return list
}

// 标的完整数据集
export const mockStockUniverse = [
  {
    symbol: 'MSFT',
    name: '微软',
    market: 'US',
    currency: 'USD',
    group: '核心科技',
    category: '企业软件与云/AI服务',
    price: 487.31,
    prevClose: 483.24,
    open: 483.205,
    high: 490.605,
    low: 481.860,
    change: 4.07,
    changeRate: 0.84,
    volume: 17230800,
    volumeText: '1723.08万',
    turnover: 8400000000,
    turnoverText: '84亿',
    turnoverRate: '0.23%',
    amplitude: '1.81%',
    volumeRatio: 0.67,
    pe: 27.15,
    peTTM: '27.15',
    peStatic: '27.15',
    peDynamic: '24.63',
    pb: 8.179,
    weibi: '60.00%',
    dividendTTM: '3.560',
    dividendYieldTTM: '0.730%',
    dividendYield: '0.73%',
    marketCap: '3.62万亿',
    totalShares: '74.26亿',
    floatMarketCap: '3.62万亿',
    floatShares: '74.23亿',
    high52: 549.201,
    low52: 348.544,
    historyHigh: 550.013,
    historyLow: 6.127,
    avgPrice: 487.505,
    lotSize: '1股',
    beta: 0.967,
    quoteTime: '08/24 16:00:00 (美东)',
    sparkline: [483.2, 484.5, 483.9, 486.2, 488.1, 487.0, 489.2, 487.31],
    aiScore: 94.8,
    aiVerdict: '强烈推荐 · 稳健上行',
    aiSummary: 'Azure AI 客户数量与年经常性收入持续超预期，Copilot 渗透率提升带动商业云毛利率上修。技术面上行通道保持良好。',
    factors: [
      { name: '动量因子', score: 92 },
      { name: '成长因子', score: 95 },
      { name: '情绪因子', score: 90 },
      { name: '质量因子', score: 96 },
      { name: '资金流向', score: 93 },
      { name: '分析师预期', score: 94 },
      { name: '流动性', score: 99 },
      { name: '估值水平', score: 62 }
    ],
    capitalFlow: {
      superIn: 2200,
      superOut: 1350,
      largeIn: 2900,
      largeOut: 2100,
      midIn: 1800,
      midOut: 1900,
      smallIn: 1300,
      smallOut: 1450,
      netInflow: 1100
    },
    news: [
      { id: 1, title: '微软宣布推出下一代 Copilot 企业级自主智能体系统', time: '8分钟前', source: '彭博社', sentiment: 'bull', impact: 5 },
      { id: 2, title: '摩根士丹利重申对微软的“增持”评级，目标价 520 美元', time: '35分钟前', source: '大摩研报', sentiment: 'bull', impact: 4 }
    ],
    bids: [
      { level: '买1', price: 487.25, volume: 8400, percent: 100 },
      { level: '买2', price: 487.15, volume: 6200, percent: 74 },
      { level: '买3', price: 487.05, volume: 9100, percent: 92 },
      { level: '买4', price: 486.95, volume: 4300, percent: 51 },
      { level: '买5', price: 486.85, volume: 7200, percent: 76 },
      { level: '买6', price: 486.75, volume: 5100, percent: 61 },
      { level: '买7', price: 486.65, volume: 11200, percent: 95 },
      { level: '买8', price: 486.55, volume: 3800, percent: 45 },
      { level: '买9', price: 486.45, volume: 6400, percent: 68 },
      { level: '买10', price: 486.35, volume: 8900, percent: 86 }
    ],
    asks: [
      { level: '卖10', price: 488.25, volume: 7800, percent: 70 },
      { level: '卖9', price: 488.15, volume: 5600, percent: 52 },
      { level: '卖8', price: 488.05, volume: 9200, percent: 88 },
      { level: '卖7', price: 487.95, volume: 6100, percent: 59 },
      { level: '卖6', price: 487.85, volume: 10400, percent: 94 },
      { level: '卖5', price: 487.75, volume: 4900, percent: 46 },
      { level: '卖4', price: 487.65, volume: 11000, percent: 100 },
      { level: '卖3', price: 487.55, volume: 7300, percent: 66 },
      { level: '卖2', price: 487.45, volume: 5800, percent: 53 },
      { level: '卖1', price: 487.35, volume: 8900, percent: 81 }
    ],
    trades: [
      { time: '16:00:00', price: 487.31, volume: 1200, side: 'buy' },
      { time: '15:59:58', price: 487.30, volume: 450, side: 'buy' },
      { time: '15:59:54', price: 487.25, volume: 800, side: 'sell' }
    ]
  },
  {
    symbol: 'NVDA',
    name: '英伟达',
    market: 'US',
    currency: 'USD',
    group: '核心科技',
    category: '半导体与算力硬件',
    price: 128.85,
    prevClose: 124.50,
    open: 125.20,
    high: 130.40,
    low: 124.80,
    change: 4.35,
    changeRate: 3.49,
    volume: 58294100,
    volumeText: '5829.41万',
    turnover: 7480000000,
    turnoverText: '74.80亿',
    turnoverRate: '2.38%',
    amplitude: '4.50%',
    volumeRatio: 1.42,
    pe: 68.4,
    peTTM: '68.40',
    peStatic: '64.20',
    peDynamic: '59.80',
    pb: 32.5,
    weibi: '52.30%',
    dividendTTM: '0.160',
    dividendYieldTTM: '0.030%',
    dividendYield: '0.03%',
    marketCap: '3.16万亿',
    totalShares: '245.8亿',
    floatMarketCap: '3.16万亿',
    floatShares: '245.2亿',
    high52: 140.76,
    low52: 45.01,
    historyHigh: 140.76,
    historyLow: 0.04,
    avgPrice: 128.92,
    lotSize: '1股',
    beta: 2.15,
    quoteTime: '08/24 16:00:00 (美东)',
    sparkline: [124.5, 125.2, 126.0, 125.5, 127.8, 128.5, 127.9, 129.2, 128.85],
    aiScore: 92.4,
    aiVerdict: '强烈推荐 · 突破上行',
    aiSummary: 'Blackwell 芯片量产推进迅速，全球数据中心资本开支维持双位数高增。技术形态突破近两周旗形整理，动量与资金面极佳。',
    factors: [
      { name: '动量因子', score: 96 },
      { name: '成长因子', score: 94 },
      { name: '情绪因子', score: 91 },
      { name: '质量因子', score: 88 },
      { name: '资金流向', score: 95 },
      { name: '分析师预期', score: 90 },
      { name: '流动性', score: 98 },
      { name: '估值水平', score: 48 }
    ],
    capitalFlow: {
      superIn: 1850,
      superOut: 1120,
      largeIn: 2400,
      largeOut: 1980,
      midIn: 1600,
      midOut: 1750,
      smallIn: 1200,
      smallOut: 1400,
      netInflow: 800
    },
    news: [
      { id: 1, title: '英伟达下一代 GPU 预订量创历史新高，各大云巨头追加订单', time: '10分钟前', source: '彭博社', sentiment: 'bull', impact: 5 },
      { id: 2, title: '投行将英伟达目标价上调至 160 美元，维持买入评级', time: '42分钟前', source: '高盛研究', sentiment: 'bull', impact: 4 },
      { id: 3, title: 'AI 供应链产能爬坡顺利，台积电先进制程稼动率满载', time: '2小时前', source: '路透社', sentiment: 'bull', impact: 3 }
    ],
    bids: [
      { level: '买1', price: 128.80, volume: 15400, percent: 100 },
      { level: '买2', price: 128.75, volume: 12200, percent: 79 },
      { level: '买3', price: 128.70, volume: 18900, percent: 92 },
      { level: '买4', price: 128.65, volume: 9400, percent: 61 },
      { level: '买5', price: 128.60, volume: 14300, percent: 73 },
      { level: '买6', price: 128.55, volume: 8200, percent: 53 },
      { level: '买7', price: 128.50, volume: 22000, percent: 96 },
      { level: '买8', price: 128.45, volume: 6500, percent: 42 },
      { level: '买9', price: 128.40, volume: 11800, percent: 76 },
      { level: '买10', price: 128.35, volume: 13500, percent: 87 }
    ],
    asks: [
      { level: '卖10', price: 129.30, volume: 11000, percent: 71 },
      { level: '卖9', price: 129.25, volume: 8700, percent: 56 },
      { level: '卖8', price: 129.20, volume: 14200, percent: 92 },
      { level: '卖7', price: 129.15, volume: 9800, percent: 63 },
      { level: '卖6', price: 129.10, volume: 16500, percent: 86 },
      { level: '卖5', price: 129.05, volume: 7600, percent: 49 },
      { level: '卖4', price: 129.00, volume: 25400, percent: 100 },
      { level: '卖3', price: 128.95, volume: 12300, percent: 79 },
      { level: '卖2', price: 128.90, volume: 9100, percent: 59 },
      { level: '卖1', price: 128.85, volume: 14600, percent: 94 }
    ],
    trades: [
      { time: '15:59:58', price: 128.85, volume: 450, side: 'buy' },
      { time: '15:59:55', price: 128.85, volume: 1200, side: 'buy' },
      { time: '15:59:52', price: 128.82, volume: 300, side: 'sell' },
      { time: '15:59:48', price: 128.85, volume: 850, side: 'buy' },
      { time: '15:59:43', price: 128.80, volume: 600, side: 'sell' },
      { time: '15:59:39', price: 128.85, volume: 2100, side: 'buy' },
      { time: '15:59:35', price: 128.84, volume: 150, side: 'buy' },
      { time: '15:59:30', price: 128.80, volume: 500, side: 'sell' }
    ]
  },
  {
    symbol: 'AAPL',
    name: '苹果公司',
    market: 'US',
    currency: 'USD',
    group: '核心科技',
    category: '消费电子与AI终端',
    price: 226.40,
    prevClose: 224.80,
    open: 225.10,
    high: 227.60,
    low: 224.30,
    volume: 34890000,
    turnover: 7890000000,
    turnoverRate: '1.12%',
    amplitude: '1.47%',
    volumeRatio: 1.05,
    pe: 34.2,
    pb: 46.8,
    marketCap: '3.45万亿美元',
    high52: 237.23,
    low52: 164.08,
    beta: 1.08,
    dividendYield: '0.44%',
    sparkline: [224.8, 225.1, 225.6, 225.2, 226.0, 226.5, 226.1, 226.4],
    aiScore: 84.6,
    aiVerdict: '温和看多 · 震荡走高',
    aiSummary: 'Apple Intelligence 在新机型搭载率预期积极，服务业务收入稳步扩张，现金流极其充沛。',
    factors: [
      { name: '动量因子', score: 81 },
      { name: '成长因子', score: 79 },
      { name: '情绪因子', score: 85 },
      { name: '质量因子', score: 98 },
      { name: '资金流向', score: 82 },
      { name: '分析师预期', score: 86 },
      { name: '流动性', score: 99 },
      { name: '估值水平', score: 62 }
    ],
    capitalFlow: {
      superIn: 1200,
      superOut: 980,
      largeIn: 1800,
      largeOut: 1650,
      midIn: 1400,
      midOut: 1350,
      smallIn: 900,
      smallOut: 950,
      netInflow: 370
    },
    news: [
      { id: 101, title: '摩根士丹利重申苹果为首选股，看好换机周期爆发', time: '25分钟前', source: '大摩报告', sentiment: 'bull', impact: 4 },
      { id: 102, title: 'App Store 8月全球开发者净收益同比增长 11.2%', time: '1小时前', source: 'TechCrunch', sentiment: 'bull', impact: 3 }
    ],
    bids: [
      { level: '买1', price: 226.35, volume: 8200, percent: 100 },
      { level: '买2', price: 226.30, volume: 6400, percent: 78 },
      { level: '买3', price: 226.25, volume: 9100, percent: 92 },
      { level: '买4', price: 226.20, volume: 4800, percent: 58 },
      { level: '买5', price: 226.15, volume: 7300, percent: 75 }
    ],
    asks: [
      { level: '卖5', price: 226.60, volume: 5500, percent: 62 },
      { level: '卖4', price: 226.55, volume: 8900, percent: 95 },
      { level: '卖3', price: 226.50, volume: 9200, percent: 98 },
      { level: '卖2', price: 226.45, volume: 6100, percent: 65 },
      { level: '卖1', price: 226.40, volume: 7800, percent: 83 }
    ],
    trades: [
      { time: '15:59:59', price: 226.40, volume: 200, side: 'buy' },
      { time: '15:59:56', price: 226.38, volume: 150, side: 'sell' },
      { time: '15:59:51', price: 226.40, volume: 500, side: 'buy' }
    ]
  },
  {
    symbol: 'TSLA',
    name: '特斯拉',
    market: 'US',
    currency: 'USD',
    group: '核心科技',
    category: '新能源汽车与具身智能',
    price: 218.30,
    prevClose: 222.10,
    open: 221.50,
    high: 223.40,
    low: 216.80,
    volume: 62100000,
    turnover: 13600000000,
    turnoverRate: '3.85%',
    amplitude: '2.97%',
    volumeRatio: 1.18,
    pe: 61.2,
    pb: 9.8,
    marketCap: '6980亿美元',
    high52: 271.00,
    low52: 138.80,
    beta: 2.42,
    dividendYield: '0.00%',
    sparkline: [222.1, 221.5, 220.0, 219.2, 217.5, 218.0, 217.2, 218.3],
    aiScore: 68.2,
    aiVerdict: '中性观望 · 关键支撑测试',
    aiSummary: 'Robotaxi 商业化落地仍待法规审批，短期毛利率承压，建议在 215 美元支撑位附近观察企稳信号。',
    factors: [
      { name: '动量因子', score: 62 },
      { name: '成长因子', score: 71 },
      { name: '情绪因子', score: 69 },
      { name: '质量因子', score: 74 },
      { name: '资金流向', score: 58 },
      { name: '分析师预期', score: 65 },
      { name: '流动性', score: 99 },
      { name: '估值水平', score: 52 }
    ],
    capitalFlow: {
      superIn: 890,
      superOut: 1150,
      largeIn: 1350,
      largeOut: 1600,
      midIn: 1200,
      midOut: 1180,
      smallIn: 980,
      smallOut: 850,
      netInflow: -360
    },
    news: [
      { id: 201, title: '特斯拉 FSD V13 即将推送，接管率大幅降低', time: '35分钟前', source: 'Electrek', sentiment: 'bull', impact: 3 },
      { id: 202, title: '欧洲新能源车补贴调整，短期交付量或有季节性波动', time: '2小时前', source: '金融时报', sentiment: 'bear', impact: 4 }
    ],
    bids: [
      { level: '买1', price: 218.25, volume: 11000, percent: 95 },
      { level: '买2', price: 218.20, volume: 8500, percent: 73 },
      { level: '买3', price: 218.15, volume: 12400, percent: 100 }
    ],
    asks: [
      { level: '卖3', price: 218.40, volume: 10200, percent: 88 },
      { level: '卖2', price: 218.35, volume: 7600, percent: 65 },
      { level: '卖1', price: 218.30, volume: 9800, percent: 84 }
    ],
    trades: [
      { time: '15:59:58', price: 218.30, volume: 300, side: 'sell' },
      { time: '15:59:50', price: 218.28, volume: 150, side: 'sell' }
    ]
  },
  {
    symbol: '00700',
    name: '腾讯控股',
    market: 'HK',
    currency: 'HKD',
    group: '港股核心',
    category: '互联网综合与数字文娱',
    price: 378.20,
    prevClose: 372.60,
    open: 374.00,
    high: 380.40,
    low: 373.20,
    volume: 18450000,
    turnover: 6980000000,
    turnoverRate: '0.42%',
    amplitude: '1.93%',
    volumeRatio: 1.25,
    pe: 18.5,
    pb: 3.4,
    marketCap: '3.52万亿港元',
    high52: 410.00,
    low52: 260.20,
    beta: 0.95,
    dividendYield: '1.28%',
    sparkline: [372.6, 374.0, 375.5, 376.8, 377.2, 379.0, 378.0, 378.2],
    aiScore: 89.1,
    aiVerdict: '积极看多 · 回购与游戏双轮驱动',
    aiSummary: '千亿级回购计划持续注销股份，视频号广告变现与头部新游表现强劲，估值具备极高安全边际。',
    factors: [
      { name: '动量因子', score: 86 },
      { name: '成长因子', score: 88 },
      { name: '情绪因子', score: 84 },
      { name: '质量因子', score: 95 },
      { name: '资金流向', score: 92 },
      { name: '分析师预期', score: 91 },
      { name: '流动性', score: 98 },
      { name: '估值水平', score: 80 }
    ],
    capitalFlow: {
      superIn: 1450,
      superOut: 920,
      largeIn: 2100,
      largeOut: 1750,
      midIn: 1600,
      midOut: 1550,
      smallIn: 1100,
      smallOut: 1200,
      netInflow: 830 // 百万港元
    },
    news: [
      { id: 301, title: '腾讯控股今日耗资 10 亿港元回购 265 万股', time: '18分钟前', source: '港交所公告', sentiment: 'bull', impact: 4 },
      { id: 302, title: '南向港股通今日大幅净买入腾讯 8.2 亿港元', time: '1小时前', source: 'Wind资讯', sentiment: 'bull', impact: 4 }
    ],
    bids: [
      { level: '买1', price: 378.00, volume: 24000, percent: 100 },
      { level: '买2', price: 377.80, volume: 18500, percent: 77 },
      { level: '买3', price: 377.60, volume: 21000, percent: 87 },
      { level: '买4', price: 377.40, volume: 14500, percent: 60 },
      { level: '买5', price: 377.20, volume: 19800, percent: 82 }
    ],
    asks: [
      { level: '卖5', price: 379.00, volume: 16200, percent: 67 },
      { level: '卖4', price: 378.80, volume: 22500, percent: 93 },
      { level: '卖3', price: 378.60, volume: 17800, percent: 74 },
      { level: '卖2', price: 378.40, volume: 13500, percent: 56 },
      { level: '卖1', price: 378.20, volume: 24100, percent: 100 }
    ],
    trades: [
      { time: '16:00:00', price: 378.20, volume: 5000, side: 'buy' },
      { time: '15:59:52', price: 378.00, volume: 1200, side: 'sell' },
      { time: '15:59:45', price: 378.20, volume: 2400, side: 'buy' }
    ]
  },
  {
    symbol: '09988',
    name: '阿里巴巴-W',
    market: 'HK',
    currency: 'HKD',
    group: '港股核心',
    category: '电商与云计算',
    price: 84.50,
    prevClose: 83.10,
    open: 83.50,
    high: 85.20,
    low: 83.20,
    volume: 38200000,
    turnover: 3230000000,
    turnoverRate: '0.85%',
    amplitude: '2.41%',
    volumeRatio: 1.15,
    pe: 14.2,
    pb: 1.45,
    marketCap: '1.62万亿港元',
    high52: 92.50,
    low52: 64.80,
    beta: 1.12,
    dividendYield: '2.10%',
    sparkline: [83.1, 83.5, 84.0, 83.8, 84.5, 85.0, 84.2, 84.5],
    aiScore: 82.0,
    aiVerdict: '温和看多 · 估值重估修复',
    aiSummary: '完成双重主要上市，纳入港股通预期落地；阿里云公共云及 AI 基础设施收入增速转正。',
    factors: [
      { name: '动量因子', score: 79 },
      { name: '成长因子', score: 75 },
      { name: '情绪因子', score: 81 },
      { name: '质量因子', score: 87 },
      { name: '资金流向', score: 84 },
      { name: '分析师预期', score: 83 },
      { name: '流动性', score: 96 },
      { name: '估值水平', score: 88 }
    ],
    capitalFlow: {
      superIn: 680,
      superOut: 450,
      largeIn: 980,
      largeOut: 850,
      midIn: 820,
      midOut: 790,
      smallIn: 550,
      smallOut: 580,
      netInflow: 360
    },
    news: [
      { id: 401, title: '阿里云发布百炼大模型平台升级版，企业级调用量激增', time: '40分钟前', source: '36氪', sentiment: 'bull', impact: 4 },
      { id: 402, title: '淘天集团启动百亿补贴策略深化，用户留存指标提升', time: '3小时前', source: '晚点LatePost', sentiment: 'neutral', impact: 2 }
    ],
    bids: [
      { level: '买1', price: 84.45, volume: 32000, percent: 100 },
      { level: '买2', price: 84.40, volume: 28000, percent: 87 },
      { level: '买3', price: 84.35, volume: 19500, percent: 61 }
    ],
    asks: [
      { level: '卖3', price: 84.60, volume: 22000, percent: 68 },
      { level: '卖2', price: 84.55, volume: 29000, percent: 90 },
      { level: '卖1', price: 84.50, volume: 31000, percent: 96 }
    ],
    trades: [
      { time: '16:00:00', price: 84.50, volume: 6000, side: 'buy' },
      { time: '15:59:50', price: 84.45, volume: 2500, side: 'sell' }
    ]
  },
  {
    symbol: '600519',
    name: '贵州茅台',
    market: 'CN',
    currency: 'CNY',
    group: 'A股白马',
    category: '高端白酒与核心资产',
    price: 1450.00,
    prevClose: 1435.50,
    open: 1438.00,
    high: 1458.00,
    low: 1436.00,
    volume: 2450000,
    turnover: 3550000000,
    turnoverRate: '0.20%',
    amplitude: '1.53%',
    volumeRatio: 1.10,
    pe: 22.4,
    pb: 7.6,
    marketCap: '1.82万亿元',
    high52: 1880.00,
    low52: 1390.00,
    beta: 0.72,
    dividendYield: '3.52%',
    sparkline: [1435.5, 1438.0, 1442.0, 1446.5, 1449.0, 1455.0, 1448.0, 1450.0],
    aiScore: 86.5,
    aiVerdict: '长期配置 · 高股息与现金流护城河',
    aiSummary: '龙头地位不可撼动，拟实施特别分红与股份注销，股息率极具吸引力，机构中长期资金持续加仓。',
    factors: [
      { name: '动量因子', score: 72 },
      { name: '成长因子', score: 82 },
      { name: '情绪因子', score: 80 },
      { name: '质量因子', score: 99 },
      { name: '资金流向', score: 88 },
      { name: '分析师预期', score: 92 },
      { name: '流动性', score: 95 },
      { name: '估值水平', score: 76 }
    ],
    capitalFlow: {
      superIn: 820,
      superOut: 510,
      largeIn: 1100,
      largeOut: 950,
      midIn: 900,
      midOut: 980,
      smallIn: 620,
      smallOut: 700,
      netInflow: 300 // 百万元
    },
    news: [
      { id: 501, title: '贵州茅台发布未来三年股东回报规划，分红比例不低于 75%', time: '1小时前', source: '上交所', sentiment: 'bull', impact: 5 },
      { id: 502, title: '北向资金今日净买入贵州茅台 4.3 亿元', time: '2小时前', source: '东方财富', sentiment: 'bull', impact: 4 }
    ],
    bids: [
      { level: '买1', price: 1449.80, volume: 1500, percent: 100 },
      { level: '买2', price: 1449.50, volume: 1200, percent: 80 },
      { level: '买3', price: 1449.00, volume: 1800, percent: 90 }
    ],
    asks: [
      { level: '卖3', price: 1450.80, volume: 1300, percent: 72 },
      { level: '卖2', price: 1450.50, volume: 1600, percent: 88 },
      { level: '卖1', price: 1450.00, volume: 1750, percent: 97 }
    ],
    trades: [
      { time: '15:00:00', price: 1450.00, volume: 500, side: 'buy' },
      { time: '14:59:52', price: 1449.80, volume: 120, side: 'sell' }
    ]
  },
  {
    symbol: '300750',
    name: '宁德时代',
    market: 'CN',
    currency: 'CNY',
    group: 'A股白马',
    category: '动力电池与储能系统',
    price: 184.20,
    prevClose: 179.80,
    open: 180.50,
    high: 186.00,
    low: 180.00,
    volume: 21500000,
    turnover: 3950000000,
    turnoverRate: '1.25%',
    amplitude: '3.34%',
    volumeRatio: 1.35,
    pe: 17.8,
    pb: 3.6,
    marketCap: '8100亿元',
    high52: 220.00,
    low52: 135.20,
    beta: 1.38,
    dividendYield: '2.20%',
    sparkline: [179.8, 180.5, 182.0, 181.8, 184.0, 185.5, 183.8, 184.2],
    aiScore: 88.0,
    aiVerdict: '积极看多 · 全球市占率稳固',
    aiSummary: '神行超充电池与麒麟电池出货占比提升，海外欧美市场建厂合作顺利，储能第二增长曲线爆发。',
    factors: [
      { name: '动量因子', score: 85 },
      { name: '成长因子', score: 87 },
      { name: '情绪因子', score: 83 },
      { name: '质量因子', score: 94 },
      { name: '资金流向', score: 89 },
      { name: '分析师预期', score: 88 },
      { name: '流动性', score: 97 },
      { name: '估值水平', score: 82 }
    ],
    capitalFlow: {
      superIn: 980,
      superOut: 620,
      largeIn: 1350,
      largeOut: 1100,
      midIn: 950,
      midOut: 1020,
      smallIn: 680,
      smallOut: 720,
      netInflow: 500
    },
    news: [
      { id: 601, title: '宁德时代新一代全固态电池样品进入试制测试阶段', time: '50分钟前', source: '科创板日报', sentiment: 'bull', impact: 5 },
      { id: 602, title: '欧洲储能大单中标落地，签约规模达 3.5GWh', time: '2小时前', source: '第一财经', sentiment: 'bull', impact: 4 }
    ],
    bids: [
      { level: '买1', price: 184.15, volume: 8200, percent: 100 },
      { level: '买2', price: 184.10, volume: 6500, percent: 79 },
      { level: '买3', price: 184.00, volume: 9400, percent: 91 }
    ],
    asks: [
      { level: '卖3', price: 184.35, volume: 7600, percent: 74 },
      { level: '卖2', price: 184.25, volume: 8900, percent: 87 },
      { level: '卖1', price: 184.20, volume: 9800, percent: 95 }
    ],
    trades: [
      { time: '15:00:00', price: 184.20, volume: 2800, side: 'buy' },
      { time: '14:59:48', price: 184.15, volume: 850, side: 'sell' }
    ]
  }
]

// 惰性内存缓存：仅在用户真正查看某标的某周期时，0ms 按需单次生成
const intradayCache = new Map()
const klineCache = new Map()

export function getStockIntraday(symbol) {
  if (intradayCache.has(symbol)) {
    return intradayCache.get(symbol)
  }
  const stock = mockStockUniverse.find(s => s.symbol === symbol)
  const basePrice = stock ? stock.price : 100
  const data = generateIntradayData(basePrice)
  intradayCache.set(symbol, data)
  return data
}

export function getStockKline(symbol, period = 'daily') {
  const cacheKey = `${symbol}_${period}`
  if (klineCache.has(cacheKey)) {
    return klineCache.get(cacheKey)
  }
  const stock = mockStockUniverse.find(s => s.symbol === symbol)
  const basePrice = stock ? stock.price : 100
  const daysMap = { daily: 60, weekly: 80, monthly: 100, m5: 40 }
  const days = daysMap[period] || 60
  const data = generateKlineHistory(basePrice, days)
  klineCache.set(cacheKey, data)
  return data
}

