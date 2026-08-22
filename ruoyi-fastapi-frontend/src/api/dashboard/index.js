import request from '@/utils/request'

// 工作台均衡总览聚合：一次返回资产/行情/热度/自选信号/舆情/简报/运行状态
export function getDashboardSummary(query) {
  return request({
    url: '/dashboard/summary',
    method: 'get',
    params: query
  })
}
