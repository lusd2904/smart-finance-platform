import { defineStore } from 'pinia'
import { getRouters } from '@/api/menu'
import { menuTree } from '@/config/menus'
import router from '@/router'
import { implementedPages, loadView } from '@/router/pages'
import { unwrap, unwrapList } from '@/utils/list'
import { useUserStore } from '@/store/user'

const ICON_MAP = {
  chart: 'ChatDotRound',
  dashboard: 'DataBoard',
  documentation: 'Reading',
  'time-range': 'Clock',
  edit: 'Edit',
  user: 'User',
  peoples: 'UserFilled',
  tree: 'Menu',
  system: 'Setting',
  money: 'Wallet',
  example: 'Grid',
  monitor: 'Monitor',
  redis: 'Coin',
  server: 'Cpu',
  guide: 'Guide',
  skill: 'MagicStick',
  build: 'SetUp',
  log: 'Document',
  date: 'Calendar',
  job: 'Clock',
  form: 'Tickets',
  dict: 'Collection',
  online: 'Connection',
  swagger: 'Document',
  cascader: 'Share',
  validCode: 'Key',
  color: 'Brush',
  tool: 'Tools',
  row: 'List',
  druid: 'DataLine',
  code: 'Cpu',
  nested: 'Menu'
}

function mapIcon(icon) {
  if (!icon) return 'Menu'
  if (ICON_MAP[icon]) return ICON_MAP[icon]
  const pascal = String(icon)
    .split(/[-_]/)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join('')
  return pascal || 'Menu'
}

function joinPath(base, child) {
  const c = String(child || '')
  if (!c) return normalizePath(base)
  if (c.startsWith('/')) return normalizePath(c)
  const b = String(base || '').replace(/\/+$/, '')
  if (!b || b === '/') return normalizePath(`/${c}`)
  return normalizePath(`${b}/${c}`)
}

function normalizePath(path) {
  const p = `/${String(path || '').replace(/^\/+/, '')}`.replace(/\/+/g, '/')
  return p === '/' ? '/' : p.replace(/\/+$/, '')
}

function componentToPath(component) {
  if (!component || ['Layout', 'ParentView', 'InnerLink'].includes(component)) return ''
  const key = String(component).replace(/^\//, '').replace(/\/index$/, '')
  if (loadView(component) || implementedPages.some((p) => p.path === key)) return `/${key}`
  return `/${key}`
}

function titleOf(route) {
  return route?.meta?.title || route?.name || ''
}

function flattenChildren(route, parentPath) {
  const out = []
  for (const child of route.children || []) {
    if (child.hidden) continue
    const path = componentToPath(child.component) || joinPath(parentPath, child.path)
    const nested = child.children || []
    if (nested.length && (child.component === 'ParentView' || child.component === 'Layout')) {
      out.push(...flattenChildren(child, path))
      continue
    }
    out.push({
      title: titleOf(child),
      path,
      icon: mapIcon(child.meta?.icon),
      component: child.component
    })
  }
  return out
}

export function mapRoutersToSidebar(routers) {
  return (routers || [])
    .filter((r) => r && !r.hidden)
    .map((r) => {
      const parentPath = r.path || ''
      const items = flattenChildren(r, parentPath)
      const code = String(parentPath || r.name || titleOf(r))
        .replace(/^\//, '')
        .split('/')[0] || 'menu'
      const leaf = !r.alwaysShow && items.length <= 1
      return {
        code,
        title: titleOf(r) || items[0]?.title || code,
        icon: mapIcon(r.meta?.icon || items[0]?.icon),
        path: leaf ? items[0]?.path || normalizePath(parentPath) : items[0]?.path || normalizePath(parentPath),
        groups: leaf || !items.length ? [] : [{ code: 'children', title: '', items }]
      }
    })
    .filter((s) => s.title)
}

function registerRoutes(routers, parentPath = '') {
  for (const r of routers || []) {
    if (r.hidden) continue
    const path = joinPath(parentPath, r.path)
    const comp = loadView(r.component)
    const name = r.name || path.replace(/\//g, '-') || `r-${Math.random().toString(36).slice(2, 7)}`
    if (comp && path && path !== '/' && !router.hasRoute(name)) {
      router.addRoute('/', {
        path: path.replace(/^\//, ''),
        name,
        component: comp,
        meta: { title: r.meta?.title || name }
      })
    }
    if (r.children?.length) registerRoutes(r.children, path === '/' ? '' : path)
  }
}

function parseRouterPayload(res) {
  const raw = unwrap(res)
  if (Array.isArray(raw)) return raw
  if (Array.isArray(raw.data)) return raw.data
  return unwrapList(res)
}

export const usePermissionStore = defineStore('permission', {
  state: () => ({
    ready: false,
    source: '',
    routers: [],
    sidebarTree: []
  }),
  actions: {
    async generateRoutes() {
      const user = useUserStore()
      const live = Boolean(user.token && user.token !== 'demo-stub-token' && !user.usingStub)
      try {
        const res = await getRouters()
        const routers = parseRouterPayload(res)
        if (!routers.length) throw new Error('empty routers')
        this.routers = routers
        this.sidebarTree = mapRoutersToSidebar(routers)
        registerRoutes(routers)
        this.source = 'getRouters'
        this.ready = true
        return this.sidebarTree
      } catch (e) {
        if (live) {
          this.routers = []
          this.sidebarTree = []
          this.source = 'getRouters-failed'
          this.ready = true
          throw e
        }
        this.routers = []
        this.sidebarTree = menuTree
        this.source = 'menus.js'
        this.ready = true
        return this.sidebarTree
      }
    },
    reset() {
      this.ready = false
      this.source = ''
      this.routers = []
      this.sidebarTree = []
    }
  }
})
