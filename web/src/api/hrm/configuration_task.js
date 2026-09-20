import request from '@/utils/request'

// 配置任务 API 封装：任务/版本/阶段/运行/产物/报告/定时。
// 后端所有 BIGINT ID 均以字符串返回，前端不得使用 Number() 转换。

function silent(config) {
  return request({
    ...config,
    headers: { showErrorMessage: false, showErrorNotification: false, ...(config.headers || {}) }
  })
}

// ---------- 任务 ----------

export function listTasks(query) {
  return silent({ url: '/configuration-tasks', method: 'get', params: query })
}

export function getTask(taskId) {
  return silent({ url: '/configuration-tasks/' + taskId, method: 'get' })
}

export function addTask(data) {
  return silent({ url: '/configuration-tasks', method: 'post', data })
}

export function updateTask(taskId, data) {
  return silent({ url: '/configuration-tasks/' + taskId, method: 'put', data })
}

// ---------- 版本 ----------

export function createVersion(taskId, data) {
  return silent({ url: `/configuration-tasks/${taskId}/versions`, method: 'post', data })
}

export function listVersions(taskId, limit = 50) {
  return silent({ url: `/configuration-tasks/${taskId}/versions`, method: 'get', params: { limit } })
}

export function getVersion(versionId) {
  return silent({ url: `/configuration-tasks/versions/${versionId}`, method: 'get' })
}

export function updateVersion(versionId, data) {
  return silent({ url: `/configuration-tasks/versions/${versionId}`, method: 'put', data })
}

export function publishVersion(versionId) {
  return silent({ url: `/configuration-tasks/versions/${versionId}/publish`, method: 'post' })
}

// ---------- 阶段 ----------

export function saveVersionStages(versionId, stages) {
  return silent({ url: `/configuration-tasks/versions/${versionId}/stages`, method: 'post', data: stages })
}

export function listVersionStages(versionId) {
  return silent({ url: `/configuration-tasks/versions/${versionId}/stages`, method: 'get' })
}

export function listRunStages(taskRunId) {
  return silent({ url: `/configuration-tasks/runs/${taskRunId}/stages`, method: 'get' })
}

export function approveRunStage(runStageId, data) {
  return silent({ url: `/configuration-tasks/runs/stages/${runStageId}/approve`, method: 'post', data })
}

export function retryRunStage(runStageId) {
  return silent({ url: `/configuration-tasks/runs/stages/${runStageId}/retry`, method: 'post' })
}

// ---------- 运行 ----------

export function createRun(taskId, data) {
  return silent({ url: `/configuration-tasks/${taskId}/runs`, method: 'post', data })
}

export function stopRun(taskRunId, data = {}) {
  return silent({ url: `/configuration-tasks/runs/${taskRunId}/stop`, method: 'post', data })
}

export function listRuns(taskId, query = {}) {
  return silent({ url: `/configuration-tasks/${taskId}/runs`, method: 'get', params: query })
}

export function getRun(taskRunId) {
  return silent({ url: `/configuration-tasks/runs/${taskRunId}`, method: 'get' })
}

// ---------- 产物与报告 ----------

export function listRunArtifacts(taskRunId) {
  return silent({ url: `/configuration-tasks/runs/${taskRunId}/artifacts`, method: 'get' })
}

export function generateRunReport(taskRunId, notifyFeishu = false) {
  return silent({
    url: `/configuration-tasks/runs/${taskRunId}/report`,
    method: 'post',
    params: { notifyFeishu }
  })
}

// ---------- 定时触发 ----------

export function getTaskSchedule(taskId) {
  return silent({ url: `/configuration-tasks/${taskId}/schedule`, method: 'get' })
}

export function saveTaskSchedule(taskId, data) {
  return silent({ url: `/configuration-tasks/${taskId}/schedule`, method: 'put', data })
}

// ---------- 录制转模板 ----------

export function convertRecordingToTemplate(data) {
  return silent({ url: '/configuration-tasks/templates/from-recording', method: 'post', data })
}
