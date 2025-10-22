import request from '@/utils/request'

// 查询所有agent
export function all() {
  return request({
    url: '/qtr/agent/list',
    method: 'get',
    params:{"isPage": false}
  })
}

// 查询agent列表
export function list(query) {
  return request({
    url: '/qtr/agent/list',
    method: 'get',
    params: query
  })
}


// 查询agent详细
export function getDetail(dataId) {
  return request({
    url: '/qtr/agent/' + dataId,
    method: 'get'
  })
}

// 新增agent
export function addAgent(data) {
  return request({
    url: '/qtr/agent',
    method: 'post',
    data: data
  })
}


// 修改agent
export function updateAgent(data) {
  return request({
    url: '/qtr/agent',
    method: 'put',
    data: data
  })
}

// 删除agent
export function delAgent(deleteData) {
  return request({
    url: '/qtr/agent',
    method: 'delete',
    data: deleteData
  })
}