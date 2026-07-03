import request from '@/utils/request';

function sanitizeQueryParams(query) {
  return Object.fromEntries(
    Object.entries(query || {}).filter(
      ([, value]) => value !== undefined && value !== null && value !== ''
    )
  );
}

// 查询工单AI仓库映射
export function listTicketAiRepoMappings(query) {
  return request({
    url: '/ticket/ai/repo-mappings',
    method: 'get',
    params: query,
  });
}

// 新增工单AI仓库映射
export function addTicketAiRepoMapping(data) {
  return request({
    url: '/ticket/ai/repo-mappings',
    method: 'post',
    data,
  });
}

// 修改工单AI仓库映射
export function updateTicketAiRepoMapping(data) {
  return request({
    url: '/ticket/ai/repo-mappings',
    method: 'put',
    data,
  });
}

// 删除工单AI仓库映射
export function delTicketAiRepoMapping(mappingId) {
  return request({
    url: `/ticket/ai/repo-mappings/${mappingId}`,
    method: 'delete',
  });
}

// 查询工单AI分析任务
export function listTicketAiAnalysisTasks(ticketId, query) {
  return request({
    url: `/ticket/${ticketId}/ai-analysis/tasks`,
    method: 'get',
    params: query,
  });
}

// 提交工单AI分析任务
export function addTicketAiAnalysis(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/ai-analysis`,
    method: 'post',
    data,
    showErrorMessage: false,
  });
}

// 重试工单AI分析任务
export function retryTicketAiAnalysis(ticketId, taskId) {
  return request({
    url: `/ticket/${ticketId}/ai-analysis/tasks/${taskId}/retry`,
    method: 'post',
    showErrorMessage: false,
  });
}

