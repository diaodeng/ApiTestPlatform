import request from '@/utils/request'

// 查询 AI Provider 列表
export function listAiProvider(query) {
  return request({
    url: '/system/aiprovider/list',
    method: 'get',
    params: query
  })
}

// 查询可选 AI Provider
export function listAiProviderOptions() {
  return request({
    url: '/system/aiprovider/options',
    method: 'get'
  })
}

// 查询 AI Provider 详情
export function getAiProvider(providerId) {
  return request({
    url: `/system/aiprovider/${providerId}`,
    method: 'get'
  })
}

// 新增 AI Provider
export function addAiProvider(data) {
  return request({
    url: '/system/aiprovider',
    method: 'post',
    data
  })
}

// 修改 AI Provider
export function updateAiProvider(data) {
  return request({
    url: '/system/aiprovider',
    method: 'put',
    data
  })
}

// 删除 AI Provider
export function delAiProvider(providerId) {
  return request({
    url: `/system/aiprovider/${providerId}`,
    method: 'delete'
  })
}
