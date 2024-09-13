import request from '@/utils/request'

// 查询用例列表
export function list(query) {
  return request({
    url: '/hrm/report/list',
    method: 'get',
    params: query
  })
}


export function del(data) {
  return request({
    url: '/hrm/report',
    method: 'DELETE',
    data: data
  })
}

export function detail(detailId) {
  return request({
    url: `/hrm/report/${detailId}`,
    method: 'GET'
  })
}

export function countInfo(days) {
  return request({
    url: `/hrm/common/countInfo`,
    method: 'GET'
  })
}