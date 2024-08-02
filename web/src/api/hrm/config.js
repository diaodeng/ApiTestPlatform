import request from '@/utils/request'

// 查询用例列表
export function list(query) {
  return request({
    url: '/hrm/config/list',
    method: 'get',
    params: query
  })
}


export function del(data) {
  return request({
    url: '/hrm/config',
    method: 'DELETE',
    data: data
  })
}

export function detail(id) {
  return request({
    url: `/hrm/config/${id}`,
    method: 'GET'
  })
}

export function copy(id) {
  return request({
    url: `/hrm/config/${id}`,
    method: 'POST'
  })
}