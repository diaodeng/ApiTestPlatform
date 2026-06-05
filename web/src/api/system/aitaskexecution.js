import request from '@/utils/request'

function sanitizeQueryParams(query) {
  return Object.fromEntries(
    Object.entries(query || {}).filter(
      ([, value]) => value !== undefined && value !== null && value !== ''
    )
  )
}

// 查询 AI 执行审计列表
export function listAiTaskExecution(query) {
  return request({
    url: '/system/aitaskexecution/list',
    method: 'get',
    params: sanitizeQueryParams(query),
  })
}

// 查询 AI 执行审计详情
export function getAiTaskExecution(executionId) {
  return request({
    url: `/system/aitaskexecution/${executionId}`,
    method: 'get',
  })
}
