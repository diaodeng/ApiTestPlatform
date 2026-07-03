import request from '@/utils/request';

function sanitizeQueryParams(query) {
  return Object.fromEntries(
    Object.entries(query || {}).filter(
      ([, value]) => value !== undefined && value !== null && value !== ''
    )
  );
}

// 指派工单
export function assignTicket(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/assign`,
    method: 'post',
    data,
  });
}

// 流转工单状态
export function changeTicketStatus(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/status`,
    method: 'post',
    data,
  });
}

// 手动翻译工单描述
export function translateTicketDescription(ticketId) {
  return request({
    url: `/ticket/${ticketId}/translate-description`,
    method: 'post',
  });
}

// 新增工单评论
export function addTicketComment(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/comments`,
    method: 'post',
    data,
  });
}

// 查询工单评论列表
export function getTicketComments(ticketId) {
  return request({
    url: `/ticket/${ticketId}/comments`,
    method: 'get',
  });
}

// 查询工单协同消息
export function getTicketMessages(ticketId) {
  return request({
    url: `/ticket/${ticketId}/messages`,
    method: 'get',
  });
}

// 新增工单协同消息
export function addTicketMessage(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/messages`,
    method: 'post',
    data,
  });
}

// 新增工单 ACR 快照
export function addTicketSnapshot(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/snapshots`,
    method: 'post',
    data,
  });
}

// 自动生成工单知识库案例
export function extractTicketKnowledge(ticketId) {
  return request({
    url: `/ticket/${ticketId}/knowledge/extract`,
    method: 'post',
  });
}

// 新增工单事件
export function addTicketEvent(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/events`,
    method: 'post',
    data,
  });
}

// 查询工单时间线
export function getTicketTimeline(ticketId) {
  return request({
    url: `/ticket/${ticketId}/timeline`,
    method: 'get',
  });
}

// 保存工单RCA
export function saveTicketRca(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/rca`,
    method: 'put',
    data,
  });
}

