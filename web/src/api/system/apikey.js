import request from '@/utils/request'

// 查询 API Key 列表
export function listApiKey(query) {
  return request({
    url: '/system/apikey/list',
    method: 'get',
    params: query
  })
}

// 查询 API Key 详情
export function getApiKey(apiKeyId) {
  return request({
    url: '/system/apikey/' + apiKeyId,
    method: 'get'
  })
}

// 查询当前用户可授权的 API Key 权限选项
export function listApiKeyPermissionOptions() {
  return request({
    url: '/system/apikey/permissionOptions',
    method: 'get'
  })
}

// 新增 API Key
export function addApiKey(data) {
  return request({
    url: '/system/apikey',
    method: 'post',
    data: data
  })
}

// 查看 API Key 明文
export function viewApiKey(apiKeyId, data) {
  return request({
    url: '/system/apikey/' + apiKeyId + '/view',
    method: 'post',
    data: data
  })
}

// 手动过期 API Key
export function expireApiKey(apiKeyId) {
  return request({
    url: '/system/apikey/' + apiKeyId + '/expire',
    method: 'post'
  })
}

// 删除 API Key
export function delApiKey(apiKeyId) {
  return request({
    url: '/system/apikey/' + apiKeyId,
    method: 'delete'
  })
}
