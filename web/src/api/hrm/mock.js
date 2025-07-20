import request from '@/utils/request'

// 查询用例列表
export function listMockRule(query) {
  return request({
    url: '/hrm/case/list',
    method: 'get',
    params: query
  })
}


// 查询用例详细
export function getMockRule(caseId) {
  return request({
    url: '/hrm/case/' + caseId,
    method: 'get'
  })
}

// 新增用例
export function addMockRule(data) {
  return request({
    url: '/hrm/case',
    method: 'post',
    data: data
  })
}

// 复制用例
export function copyMockRule(data) {
  return request({
    url: '/hrm/case/copy',
    method: 'post',
    data: data
  })
}

// 修改用例状态
export function changeMockRuleStatus(data) {
  return request({
    url: '/hrm/case/status',
    method: 'post',
    data: data
  })
}

// 修改用例
export function updateMockRule(data) {
  return request({
    url: '/hrm/case',
    method: 'put',
    data: data
  })
}

// 删除用例
export function delMockRule(caseId) {
  return request({
    url: '/hrm/case/' + caseId,
    method: 'delete'
  })
}


// debug用例
export function debugMockRule(data) {
  return request({
    url: '/hrm/runner/debug',
    method: 'POST',
    data: data
  })
}


/*
* 获取可使用的断言方法
* */
export function getComparator(data) {
  return request({
    url: '/hrm/common/comparator',
    method: 'GET',
    params: data
  })
}