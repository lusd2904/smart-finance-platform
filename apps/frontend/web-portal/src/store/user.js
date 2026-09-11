import { defineStore } from 'pinia'
import { login as loginApi, logout as logoutApi, getInfo } from '@/api/auth'
import { getToken, setToken, removeToken } from '@/utils/auth'

const DEMO_SESSION_KEY = 'sfp-demo-session'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: getToken(),
    id: '',
    name: '',
    nickName: '',
    roles: [],
    permissions: [],
    usingStub: false
  }),
  getters: {
    displayName: (state) => state.nickName || state.name || '用户'
  },
  actions: {
    async login(userInfo) {
      const username = userInfo.username.trim()
      const res = await loginApi(username, userInfo.password, userInfo.code, userInfo.uuid)
      const token = res.token || res.access_token
      if (!token) throw new Error(res.msg || '登录失败')
      setToken(token)
      this.token = token
      this.usingStub = false
    },
    async getInfo() {
      const res = await getInfo()
      const user = res.user || {}
      this.roles = res.roles?.length ? res.roles : ['ROLE_DEFAULT']
      this.permissions = res.permissions || []
      this.id = user.userId
      this.name = user.userName
      this.nickName = user.nickName
      this.usingStub = false
      return res
    },
    enterDemoSession() {
      this.token = 'demo-stub-token'
      this.id = 0
      this.name = 'demo'
      this.nickName = '演示用户'
      this.roles = ['ROLE_DEMO']
      this.permissions = []
      this.usingStub = true
      setToken('demo-stub-token')
      if (typeof sessionStorage !== 'undefined') {
        sessionStorage.setItem(DEMO_SESSION_KEY, '1')
      }
    },
    hydrateDemoSession() {
      if (typeof sessionStorage === 'undefined') return false
      if (sessionStorage.getItem(DEMO_SESSION_KEY) !== '1') return false
      this.enterDemoSession()
      return true
    },
    async logOut() {
      try {
        if (this.token && this.token !== 'demo-stub-token') {
          await logoutApi()
        }
      } catch {
        /* still clear local session */
      }
      this.token = ''
      this.roles = []
      this.permissions = []
      this.usingStub = false
      removeToken()
      if (typeof sessionStorage !== 'undefined') {
        sessionStorage.removeItem(DEMO_SESSION_KEY)
      }
      try {
        const { usePermissionStore } = await import('./permission')
        usePermissionStore().reset()
      } catch {
        /* store may not be ready */
      }
    }
  }
})
