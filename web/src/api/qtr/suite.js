import request from '@/utils/request'

// 查询环境列表
export function listSuite(query) {
  return request({
    url: '/qtr/suite/list',
    method: 'get',
    params: query
  })
}

// 查询环境详细
export function getSuite(suiteId) {
  return request({
    url: '/qtr/suite/' + suiteId,
    method: 'get'
  })
}

// 新增环境
export function addSuite(data) {
  return request({
    url: '/qtr/suite',
    method: 'post',
    data: data
  })
}

// 修改环境
export function updateSuite(data) {
  return request({
    url: '/qtr/suite',
    method: 'put',
    data: data
  })
}

// 删除环境
export function delSuite(suiteId) {
  return request({
    url: '/qtr/suite/' + suiteId,
    method: 'delete'
  })
}