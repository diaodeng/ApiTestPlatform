import request from '@/utils/request'

// 查询当前用户配置列表
export function listCurrentUserConfigs(query) {
  return request({
    url: '/system/user-config/current',
    method: 'get',
    params: query
  })
}

// 查询当前用户单个配置
export function getCurrentUserConfig(configType, configKey) {
  return request({
    url: `/system/user-config/current/${configType}/${configKey}`,
    method: 'get',
    showErrorMessage: false,
    showErrorNotification: false
  })
}

// 保存当前用户配置
export function saveCurrentUserConfig(data) {
  return request({
    url: '/system/user-config/current',
    method: 'put',
    data
  })
}
