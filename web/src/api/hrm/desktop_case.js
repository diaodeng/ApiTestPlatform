import request from '@/utils/request'

export function listDesktopCase(query) {
  return request({
    url: '/hrm/desktop-case/list',
    method: 'get',
    params: query
  })
}

export function getDesktopCase(desktopCaseId) {
  return request({
    url: '/hrm/desktop-case/' + desktopCaseId,
    method: 'get'
  })
}

export function getDesktopStorageConfig() {
  return request({
    url: '/hrm/desktop-case/storage-config',
    method: 'get'
  })
}

export function saveDesktopStorageConfig(data) {
  return request({
    url: '/hrm/desktop-case/storage-config',
    method: 'post',
    data
  })
}

export function addDesktopCase(data) {
  return request({
    url: '/hrm/desktop-case',
    method: 'post',
    data
  })
}

export function updateDesktopCase(data) {
  return request({
    url: '/hrm/desktop-case',
    method: 'put',
    data
  })
}

export function delDesktopCase(desktopCaseId) {
  return request({
    url: '/hrm/desktop-case/' + desktopCaseId,
    method: 'delete'
  })
}

export function runDesktopCase(data) {
  return request({
    url: '/hrm/desktop-case/run',
    method: 'post',
    data
  })
}

export function listDesktopRun(query) {
  return request({
    url: '/hrm/desktop-case/run/list',
    method: 'get',
    params: query
  })
}

export function getDesktopRun(desktopCaseRunId) {
  return request({
    url: '/hrm/desktop-case/run/' + desktopCaseRunId,
    method: 'get'
  })
}

export function replaceDesktopBaseline(data) {
  return request({
    url: '/hrm/desktop-case/run/replace-baseline',
    method: 'post',
    data
  })
}

export function listDesktopRecording(query) {
  return request({
    url: '/hrm/desktop-case/recording/list',
    method: 'get',
    params: query
  })
}

export function getDesktopRecording(recordingId) {
  return request({
    url: '/hrm/desktop-case/recording/' + recordingId,
    method: 'get'
  })
}

export function updateDesktopRecordingEvent(data) {
  return request({
    url: '/hrm/desktop-case/recording/event/update',
    method: 'post',
    data
  })
}

export function startDesktopRecording(data) {
  return request({
    url: '/hrm/desktop-case/recording/start',
    method: 'post',
    data
  })
}

export function stopDesktopRecording(data) {
  return request({
    url: '/hrm/desktop-case/recording/stop',
    method: 'post',
    data
  })
}

export function replayDesktopRecording(data) {
  return request({
    url: '/hrm/desktop-case/recording/replay',
    method: 'post',
    data
  })
}

export function applyDesktopRecording(data) {
  return request({
    url: '/hrm/desktop-case/recording/apply',
    method: 'post',
    data
  })
}

export function saveDesktopRecordingAsCase(data) {
  return request({
    url: '/hrm/desktop-case/recording/save-as-case',
    method: 'post',
    data
  })
}
