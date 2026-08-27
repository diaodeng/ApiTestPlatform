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

// 查询已保存 Provider 的模型目录缓存（仅已启用）
export function listAiProviderModelCatalog(providerId) {
  return request({
    url: `/system/aiprovider/${providerId}/model-catalog`,
    method: 'get'
  })
}

// 查询已保存 Provider 的全部模型目录（含已禁用）
export function listAiProviderAllModelCatalog(providerId) {
  return request({
    url: `/system/aiprovider/${providerId}/model-catalog/all`,
    method: 'get'
  })
}

// 从远端API拉取并持久化模型目录
export function refreshAiProviderModelCatalog(providerId) {
  return request({
    url: `/system/aiprovider/${providerId}/model-catalog/refresh`,
    method: 'put'
  })
}

// 手动添加模型目录项
export function addAiProviderModelCatalogItem(providerId, data) {
  return request({
    url: `/system/aiprovider/${providerId}/model-catalog/items`,
    method: 'post',
    data
  })
}

// 启用/禁用模型目录项
export function toggleAiProviderModelCatalogItem(providerId, modelId, data) {
  return request({
    url: `/system/aiprovider/${providerId}/model-catalog/items/${modelId}/toggle`,
    method: 'put',
    data
  })
}

// 删除人工添加的模型目录项
export function delAiProviderModelCatalogItem(providerId, modelId) {
  return request({
    url: `/system/aiprovider/${providerId}/model-catalog/items/${modelId}`,
    method: 'delete'
  })
}

// 按Provider编码获取可用模型下拉选项
export function listAiProviderModelOptions(providerCode) {
  return request({
    url: `/system/aiprovider/options/${providerCode}/models`,
    method: 'get'
  })
}

// 使用当前表单草稿测试 Provider 默认模型
export function testAiProviderConnection(data) {
  return request({
    url: '/system/aiprovider/connection/test',
    method: 'post',
    data
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
