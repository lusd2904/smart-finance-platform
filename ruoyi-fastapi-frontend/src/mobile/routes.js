/** Independent mobile H5 route tree. PC admin routes stay untouched. */

export const mobileRoutes = [
  {
    path: '/m/login',
    name: 'MobileLogin',
    component: () => import('@/mobile/views/Login.vue'),
    hidden: true,
    meta: { title: '登录', mobile: true }
  },
  {
    path: '/m',
    component: () => import('@/mobile/components/MobileShell.vue'),
    hidden: true,
    meta: { mobile: true },
    children: [
      {
        path: '',
        name: 'MobileHeat',
        component: () => import('@/mobile/views/Heat.vue'),
        meta: { title: '热度', tab: 'heat', mobile: true }
      },
      {
        path: 'sentiment',
        name: 'MobileSentiment',
        component: () => import('@/mobile/views/Sentiment.vue'),
        meta: { title: '舆情', tab: 'sentiment', mobile: true }
      },
      {
        path: 'picks',
        name: 'MobilePicks',
        component: () => import('@/mobile/views/Picks.vue'),
        meta: { title: '选股', tab: 'picks', mobile: true }
      },
      {
        path: 'positions',
        name: 'MobilePositions',
        component: () => import('@/mobile/views/Positions.vue'),
        meta: { title: '持仓', tab: 'positions', mobile: true }
      },
      {
        path: 'me',
        name: 'MobileMe',
        component: () => import('@/mobile/views/Me.vue'),
        meta: { title: '我的', tab: 'me', mobile: true }
      },
      {
        path: 'symbol/:code',
        name: 'MobileSymbol',
        component: () => import('@/mobile/views/Symbol.vue'),
        meta: { title: '标的', hideTab: true, mobile: true }
      }
    ]
  }
]
