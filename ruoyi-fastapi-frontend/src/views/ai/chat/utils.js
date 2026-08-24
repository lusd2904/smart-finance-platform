// AI 聊天页共享的小工具函数（无状态，供多个子组件复用）

export function formatTime(timeStr) {
  if (!timeStr) return ''
  try {
    const date = new Date(timeStr)
    return date.toLocaleString()
  } catch {
    return timeStr
  }
}

export function getImageUrl(url) {
  if (!url) return ''
  if (url.startsWith('http') || url.startsWith('https') || url.startsWith('blob:')) {
    return url
  }
  return import.meta.env.VITE_APP_BASE_API + url
}
