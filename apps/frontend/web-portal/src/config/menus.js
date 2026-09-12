/**
 * Sidebar live menus come from GET /getRouters (see store/permission.js).
 * This file is only: (1) getRouters-shaped demo fallback, (2) admin Menu.vue stub IA.
 */

/** Matches sql/sentiment-menu.sql + backend menurouter.BuildRouters shape. */
export const sentimentRouters = [
  {
    name: 'Sentiment',
    path: '/sentiment',
    hidden: false,
    redirect: 'noRedirect',
    component: 'Layout',
    alwaysShow: true,
    meta: { title: '舆情分析', icon: 'chart' },
    children: [
      {
        name: 'SentimentDashboardIndex',
        path: 'dashboard',
        hidden: false,
        component: 'sentiment/dashboard/index',
        meta: { title: '舆情大盘', icon: 'dashboard' }
      },
      {
        name: 'SentimentNewsIndex',
        path: 'news',
        hidden: false,
        component: 'sentiment/news/index',
        meta: { title: '资讯列表', icon: 'documentation' }
      },
      {
        name: 'SentimentAnalysisIndex',
        path: 'analysis',
        hidden: false,
        component: 'sentiment/analysis/index',
        meta: { title: '分析历史', icon: 'time-range' }
      }
    ]
  }
]

/** Demo/getRouters-fail sidebar only. Never the handmade market/trade tree. */
export const menuTree = [
  {
    code: 'sentiment',
    title: '舆情分析',
    icon: 'ChatDotRound',
    path: '/sentiment/dashboard',
    groups: [
      {
        code: 'children',
        title: '',
        items: [
          { title: '舆情大盘', path: '/sentiment/dashboard', icon: 'DataBoard' },
          { title: '资讯列表', path: '/sentiment/news', icon: 'Reading' },
          { title: '分析历史', path: '/sentiment/analysis', icon: 'Clock' }
        ]
      }
    ]
  }
]

/** System Menu.vue stub preview only — not consumed by Sidebar. */
export const informationArchitecture = [
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
          { title: '市场热度', path: '/market/heat', icon: 'Histogram' },
          { title: '全部股票', path: '/market/stocks', icon: 'Collection' },
          { title: '智能选股', path: '/market/recommendations', icon: 'MagicStick' },
          { title: '财经资讯', path: '/market/finance-news', icon: 'Notebook' },
          { title: '资金与日历', path: '/market/flow', icon: 'Money' },
          { title: '市场分析', path: '/market/review', icon: 'Document' },
          { title: '任务中心', path: '/analysis/jobs', icon: 'Clock' }
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

export const placeholderMeta = {}
