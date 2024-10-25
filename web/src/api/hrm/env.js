import request from '@/utils/request'

// 查询环境列表
export function listEnv(query) {
  return request({
    url: '/hrm/env/list',
    method: 'get',
    params: query
  })
}

/*
* 查询所有环境
* */
export function allEnv(query) {
  return request({
    url: '/hrm/env/all',
    method: 'get',
    params: query
  })
}

// 查询环境详细
export function getEnv(envId) {
  return request({
    url: '/hrm/env/' + envId,
    method: 'get'
  })
}

// 新增环境
export function addEnv(data) {
  return request({
    url: '/hrm/env',
    method: 'post',
    data: data
  })
}

// 修改环境
export function updateEnv(data) {
  return request({
    url: '/hrm/env',
    method: 'put',
    data: data
  })
}

// 删除环境
export function delEnv(envId) {
  return request({
    url: '/hrm/env/' + envId,
    method: 'delete'
  })
}