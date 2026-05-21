import request from '@/utils/request'

// 查询工单列表
export function listTicket(query) {
  return request({
    url: '/ticket/list',
    method: 'get',
    params: query
  })
}

// 下载工单导入模板
export function downloadTicketImportTemplate() {
  return request({
    url: '/ticket/import/template',
    method: 'get',
    responseType: 'blob'
  })
}

// 导入工单Excel
export function importTicketExcel(data) {
  return request({
    url: '/ticket/import',
    method: 'post',
    data,
    headers: {
      'Content-Type': 'multipart/form-data',
      repeatSubmit: false
    }
  })
}

// 自然语言搜索工单
export function searchTicketNaturalLanguage(query) {
  return request({
    url: '/ticket/search/natural-language',
    method: 'get',
    params: query
  })
}

// 查询工单详情
export function getTicket(ticketId) {
  return request({
    url: `/ticket/${ticketId}`,
    method: 'get'
  })
}

// 查询日志拉取存储配置
export function getTicketLogPullStorageConfig() {
  return request({
    url: '/ticket/log-pull/storage-config',
    method: 'get'
  })
}

// 保存日志拉取存储配置
export function saveTicketLogPullStorageConfig(data) {
  return request({
    url: '/ticket/log-pull/storage-config',
    method: 'put',
    data
  })
}

// 新增工单
export function addTicket(data) {
  return request({
    url: '/ticket',
    method: 'post',
    data
  })
}

// 修改工单
export function updateTicket(data) {
  return request({
    url: '/ticket',
    method: 'put',
    data
  })
}

// 删除工单
export function delTicket(ticketId) {
  return request({
    url: `/ticket/${ticketId}`,
    method: 'delete'
  })
}

// 指派工单
export function assignTicket(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/assign`,
    method: 'post',
    data
  })
}

// 流转工单状态
export function changeTicketStatus(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/status`,
    method: 'post',
    data
  })
}

// 新增工单评论
export function addTicketComment(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/comments`,
    method: 'post',
    data
  })
}

// 新增工单事件
export function addTicketEvent(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/events`,
    method: 'post',
    data
  })
}

// 查询工单时间线
export function getTicketTimeline(ticketId) {
  return request({
    url: `/ticket/${ticketId}/timeline`,
    method: 'get'
  })
}

// 查询工单日志拉取记录
export function listTicketLogPulls(ticketId, query) {
  return request({
    url: `/ticket/${ticketId}/log-pulls`,
    method: 'get',
    params: query
  })
}

// 新增工单日志拉取任务
export function addTicketLogPull(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/log-pulls`,
    method: 'post',
    data
  })
}

// 查询日志拉取文本内容
export function getTicketLogPullContent(recordId, query) {
  return request({
    url: `/ticket/log-pulls/${recordId}/content`,
    method: 'get',
    params: query
  })
}

// 保存工单RCA
export function saveTicketRca(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/rca`,
    method: 'put',
    data
  })
}

// 查询工作流配置
export function getTicketWorkflow() {
  return request({
    url: '/ticket/workflow/config',
    method: 'get'
  })
}

// 保存工作流状态节点
export function saveWorkflowStatus(data) {
  return request({
    url: '/ticket/workflow/status',
    method: 'post',
    data
  })
}

// 删除工作流状态节点
export function delWorkflowStatus(statusId) {
  return request({
    url: `/ticket/workflow/status/${statusId}`,
    method: 'delete'
  })
}

// 保存工作流流转规则
export function saveWorkflowTransition(data) {
  return request({
    url: '/ticket/workflow/transition',
    method: 'post',
    data
  })
}

// 删除工作流流转规则
export function delWorkflowTransition(transitionId) {
  return request({
    url: `/ticket/workflow/transition/${transitionId}`,
    method: 'delete'
  })
}

// 查询工单指派用户选项
export function listTicketUserOptions(query) {
  return request({
    url: '/ticket/users/options',
    method: 'get',
    params: query
  })
}

// 查询工单项目选项
export function listTicketProjectOptions() {
  return request({
    url: '/ticket/projects/options',
    method: 'get'
  })
}

// 查询工单模块选项
export function listTicketModuleOptions(query) {
  return request({
    url: '/ticket/modules/options',
    method: 'get',
    params: query
  })
}

// 查询工单统计
export function getTicketStatistics(query) {
  return request({
    url: '/ticket/statistics/overview',
    method: 'get',
    params: query
  })
}

// 查询知识库列表
export function listKnowledge(query) {
  return request({
    url: '/ticket/knowledge/list',
    method: 'get',
    params: query
  })
}

// 查询知识库详情
export function getKnowledge(articleId) {
  return request({
    url: `/ticket/knowledge/${articleId}`,
    method: 'get'
  })
}

// 新增知识库
export function addKnowledge(data) {
  return request({
    url: '/ticket/knowledge',
    method: 'post',
    data
  })
}

// 修改知识库
export function updateKnowledge(data) {
  return request({
    url: '/ticket/knowledge',
    method: 'put',
    data
  })
}

// 删除知识库
export function delKnowledge(articleId) {
  return request({
    url: `/ticket/knowledge/${articleId}`,
    method: 'delete'
  })
}
