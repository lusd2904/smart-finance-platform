import { createRouter, createWebHistory } from 'vue-router'
import { placeholderMeta } from '@/config/menus'
import { implementedPages } from './pages'

const MainLayout = () => import('@/components/layout/MainLayout.vue')

const implementedChildren = implementedPages.map((page) => ({
  path: page.path,
  name: page.path.replace(/\//g, '-'),
  component: page.component,
  meta: { title: page.title }
}))

const placeholderChildren = Object.keys(placeholderMeta).map((path) => ({
  path: path.replace(/^\//, ''),
  component: () => import('@/views/Placeholder.vue'),
  meta: { title: placeholderMeta[path].title }
}))

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
      meta: { public: true, title: '登录' }
    },
    {
      path: '/',
      component: MainLayout,
      redirect: '/index',
      children: [
        {
          path: 'index',
          name: 'Workbench',
          component: () => import('@/views/Workbench.vue'),
          meta: { title: '工作台' }
        },
        {
          path: 'market/terminal',
          name: 'MarketTerminal',
          component: () => import('@/views/Terminal.vue'),
          meta: { title: '行情交易', activeMenu: '/trade/terminal' }
        },
        {
          path: 'trade/terminal',
          name: 'TradeTerminal',
          component: () => import('@/views/Terminal.vue'),
          meta: { title: '行情交易', activeMenu: '/trade/terminal' }
        },
        ...implementedChildren,
        ...placeholderChildren
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/index'
    }
  ],
  scrollBehavior() {
    return { top: 0 }
  }
})

export default router
