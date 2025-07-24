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


// 查询mock规则响应列表
export function listMockRuleResponse(query) {
  return request({
    url: '/hrm/mockManager/responseList',
    method: 'get',
    params: query
  })
}

// 通过条件查询mock规则响应列表
export function listMockRuleResponseByCondition(data) {
  return request({
    url: '/hrm/mockManager/getResponseByCondition',
    method: 'post',
    data: data
  })
}

// 查询mock规则响应详情
export function getRuleResponseDetail(query) {
  return request({
    url: '/hrm/mockManager/responseDetail',
    method: 'get',
    params: query
  })
}

// 添加mock规则响应详情
export function addResponseDetail(data) {
  return request({
    url: '/hrm/mockManager/addResponse',
    method: 'post',
    data: data
  })
}

// 设置mock规则的默认响应
export function setDefaultResponse(data) {
  return request({
    url: '/hrm/mockManager/setDefaultResponse',
    method: 'post',
    data: data
  })
}

// 修改mock规则响应详情
export function editResponseDetail(data) {
  return request({
    url: '/hrm/mockManager/updateResponse',
    method: 'put',
    data: data
  })
}