import request from '@/utils/request'

export function getRouters() {
  return request({ url: '/getRouters', method: 'get' })
}
