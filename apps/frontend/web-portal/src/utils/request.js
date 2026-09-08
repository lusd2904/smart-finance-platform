import axios from 'axios'
import { ElMessage } from 'element-plus'
import { getToken, removeToken } from './auth'

export const isRelogin = { show: false }

const service = axios.create({
  baseURL: import.meta.env.VITE_APP_BASE_API || '/dev-api',
  timeout: 60000
})

service.interceptors.request.use((config) => {
  const isToken = (config.headers || {}).isToken === false
  if (getToken() && !isToken) {
    config.headers.Authorization = `Bearer ${getToken()}`
  }
  return config
})

service.interceptors.response.use(
  (res) => {
    const payload = res.data
    const code = payload?.code
    if (code === 401) {
      if (!isRelogin.show) {
        isRelogin.show = true
        removeToken()
        ElMessage.error(payload?.msg || '登录已过期')
        window.setTimeout(() => {
          isRelogin.show = false
          if (window.location.pathname !== '/login') {
            window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`
          }
        }, 300)
      }
      return Promise.reject(new Error(payload?.msg || 'Unauthorized'))
    }
    if (code !== undefined && code !== 200 && code !== 0) {
      const message = payload?.msg || payload?.message || '请求失败'
      if (!configSilent(res.config)) {
        ElMessage.error(message)
      }
      return Promise.reject(new Error(message))
    }
    return payload
  },
  (error) => {
    const message = error?.response?.data?.msg || error?.message || '网络异常'
    if (!configSilent(error?.config)) {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  }
)

function configSilent(config) {
  return Boolean(config && (config.silent || config.headers?.silent))
}

export default service
