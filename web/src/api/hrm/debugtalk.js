import request from '@/utils/request'

// 查询DebugTalk列表
export function listDebugTalk(query) {
  return request({
    url: '/hrm/debugtalk/list',
    method: 'get',
    params: query
  })
}

// 查询DebugTalk详细
export function getDebugTalk(debugtalkId) {
  return request({
    url: '/hrm/debugtalk/' + debugtalkId,
    method: 'get'
  })
}

// 新增DebugTalk
export function addDebugTalk(data) {
  return request({
    url: '/hrm/debugtalk',
    method: 'post',
    data: data
  })
}

// 修改DebugTalk
export function updateDebugTalk(data) {
  return request({
    url: '/hrm/debugtalk',
    method: 'put',
    data: data
  })
}

// 删除DebugTalk
export function delDebugTalk(debugtalkId) {
  return request({
    url: '/hrm/debugtalk/' + debugtalkId,
    method: 'delete'
  })
}