import request from '@/utils/request'

export function listPressureScenarios(query) {
  return request({
    url: '/pressure/scenarios',
    method: 'get',
    params: query
  })
}

export function getPressureScenario(scenarioId) {
  return request({
    url: `/pressure/scenarios/${scenarioId}`,
    method: 'get'
  })
}

export function addPressureScenario(data) {
  return request({
    url: '/pressure/scenarios',
    method: 'post',
    data
  })
}

export function updatePressureScenario(scenarioId, data) {
  return request({
    url: `/pressure/scenarios/${scenarioId}`,
    method: 'put',
    data
  })
}

export function listPressureRuns(query) {
  return request({
    url: '/pressure/runs',
    method: 'get',
    params: query
  })
}

export function createPressureRun(data) {
  return request({
    url: '/pressure/runs',
    method: 'post',
    data
  })
}

export function startPressureRun(runId) {
  return request({
    url: `/pressure/runs/${runId}/start`,
    method: 'post'
  })
}

export function stopPressureRun(runId) {
  return request({
    url: `/pressure/runs/${runId}/stop`,
    method: 'post'
  })
}

export function forceStopPressureRun(runId) {
  return request({
    url: `/pressure/runs/${runId}/force-stop`,
    method: 'post'
  })
}

export function getPressureRunStatus(runId) {
  return request({
    url: `/pressure/runs/${runId}/status`,
    method: 'get'
  })
}

export function comparePressureRuns(data) {
  return request({
    url: '/pressure/runs/compare',
    method: 'post',
    data
  })
}

export function refreshPressureSummary(runId) {
  return request({
    url: `/pressure/runs/${runId}/summary`,
    method: 'post'
  })
}

export function listPressureWorkers(query) {
  return request({
    url: '/pressure/workers',
    method: 'get',
    params: query
  })
}

export function registerPressureWorker(data) {
  return request({
    url: '/pressure/workers/register',
    method: 'post',
    data
  })
}

export function heartbeatPressureWorker(data) {
  return request({
    url: '/pressure/workers/heartbeat',
    method: 'post',
    data
  })
}

export function getPressureWorkerAssignment(workerId) {
  return request({
    url: `/pressure/workers/${workerId}/assignment`,
    method: 'get'
  })
}
