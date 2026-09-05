import router from './router'
import { ElMessage } from 'element-plus'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { getToken } from '@/utils/auth'
import { isHttp, isPathMatch } from '@/utils/validate'
import { isRelogin } from '@/utils/request'
import useUserStore from '@/store/modules/user'
import useSettingsStore from '@/store/modules/settings'
import usePermissionStore from '@/store/modules/permission'
import { isMobilePath, parseMFlag, persistShellForce, readShellForce, shellForceRedirect } from '@/mobile/guard'

NProgress.configure({ showSpinner: false })

const whiteList = ['/login', '/register', '/m/login']
const isWhiteList = (path) => {
  return whiteList.some(pattern => isPathMatch(pattern, path))
}

async function ensureSession(to, onFailPath) {
  if (useUserStore().roles.length !== 0) return true
  isRelogin.show = true
  try {
    await useUserStore().getInfo()
    isRelogin.show = false
    try {
      const accessRoutes = await usePermissionStore().generateRoutes()
      accessRoutes.forEach(route => {
        if (!isHttp(route.path)) {
          router.addRoute(route)
        }
      })
    } catch (menuErr) {
      // /m constant routes are already registered; a menu fetch failure must not block the phone shell.
      if (!isMobilePath(to.path)) throw menuErr
    }
    return { ...to, replace: true }
  } catch (err) {
    isRelogin.show = false
    await useUserStore().logOut()
    ElMessage.error(err)
    if (isMobilePath(to.path) && to.path !== '/m/login') {
      return { path: onFailPath, query: { redirect: to.fullPath } }
    }
    return { path: onFailPath }
  }
}

router.beforeEach(async (to) => {
  NProgress.start()

  // Gray-test force switches. Query wins and is persisted to sfp_m; nginx UA routing comes later.
  const queryFlag = parseMFlag(to.query && to.query.m)
  if (queryFlag != null) persistShellForce(queryFlag)
  const shellForce = queryFlag != null ? queryFlag : readShellForce(to.query)
  const forced = shellForceRedirect(to.path, shellForce, !!getToken())
  if (forced) {
    NProgress.done()
    return { path: forced }
  }

  if (isMobilePath(to.path)) {
    if (getToken()) {
      to.meta.title && useSettingsStore().setTitle(to.meta.title)
      if (to.path === '/m/login') {
        NProgress.done()
        return { path: '/m' }
      }
      return ensureSession(to, '/m/login')
    }
    if (to.path === '/m/login') {
      return true
    }
    NProgress.done()
    return `/m/login?redirect=${encodeURIComponent(to.fullPath)}`
  }

  if (getToken()) {
    to.meta.title && useSettingsStore().setTitle(to.meta.title)
    if (to.path === '/login') {
      NProgress.done()
      return { path: '/portal' }
    }
    return ensureSession(to, '/')
  }
  if (isWhiteList(to.path)) {
    return true
  }
  NProgress.done()
  return `/login?redirect=${to.fullPath}`
})

router.afterEach(() => {
  NProgress.done()
})
