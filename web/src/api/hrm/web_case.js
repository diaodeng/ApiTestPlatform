import request from '@/utils/request'

export function listWebCase(query) {
  return request({
    url: '/hrm/web-case/list',
    method: 'get',
    params: query
  })
}

export function getWebCase(webCaseId) {
  return request({
    url: '/hrm/web-case/' + webCaseId,
    method: 'get'
  })
}

export function addWebCase(data) {
  return request({
    url: '/hrm/web-case',
    method: 'post',
    data
  })
}

export function updateWebCase(data) {
  return request({
    url: '/hrm/web-case',
    method: 'put',
    data
  })
}

export function delWebCase(webCaseId) {
  return request({
    url: '/hrm/web-case/' + webCaseId,
    method: 'delete'
  })
}

export function runWebCase(data) {
  return request({
    url: '/hrm/web-case/run',
    method: 'post',
    data
  })
}

export function listWebRecording(query) {
  return request({
    url: '/hrm/web-case/recording/list',
    method: 'get',
    params: query
  })
}

export function getWebRecording(recordingId) {
  return request({
    url: '/hrm/web-case/recording/' + recordingId,
    method: 'get'
  })
}

export function startWebRecording(data) {
  return request({
    url: '/hrm/web-case/recording/start',
    method: 'post',
    data
  })
}

export function stopWebRecording(data) {
  return request({
    url: '/hrm/web-case/recording/stop',
    method: 'post',
    data
  })
}

export function applyWebRecording(data) {
  return request({
    url: '/hrm/web-case/recording/apply',
    method: 'post',
    data
  })
}

export function listWebRun(query) {
  return request({
    url: '/hrm/web-case/run/list',
    method: 'get',
    params: query
  })
}
