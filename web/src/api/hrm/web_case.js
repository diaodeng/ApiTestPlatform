import request from '@/utils/request'

const WEB_CASE_SILENT_HEADERS = {
  showErrorMessage: false,
  showErrorNotification: false
}

/**
 * Web 用例页面会在调用点统一 catch 并提示；这里关闭全局拦截器二次弹错。
 * @param {import('axios').AxiosRequestConfig} config axios 请求配置
 * @returns {Promise<any>} 请求结果
 */
function webCaseRequest(config) {
  const headers = {
    ...WEB_CASE_SILENT_HEADERS,
    ...(config.headers || {})
  }
  return request({
    ...config,
    headers
  })
}

export function listWebCase(query) {
  return webCaseRequest({
    url: '/hrm/web-case/list',
    method: 'get',
    params: query
  })
}

export function getWebCase(webCaseId) {
  return webCaseRequest({
    url: '/hrm/web-case/' + webCaseId,
    method: 'get'
  })
}

export function addWebCase(data) {
  return webCaseRequest({
    url: '/hrm/web-case',
    method: 'post',
    data
  })
}

export function updateWebCase(data) {
  return webCaseRequest({
    url: '/hrm/web-case',
    method: 'put',
    data
  })
}

export function delWebCase(webCaseId) {
  return webCaseRequest({
    url: '/hrm/web-case/' + webCaseId,
    method: 'delete'
  })
}

export function runWebCase(data) {
  return webCaseRequest({
    url: '/hrm/web-case/run',
    method: 'post',
    data
  })
}

export function continueWebRun(data) {
  return webCaseRequest({
    url: '/hrm/web-case/run/continue',
    method: 'post',
    data
  })
}

export function stopWebRun(data) {
  return webCaseRequest({
    url: '/hrm/web-case/run/stop',
    method: 'post',
    data
  })
}

export function cancelWebRun(data) {
  return webCaseRequest({
    url: '/hrm/web-case/run/cancel',
    method: 'post',
    data
  })
}

export function delWebRun(webCaseRunIds) {
  return webCaseRequest({
    url: '/hrm/web-case/run/' + webCaseRunIds,
    method: 'delete'
  })
}

export function listWebRuntimeProfile(query) {
  return webCaseRequest({
    url: '/hrm/web-case/runtime-profile/list',
    method: 'get',
    params: query
  })
}

export function addWebRuntimeProfile(data) {
  return webCaseRequest({
    url: '/hrm/web-case/runtime-profile',
    method: 'post',
    data
  })
}

export function updateWebRuntimeProfile(data) {
  return webCaseRequest({
    url: '/hrm/web-case/runtime-profile',
    method: 'put',
    data
  })
}

export function delWebRuntimeProfile(profileId) {
  return webCaseRequest({
    url: '/hrm/web-case/runtime-profile/' + profileId,
    method: 'delete'
  })
}

export function listWebBrowserSession(query) {
  return webCaseRequest({
    url: '/hrm/web-case/browser-session/list',
    method: 'get',
    params: query
  })
}

export function addWebBrowserSession(data) {
  return webCaseRequest({
    url: '/hrm/web-case/browser-session',
    method: 'post',
    data
  })
}

export function updateWebBrowserSession(data) {
  return webCaseRequest({
    url: '/hrm/web-case/browser-session',
    method: 'put',
    data
  })
}

export function delWebBrowserSession(sessionId) {
  return webCaseRequest({
    url: '/hrm/web-case/browser-session/' + sessionId,
    method: 'delete'
  })
}

export function getWebRun(webCaseRunId) {
  return webCaseRequest({
    url: '/hrm/web-case/run/' + webCaseRunId,
    method: 'get'
  })
}

export function listWebRecording(query) {
  return webCaseRequest({
    url: '/hrm/web-case/recording/list',
    method: 'get',
    params: query
  })
}

export function getWebRecording(recordingId) {
  return webCaseRequest({
    url: '/hrm/web-case/recording/' + recordingId,
    method: 'get'
  })
}

/**
 * 删除单条 Web 录制步骤，并同步删除其对应的录制事件。
 * @param {Object} data 删除请求参数
 * @param {number} data.recordingId 录制会话ID
 * @param {string|number|undefined} data.stepId 步骤稳定ID
 * @param {number|undefined} data.stepIndex 步骤序号
 * @param {string|number|undefined} data.eventId 录制事件ID
 * @param {number|undefined} data.eventIndex 录制事件序号
 * @returns {Promise<any>} 请求结果
 */
export function deleteWebRecordingStep(data) {
  return webCaseRequest({
    url: '/hrm/web-case/recording/event/delete',
    method: 'post',
    data
  })
}

export function startWebRecording(data) {
  return webCaseRequest({
    url: '/hrm/web-case/recording/start',
    method: 'post',
    data
  })
}

export function continueWebRecording(data) {
  return webCaseRequest({
    url: '/hrm/web-case/recording/continue',
    method: 'post',
    data
  })
}

export function cancelWebRecording(data) {
  return webCaseRequest({
    url: '/hrm/web-case/recording/cancel',
    method: 'post',
    data
  })
}

export function stopWebRecording(data) {
  return webCaseRequest({
    url: '/hrm/web-case/recording/stop',
    method: 'post',
    data
  })
}

export function delWebRecording(recordingIds) {
  return webCaseRequest({
    url: '/hrm/web-case/recording/' + recordingIds,
    method: 'delete'
  })
}

export function applyWebRecording(data) {
  return webCaseRequest({
    url: '/hrm/web-case/recording/apply',
    method: 'post',
    data
  })
}

export function saveWebRecordingAsCase(data) {
  return webCaseRequest({
    url: '/hrm/web-case/recording/save-as-case',
    method: 'post',
    data
  })
}

export function replayWebRecording(data) {
  return webCaseRequest({
    url: '/hrm/web-case/recording/replay',
    method: 'post',
    data
  })
}

export function listWebRun(query) {
  return webCaseRequest({
    url: '/hrm/web-case/run/list',
    method: 'get',
    params: query
  })
}

