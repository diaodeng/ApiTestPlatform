import request from '@/utils/request'

// 查询AI聚合配置页数据
export function getAiConfigSummary() {
  return request({
    url: '/system/aiconfig/summary',
    method: 'get',
  })
}

// 保存AI聚合配置
export function updateAiConfig(data) {
  return request({
    url: '/system/aiconfig',
    method: 'put',
    data,
  })
}
