import { getToken } from '@/utils/auth'
import { useUserStore } from '@/store/user'

const whiteList = ['/login']

export function setupPermission(router) {
  router.beforeEach(async (to) => {
    document.title = `${to.meta.title || '智慧金融'} · SFP`
    if (getToken() || useUserStore().usingStub) {
      if (to.path === '/login') return { path: '/index' }
      if (!useUserStore().roles.length && getToken() && getToken() !== 'demo-stub-token') {
        try {
          await useUserStore().getInfo()
        } catch {
          await useUserStore().logOut()
          return { path: '/login', query: { redirect: to.fullPath } }
        }
      }
      return true
    }
    if (whiteList.includes(to.path)) return true
    return { path: '/login', query: { redirect: to.fullPath } }
  })
}
