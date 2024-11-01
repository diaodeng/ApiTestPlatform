import request from '@/utils/request'

// 查询所有转发规则
export function all() {
  return request({
    url: '/qtr/forwardRules/list',
    method: 'get'
  })
}

// 查询转发规则列表
export function list(query) {
  return request({
    url: '/qtr/forwardRules/list',
    method: 'get',
    params: query
  })
}


// 查询转发规则详细
export function getDetail(dataId) {
  return request({
    url: '/qtr/forwardRules/' + dataId,
    method: 'get'
  })
}

// 新增转发规则
export function addRules(data) {
  return request({
    url: '/qtr/forwardRules',
    method: 'post',
    data: data
  })
}

// 复制转发规则
export function copyRules(data) {
  return request({
    url: '/qtr/forwardRules/copy',
    method: 'post',
    data: data
  })
}

// 修改转发规则状态
export function changeRulesStatus(data) {
  return request({
    url: '/qtr/forwardRules/changeStatus/',
    method: 'post',
    data: data
  })
}

// 修改转发规则
export function updateRules(data) {
  return request({
    url: '/qtr/forwardRules/',
    method: 'put',
    data: data
  })
}

// 删除转发规则
export function delRules(deleteData) {
  return request({
    url: '/qtr/forwardRules',
    method: 'delete',
    data:deleteData
  })
}