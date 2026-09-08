/**
 * Static SFP information architecture (matches live sidebar / getRouters modules).
 * Pages without a v2 implementation route to Placeholder.
 */
export const menuTree = [
  {
    code: 'workspace',
    title: '工作台',
    icon: 'Odometer',
    path: '/index',
    groups: []
  },
  {
    code: 'market',
    title: '行情中心',
    icon: 'TrendCharts',
    path: '/market/heat',
    groups: [
      {
        code: 'desk',
        title: '盯盘',
        items: [
          { title: '行情交易', path: '/market/terminal', icon: 'Monitor' },
          { title: '行情台', path: '/market/board', icon: 'DataLine' },
          { title: '自选清单', path: '/market/watchlist', icon: 'Star' }
        ]
      },
      {
        code: 'research',
        title: '研究',
        items: [
          { title: '三市场热度', path: '/market/heat', icon: 'Histogram' },
          { title: '全部股票', path: '/market/stocks', icon: 'Collection' },
          { title: '智能选股', path: '/market/recommendations', icon: 'MagicStick' },
          { title: '财经资讯', path: '/market/finance-news', icon: 'Notebook' },
          { title: '资金与日历', path: '/market/flow', icon: 'Money' },
          { title: '市场分析', path: '/market/review', icon: 'Document' }
        ]
      }
    ]
  },
  {
    code: 'trade',
    title: '交易中心',
    icon: 'Wallet',
    path: '/trade/terminal',
    groups: [
      {
        code: 'core',
        title: '交易',
        items: [
          { title: '行情交易', path: '/trade/terminal', icon: 'Monitor' },
          { title: '持仓', path: '/trade/positions', icon: 'List' },
          { title: '委托', path: '/trade/orders', icon: 'Tickets' },
          { title: '风控', path: '/trade/risk', icon: 'Warning' },
          { title: '通知中心', path: '/trade/notifications', icon: 'Bell' }
        ]
      }
    ]
  },
  {
    code: 'quant',
    title: '量化交易',
    icon: 'Cpu',
    path: '/quant/strategy',
    groups: [
      {
        code: 'research',
        title: '研究',
        items: [
          { title: '因子分析', path: '/quant/factor', icon: 'DataAnalysis' },
          { title: '策略信号', path: '/quant/strategy', icon: 'Guide' },
          { title: '长桥配置', path: '/quant/longbridge', icon: 'Connection' }
        ]
      }
    ]
  },
  {
    code: 'sentiment',
    title: '舆情分析',
    icon: 'ChatDotRound',
    path: '/sentiment/dashboard',
    groups: [
      {
        code: 'core',
        title: '舆情',
        items: [
          { title: '舆情大盘', path: '/sentiment/dashboard', icon: 'DataBoard' },
          { title: '资讯列表', path: '/sentiment/news', icon: 'Reading' },
          { title: '分析历史', path: '/sentiment/analysis', icon: 'Clock' }
        ]
      }
    ]
  },
  {
    code: 'ai',
    title: 'AI 研判',
    icon: 'MagicStick',
    path: '/ai/model',
    groups: [
      {
        code: 'core',
        title: 'AI',
        items: [
          { title: '模型管理', path: '/ai/model', icon: 'SetUp' },
          { title: '研判工作台', path: '/ai/chat', icon: 'ChatLineSquare' }
        ]
      }
    ]
  },
  {
    code: 'system',
    title: '系统管理',
    icon: 'Setting',
    path: '/system/user',
    groups: [
      {
        code: 'iam',
        title: '账户',
        items: [
          { title: '用户管理', path: '/system/user', icon: 'User' },
          { title: '角色管理', path: '/system/role', icon: 'UserFilled' },
          { title: '菜单管理', path: '/system/menu', icon: 'Menu' }
        ]
      }
    ]
  }
]

export const placeholderMeta = {
  '/market/heat': { title: '三市场热度', module: '行情中心' },
  '/market/board': { title: '行情台', module: '行情中心' },
  '/market/watchlist': { title: '自选清单', module: '行情中心' },
  '/market/stocks': { title: '全部股票', module: '行情中心' },
  '/market/recommendations': { title: '智能选股', module: '行情中心' },
  '/market/finance-news': { title: '财经资讯', module: '行情中心' },
  '/market/flow': { title: '资金与日历', module: '行情中心' },
  '/market/review': { title: '市场分析', module: '行情中心' },
  '/analysis/jobs': { title: '自动分析', module: '行情中心' },
  '/trade/positions': { title: '持仓', module: '交易中心' },
  '/trade/orders': { title: '委托', module: '交易中心' },
  '/trade/risk': { title: '风控', module: '交易中心' },
  '/trade/notifications': { title: '通知中心', module: '交易中心' },
  '/quant/factor': { title: '因子分析', module: '量化交易' },
  '/quant/strategy': { title: '策略信号', module: '量化交易' },
  '/quant/longbridge': { title: '长桥配置', module: '量化交易' },
  '/sentiment/dashboard': { title: '舆情大盘', module: '舆情分析' },
  '/sentiment/news': { title: '资讯列表', module: '舆情分析' },
  '/sentiment/analysis': { title: '分析历史', module: '舆情分析' },
  '/ai/model': { title: '模型管理', module: 'AI 研判' },
  '/ai/chat': { title: '研判工作台', module: 'AI 研判' },
  '/system/user': { title: '用户管理', module: '系统管理' },
  '/system/role': { title: '角色管理', module: '系统管理' },
  '/system/menu': { title: '菜单管理', module: '系统管理' }
}
