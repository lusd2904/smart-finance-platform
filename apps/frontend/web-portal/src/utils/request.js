import axios from 'axios'
import { ElMessage } from 'element-plus'
import { getToken, removeToken } from './auth'
import { sanitizePublicText } from './secret'

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
    if (isBrokerAuthFailure(payload, res.config, res.status)) {
      return Promise.reject(brokerAuthError(payload, code || 401))
    }
    if (code === 401) {
      if (isDemoSession()) {
        return Promise.reject(new Error(sanitizePublicText(payload?.msg, 'Unauthorized')))
      }
      if (!isRelogin.show) {
        isRelogin.show = true
        removeToken()
        ElMessage.error(sanitizePublicText(payload?.msg, '登录已过期'))
        window.setTimeout(() => {
          isRelogin.show = false
          if (window.location.pathname !== '/login') {
            window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`
          }
        }, 300)
      }
      return Promise.reject(new Error(sanitizePublicText(payload?.msg, 'Unauthorized')))
    }
    if (code !== undefined && code !== 200 && code !== 0) {
      const message = sanitizePublicText(payload?.msg || payload?.message, '请求失败')
      if (!configSilent(res.config)) {
        ElMessage.error(message)
      }
      return Promise.reject(new Error(message))
    }
    return payload
  },
  (error) => {
    const payload = error?.response?.data
    if (isBrokerAuthFailure(payload, error?.config, error?.response?.status)) {
      return Promise.reject(brokerAuthError(payload, payload?.code || error?.response?.status || 401))
    }
    const message = sanitizePublicText(payload?.msg || error?.message, '网络异常')
    if (!configSilent(error?.config)) {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  }
)

function isDemoSession() {
  try {
    if (typeof sessionStorage !== 'undefined' && sessionStorage.getItem('sfp-demo-session') === '1') return true
  } catch {
    /* ignore */
  }
  return getToken() === 'demo-stub-token'
}

function configSilent(config) {
  return Boolean(config && (config.silent || config.headers?.silent))
}

function requestUrl(config) {
  return String(config?.url || '')
}

function isTradeOrLongbridge(url) {
  return /\/trade\/|\/quant\/longbridge/.test(url)
}

function isBrokerAuthFailure(payload, config, httpStatus) {
  const code = Number(payload?.code)
  const msg = String(payload?.msg || payload?.message || payload?.error || '')
  const url = requestUrl(config)
  if (code === 401004) return true
  if (isTradeOrLongbridge(url) && (code === 401 || httpStatus === 401)) return true
  if (isTradeOrLongbridge(url) && /401004|access token|longbridge|凭证|未配置/.test(msg)) return true
  return false
}

function brokerAuthError(payload, code) {
  const err = new Error(sanitizePublicText(payload?.msg || payload?.message, '长桥凭证不可用'))
  err.brokerAuth = true
  err.code = code
  return err
}

export default service
