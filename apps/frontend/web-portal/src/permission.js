import { getToken } from '@/utils/auth'
import { useUserStore } from '@/store/user'
import { safeRedirect } from '@/utils/nav'

const whiteList = ['/login']

export function setupPermission(router) {
  router.beforeEach(async (to) => {
    document.title = `${to.meta.title || '智慧金融'} · SFP`
    const userStore = useUserStore()
    if (!userStore.usingStub) {
      userStore.hydrateDemoSession()
    }
    if (getToken() || userStore.usingStub) {
      if (to.path === '/login') return { path: safeRedirect(to.query.redirect) }
      if (!userStore.roles.length && getToken() && getToken() !== 'demo-stub-token') {
        try {
          await userStore.getInfo()
        } catch {
          await userStore.logOut()
          return { path: '/login', query: { redirect: to.fullPath } }
        }
      }
      return true
    }
    if (whiteList.includes(to.path)) return true
    return { path: '/login', query: { redirect: to.fullPath } }
  })
}
