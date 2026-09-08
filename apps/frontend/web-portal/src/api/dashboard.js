import request from '@/utils/request'

export function getDashboardSummary(query) {
  return request({
    url: '/dashboard/summary',
    method: 'get',
    params: query,
    silent: true
  })
}
