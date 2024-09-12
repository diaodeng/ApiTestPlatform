import request from '@/utils/request'

// 查询测试套件列表
export function listSuite(query) {
  return request({
    url: '/qtr/suite/list',
    method: 'get',
    params: query
  })
}

// 查询测试套件详细
export function getSuite(suiteId) {
  return request({
    url: '/qtr/suite/' + suiteId,
    method: 'get'
  })
}

// 新增测试套件
export function addSuite(data) {
  return request({
    url: '/qtr/suite',
    method: 'post',
    data: data
  })
}

// 修改测试套件
export function updateSuite(data) {
  return request({
    url: '/qtr/suite',
    method: 'put',
    data: data
  })
}

// 删除测试套件
export function delSuite(suiteId) {
  return request({
    url: '/qtr/suite/' + suiteId,
    method: 'delete'
  })
}

/**************测试套件详细**************/
//查询测试套件详细列表
export function listDetailSuite(query){
  return request({
    url: '/qtr/suite/detailList',
    method: 'get',
    params: query
  })
}

// 新增测试套件详情
export function addSuiteDetail(data) {
  return request({
    url: '/qtr/suite/addSuiteDetail',
    method: 'post',
    data: data
  })
}

// 修改测试套件详细
export function updateSuiteDetail(data) {
  return request({
    url: '/qtr/suite/editSuiteDetail',
    method: 'put',
    data: data
  })
}

// 查询测试套件详细
export function getSuiteDetail(suiteDetailId) {
  return request({
    url: '/qtr/suite/getSuiteDetail/' + suiteDetailId,
    method: 'get'
  })
}
