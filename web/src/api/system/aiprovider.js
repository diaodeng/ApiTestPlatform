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
export function listAiProviderOptions(params) {
  return request({
    url: '/system/aiprovider/options',
    method: 'get',
    params
  })
}

// 查询 AI Provider 元数据选项
export function getAiProviderMetadataOptions() {
  return request({
    url: '/system/aiprovider/metadata/options',
    method: 'get'
  })
}

// 使用未保存 Provider 草稿探测模型目录
export function previewAiProviderModelCatalog(data) {
  return request({
    url: '/system/aiprovider/model-catalog/preview',
    method: 'post',
    data
  })
}

// 查询已保存 Provider 的模型目录缓存
export function listAiProviderModelCatalog(providerId) {
  return request({
    url: `/system/aiprovider/${providerId}/model-catalog`,
    method: 'get'
  })
}

// 刷新已保存 Provider 的模型目录
export function refreshAiProviderModelCatalog(providerId) {
  return request({
    url: `/system/aiprovider/${providerId}/model-catalog/refresh`,
    method: 'post'
  })
}

// 校验当前用户密码后查看 Provider 密钥
export function viewAiProviderSecret(providerId, data) {
  return request({
    url: `/system/aiprovider/${providerId}/secret/view`,
    method: 'post',
    data
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
