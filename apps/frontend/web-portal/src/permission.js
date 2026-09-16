import { getToken } from '@/utils/auth'
import { useUserStore } from '@/store/user'
import { usePermissionStore } from '@/store/permission'
import { safeRedirect } from '@/utils/nav'

const whiteList = ['/login']

export function setupPermission(router) {
  router.beforeEach(async (to) => {
    document.title = `${to.meta.title || '智慧金融'} · SFP`
    const userStore = useUserStore()
    const permissionStore = usePermissionStore()
    if (!userStore.usingStub) {
      userStore.hydrateDemoSession()
    }
    if (getToken() || userStore.usingStub) {
      if (to.path === '/login') return { path: safeRedirect(to.query.redirect) }
      const live = getToken() && getToken() !== 'demo-stub-token'
      if (live && !userStore.roles.length) {
        try {
          await userStore.getInfo()
        } catch {
          await userStore.logOut()
          permissionStore.reset()
          return { path: '/login', query: { redirect: to.fullPath } }
        }
      }
      if (!permissionStore.ready) {
        try {
          await permissionStore.generateRoutes()
        } catch {
          /* live: empty sidebar, no handmade market tree; demo already used getRouters-shaped fallback */
        }
      }
      return true
    }
    if (whiteList.includes(to.path)) return true
    return { path: '/login', query: { redirect: to.fullPath } }
  })
}
