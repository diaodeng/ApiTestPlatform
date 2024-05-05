import request from '@/utils/request'

// 查询模块列表
export function listModule(query) {
  return request({
    url: '/hrm/module/list',
    method: 'get',
    params: query
  })
}

// 查询模块列表不分页-根据项目ID查询
export function selectModulList(query) {
  return request({
    url: '/hrm/module/selectModuleList',
    method: 'get',
    params: query
  })
}

// 查询模块列表不分页-查询所有
export function showModulList(query) {
  return request({
    url: '/hrm/module/showModuleList',
    method: 'get',
    params: query
  })
}

// 查询模块详细
export function getModule(moduleId) {
  return request({
    url: '/hrm/module/' + moduleId,
    method: 'get'
  })
}

// 新增模块
export function addModule(data) {
  return request({
    url: '/hrm/module',
    method: 'post',
    data: data
  })
}

// 修改模块
export function updateModule(data) {
  return request({
    url: '/hrm/module',
    method: 'put',
    data: data
  })
}

// 删除模块
export function delModule(moduleId) {
  return request({
    url: '/hrm/module/' + moduleId,
    method: 'delete'
  })
}
