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

export function continueWebRun(data) {
  return request({
    url: '/hrm/web-case/run/continue',
    method: 'post',
    data
  })
}

export function stopWebRun(data) {
  return request({
    url: '/hrm/web-case/run/stop',
    method: 'post',
    data
  })
}

export function cancelWebRun(data) {
  return request({
    url: '/hrm/web-case/run/cancel',
    method: 'post',
    data
  })
}

export function delWebRun(webCaseRunIds) {
  return request({
    url: '/hrm/web-case/run/' + webCaseRunIds,
    method: 'delete'
  })
}

export function listWebRuntimeProfile(query) {
  return request({
    url: '/hrm/web-case/runtime-profile/list',
    method: 'get',
    params: query
  })
}

export function addWebRuntimeProfile(data) {
  return request({
    url: '/hrm/web-case/runtime-profile',
    method: 'post',
    data
  })
}

export function updateWebRuntimeProfile(data) {
  return request({
    url: '/hrm/web-case/runtime-profile',
    method: 'put',
    data
  })
}

export function delWebRuntimeProfile(profileId) {
  return request({
    url: '/hrm/web-case/runtime-profile/' + profileId,
    method: 'delete'
  })
}

export function getWebRun(webCaseRunId) {
  return request({
    url: '/hrm/web-case/run/' + webCaseRunId,
    method: 'get'
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

export function continueWebRecording(data) {
  return request({
    url: '/hrm/web-case/recording/continue',
    method: 'post',
    data
  })
}

export function cancelWebRecording(data) {
  return request({
    url: '/hrm/web-case/recording/cancel',
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

export function delWebRecording(recordingIds) {
  return request({
    url: '/hrm/web-case/recording/' + recordingIds,
    method: 'delete'
  })
}

export function applyWebRecording(data) {
  return request({
    url: '/hrm/web-case/recording/apply',
    method: 'post',
    data
  })
}

export function saveWebRecordingAsCase(data) {
  return request({
    url: '/hrm/web-case/recording/save-as-case',
    method: 'post',
    data
  })
}

export function replayWebRecording(data) {
  return request({
    url: '/hrm/web-case/recording/replay',
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
