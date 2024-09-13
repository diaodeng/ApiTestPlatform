import request from '@/utils/request'

// 查询用例列表
export function list(query) {
  return request({
    url: '/hrm/runner/runHistoryList',
    method: 'get',
    params: query
  })
}


export function debug(data) {
  return request({
    url: '/hrm/runner/debug',
    method: 'POST',
    data: data
  })
}

export function del(data) {
  return request({
    url: '/hrm/runner/runHistory',
    method: 'DELETE',
    data: data
  })
}

export function detail(detailId) {
  return request({
    url: `/hrm/runner/runHistory/${detailId}`,
    method: 'GET'
  })
}


export function testRun(data) {
  return request({
    url: '/hrm/runner/test',
    method: 'POST',
    data: data
  })
}