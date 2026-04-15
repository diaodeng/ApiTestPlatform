import request from '@/utils/request'

// 查询定时任务调度列表
export function listJob(query) {
  return request({
    url: '/monitor/job/list',
    method: 'get',
    params: query
  })
}

// 查询任务注册键选项
export function listTaskKeyOptions() {
  return request({
    url: '/monitor/job/taskKeys',
    method: 'get'
  })
}

// 查询定时任务调度详细
export function getJob(jobId) {
  return request({
    url: '/monitor/job/' + jobId,
    method: 'get'
  })
}

// 新增定时任务调度
export function addJob(data) {
  return request({
    url: '/monitor/job',
    method: 'post',
    data: data
  })
}

// 修改定时任务调度
export function updateJob(data) {
  return request({
    url: '/monitor/job',
    method: 'put',
    data: data
  })
}

// 删除定时任务调度
export function delJob(jobId) {
  return request({
    url: '/monitor/job/' + jobId,
    method: 'delete'
  })
}

// 任务状态修改
export function changeJobStatus(taskId, enabled) {
  const data = {
    taskId,
    enabled
  }
  return request({
    url: '/monitor/job/changeStatus',
    method: 'put',
    data: data
  })
}


// 定时任务立即执行一次
export function runJob(taskId) {
  const data = {
    taskId
  }
  return request({
    url: '/monitor/job/run',
    method: 'put',
    data: data
  })
}

// 查询运行中的任务
export function listRunningJobs() {
  return request({
    url: '/monitor/job/running',
    method: 'get'
  })
}

// 取消运行中的任务（撤销未执行任务）
export function cancelRunningJob(celeryTaskId) {
  return request({
    url: '/monitor/job/running/cancel',
    method: 'put',
    data: { celeryTaskId }
  })
}

// 终止运行中的任务（尝试中断运行中任务）
export function terminateRunningJob(celeryTaskId) {
  return request({
    url: '/monitor/job/running/terminate',
    method: 'put',
    data: { celeryTaskId }
  })
}
