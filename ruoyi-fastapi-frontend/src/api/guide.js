import request from '@/utils/request'

// 查询子系统使用说明
export function getGuide(module) {
  return request({
    url: '/common/guide/' + module,
    method: 'get',
    silent: true
  })
}
