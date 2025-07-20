import request from '@/utils/request'

// 查询mock规则列表
export function listMockRule(query) {
  return request({
    url: '/hrm/mockManager/ruleList',
    method: 'get',
    params: query
  })
}


// 查询mock规则详细
export function getMockRule(ruleId) {
  return request({
    url: '/hrm/mockManager/rule/' + ruleId,
    method: 'get'
  })
}

// 新增mock规则
export function addMockRule(data) {
  return request({
    url: '/hrm/mockManager/addRule',
    method: 'post',
    data: data
  })
}

// 复制mock规则
export function copyMockRule(data) {
  return request({
    url: '/hrm/mockManager/copyRule',
    method: 'post',
    data: data
  })
}

// 修改mock规则状态
export function changeMockRuleStatus(data) {
  return request({
    url: '/hrm/mockManager/ruleStatus',
    method: 'post',
    data: data
  })
}

// 修改mock规则
export function updateMockRule(data) {
  return request({
    url: '/hrm/mockManager/modifyRule',
    method: 'put',
    data: data
  })
}

// 删除mock规则
export function delMockRule(data) {
  return request({
    url: '/hrm/mockManager/ruleDelete',
    method: 'delete',
    data: data
  })
}


// debugmock规则
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