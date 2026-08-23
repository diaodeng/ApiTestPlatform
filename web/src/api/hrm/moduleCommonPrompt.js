import request from '@/utils/request'

// 查询模块通用提示词分页列表
export function listModuleCommonPrompt(query) {
  return request({
    url: '/hrm/module-common-prompt/list',
    method: 'get',
    params: query
  })
}

// 查询可配置的模块编码选项
export function listModuleCommonPromptOptions(query) {
  return request({
    url: '/hrm/module-common-prompt/options',
    method: 'get',
    params: query
  })
}

// 查询模块通用提示词详情
export function getModuleCommonPrompt(promptId) {
  return request({
    url: '/hrm/module-common-prompt/' + promptId,
    method: 'get'
  })
}

// 新增模块通用提示词
export function addModuleCommonPrompt(data) {
  return request({
    url: '/hrm/module-common-prompt',
    method: 'post',
    data
  })
}

// 修改模块通用提示词
export function updateModuleCommonPrompt(data) {
  return request({
    url: '/hrm/module-common-prompt',
    method: 'put',
    data
  })
}

// 删除模块通用提示词
export function delModuleCommonPrompt(promptId) {
  return request({
    url: '/hrm/module-common-prompt/' + promptId,
    method: 'delete'
  })
}
