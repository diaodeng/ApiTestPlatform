import request from '@/utils/request'

function sanitizeQueryParams(query) {
  return Object.fromEntries(
    Object.entries(query || {}).filter(
      ([, value]) => value !== undefined && value !== null && value !== ''
    )
  )
}

// 查询AI提示词模板列表
export function listAiPromptTemplate(query) {
  return request({
    url: '/system/aiprompt/list',
    method: 'get',
    params: sanitizeQueryParams(query),
  })
}

// 查询AI提示词模板选项
export function listAiPromptTemplateOptions(query) {
  return request({
    url: '/system/aiprompt/options',
    method: 'get',
    params: sanitizeQueryParams(query),
  })
}

// 查询AI提示词模板详情
export function getAiPromptTemplate(templateId) {
  return request({
    url: `/system/aiprompt/${templateId}`,
    method: 'get',
  })
}

// 新增AI提示词模板
export function addAiPromptTemplate(data) {
  return request({
    url: '/system/aiprompt',
    method: 'post',
    data,
  })
}

// 修改AI提示词模板
export function updateAiPromptTemplate(data) {
  return request({
    url: '/system/aiprompt',
    method: 'put',
    data,
  })
}

// 删除AI提示词模板
export function delAiPromptTemplate(templateId) {
  return request({
    url: `/system/aiprompt/${templateId}`,
    method: 'delete',
  })
}
