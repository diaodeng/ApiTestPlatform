import request from '@/utils/request'

// 查询用例列表
export function listCase(query) {
  return request({
    url: '/hrm/case/list',
    method: 'get',
    params: query
  })
}


// 查询用例详细
export function getCase(caseId) {
  return request({
    url: '/hrm/case/' + caseId,
    method: 'get'
  })
}

// 新增用例
export function addCase(data) {
  return request({
    url: '/hrm/case',
    method: 'post',
    data: data
  })
}

// 修改用例
export function updateCase(data) {
  return request({
    url: '/hrm/case',
    method: 'put',
    data: data
  })
}

// 删除用例
export function delCase(caseId) {
  return request({
    url: '/hrm/case/' + caseId,
    method: 'delete'
  })
}


// debug用例
export function debugCase(data) {
  return request({
    url: '/hrm/runner/debug',
    method: 'POST',
    data: data
  })
}

export function getComparator(data) {
  return request({
    url: '/hrm/common/comparator',
    method: 'GET',
    params: data
  })
}