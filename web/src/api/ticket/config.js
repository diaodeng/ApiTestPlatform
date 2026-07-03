import request from '@/utils/request';

function sanitizeQueryParams(query) {
  return Object.fromEntries(
    Object.entries(query || {}).filter(
      ([, value]) => value !== undefined && value !== null && value !== ''
    )
  );
}

// 查询相似工单检索配置
export function getTicketSimilarityConfig() {
  return request({
    url: '/ticket/similarity/config',
    method: 'get',
  });
}

// 保存相似工单检索配置
export function saveTicketSimilarityConfig(data) {
  return request({
    url: '/ticket/similarity/config',
    method: 'put',
    data,
  });
}

// 重建相似工单向量
export function rebuildTicketSimilarity(data) {
  return request({
    url: '/ticket/similarity/rebuild',
    method: 'post',
    data,
  });
}

// 查询工单分类统计枚举选项
export function getTicketStatClassificationOptions() {
  return request({
    url: '/ticket/stat-classification/options',
    method: 'get',
  });
}

// 查询工作流配置
export function getTicketWorkflow() {
  return request({
    url: '/ticket/workflow/config',
    method: 'get',
  });
}

// 保存工作流状态节点
export function saveWorkflowStatus(data) {
  return request({
    url: '/ticket/workflow/status',
    method: 'post',
    data,
  });
}

// 删除工作流状态节点
export function delWorkflowStatus(statusId) {
  return request({
    url: `/ticket/workflow/status/${statusId}`,
    method: 'delete',
  });
}

// 保存工作流流转规则
export function saveWorkflowTransition(data) {
  return request({
    url: '/ticket/workflow/transition',
    method: 'post',
    data,
  });
}

// 删除工作流流转规则
export function delWorkflowTransition(transitionId) {
  return request({
    url: `/ticket/workflow/transition/${transitionId}`,
    method: 'delete',
  });
}

// 查询工单指派用户选项
export function listTicketUserOptions(query) {
  return request({
    url: '/ticket/users/options',
    method: 'get',
    params: query,
  });
}

// 查询工单项目选项
export function listTicketProjectOptions() {
  return request({
    url: '/ticket/projects/options',
    method: 'get',
  });
}

// 查询工单模块选项
export function listTicketModuleOptions(query) {
  return request({
    url: '/ticket/modules/options',
    method: 'get',
    params: query,
  });
}

// 查询工单统计
export function getTicketStatistics(query) {
  return request({
    url: '/ticket/statistics/overview',
    method: 'get',
    params: query,
  });
}

// 查询工单趋势统计
export function getTicketStatisticsTrend(query) {
  return request({
    url: '/ticket/statistics/trend',
    method: 'get',
    params: query,
  });
}

// 查询知识库列表
export function listKnowledge(query) {
  return request({
    url: '/ticket/knowledge/list',
    method: 'get',
    params: query,
  });
}

// 查询知识库详情
export function getKnowledge(articleId) {
  return request({
    url: `/ticket/knowledge/${articleId}`,
    method: 'get',
  });
}

// 删除知识库
export function delKnowledge(articleId) {
  return request({
    url: `/ticket/knowledge/${articleId}`,
    method: 'delete',
  });
}

