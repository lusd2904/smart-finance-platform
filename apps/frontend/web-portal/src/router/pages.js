export const implementedPages = [
  { path: 'market/heat', title: '三市场热度', component: () => import('@/views/market/Heat.vue') },
  { path: 'market/board', title: '行情台', component: () => import('@/views/market/Board.vue') },
  { path: 'market/watchlist', title: '自选清单', component: () => import('@/views/market/Watchlist.vue') },
  { path: 'market/stocks', title: '全部股票', component: () => import('@/views/market/Stocks.vue') },
  { path: 'market/recommendations', title: '智能选股', component: () => import('@/views/market/Recommendations.vue') },
  { path: 'market/finance-news', title: '财经资讯', component: () => import('@/views/market/FinanceNews.vue') },
  { path: 'market/flow', title: '资金与日历', component: () => import('@/views/market/Flow.vue') },
  { path: 'market/review', title: '市场分析', component: () => import('@/views/market/Review.vue') },
  { path: 'analysis/jobs', title: '自动分析', component: () => import('@/views/analysis/Jobs.vue') }
]
