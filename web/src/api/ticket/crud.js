import request from '@/utils/request';

function sanitizeQueryParams(query) {
  return Object.fromEntries(
    Object.entries(query || {}).filter(
      ([, value]) => value !== undefined && value !== null && value !== ''
    )
  );
}

// 查询工单列表
export function listTicket(query) {
  return request({
    url: '/ticket/list',
    method: 'get',
    params: query,
  });
}

// 下载工单导入模板
export function downloadTicketImportTemplate() {
  return request({
    url: '/ticket/import/template',
    method: 'get',
    responseType: 'blob',
  });
}

// 导入工单Excel
export function importTicketExcel(data) {
  return request({
    url: '/ticket/import',
    method: 'post',
    data,
    headers: {
      'Content-Type': 'multipart/form-data',
      repeatSubmit: false,
    },
  });
}

// 自然语言搜索工单
export function searchTicketNaturalLanguage(query) {
  return request({
    url: '/ticket/search/natural-language',
    method: 'get',
    params: query,
  });
}

// 查询工单详情
export function getTicket(ticketId) {
  return request({
    url: `/ticket/${ticketId}`,
    method: 'get',
  });
}

// 新增工单
export function addTicket(data) {
  return request({
    url: '/ticket',
    method: 'post',
    data,
  });
}

// 修改工单
export function updateTicket(data) {
  return request({
    url: '/ticket',
    method: 'put',
    data,
  });
}

// 删除工单
export function delTicket(ticketId) {
  return request({
    url: `/ticket/${ticketId}`,
    method: 'delete',
  });
}

// 查询工单轻量详情
export function getTicketSummary(ticketId) {
  return request({
    url: `/ticket/${ticketId}/summary`,
    method: 'get',
  });
}

// 查询工单相似工单
export function getTicketSimilarTickets(ticketId, params = {}) {
  return request({
    url: `/ticket/${ticketId}/similar-tickets`,
    method: 'get',
    params,
  });
}

// 更新相似处理案例状态
export function updateTicketSimilarityCaseStatus(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/similarity-case/status`,
    method: 'post',
    data,
  });
}


  return request({
    url: '/ticket/knowledge',
    method: 'post',
    data,
  });
}

// 修改知识库
export function updateKnowledge(data) {
  return request({
    url: '/ticket/knowledge',
    method: 'put',
    data,
  });
}

