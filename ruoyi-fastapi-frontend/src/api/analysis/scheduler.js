import request from '@/utils/request'

export function getAnalysisOverview() {
  return request({
    url: '/analysis/scheduler/overview',
    method: 'get'
  })
}

export function changeAnalysisJobStatus(jobId, status) {
  return request({
    url: `/analysis/scheduler/jobs/${jobId}/status`,
    method: 'put',
    data: { status }
  })
}

export function runAnalysisJob(jobId) {
  return request({
    url: `/analysis/scheduler/jobs/${jobId}/run`,
    method: 'post',
    timeout: 20000
  })
}

export function listAnalysisJobLogs(jobId, query) {
  return request({
    url: `/analysis/scheduler/jobs/${jobId}/logs`,
    method: 'get',
    params: query
  })
}
