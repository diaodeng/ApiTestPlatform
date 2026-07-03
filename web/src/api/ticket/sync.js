import request from '@/utils/request';

function sanitizeQueryParams(query) {
  return Object.fromEntries(
    Object.entries(query || {}).filter(
      ([, value]) => value !== undefined && value !== null && value !== ''
    )
  );
}

// 鏌ヨ宸ュ崟鍚屾鑷姩鍖栭厤缃?
export function getTicketSyncAutomationConfig() {
  return request({
    url: '/ticket/sync/automation',
    method: 'get',
  });
}

// 淇濆瓨宸ュ崟鍚屾鑷姩鍖栭厤缃?
export function saveTicketSyncAutomationConfig(data) {
  return request({
    url: '/ticket/sync/automation',
    method: 'put',
    data,
  });
}

// 预览主动拉取多维表格字段
export function previewTicketSyncBitablePullFields(data) {
  return request({
    url: '/ticket/sync/automation/bitable-pull/fields-preview',
    method: 'post',
    data,
  });
}

// 查询同步通知推送配置选项
export function listTicketSyncNotifyPushOptions() {
  return request({
    url: '/ticket/sync/notify/push-options',
    method: 'get',
  });
}

// 预览按人催办统计
export function previewTicketSyncPersonReminder(data) {
  return request({
    url: '/ticket/sync/notify/person/preview',
    method: 'post',
    data,
  });
}

// 执行按人催办通知
export function runTicketSyncPersonReminder(data) {
  return request({
    url: '/ticket/sync/notify/person/run',
    method: 'post',
    data,
  });
}

// 执行工单汇总统计通知
export function runTicketSyncSummaryReport(data) {
  return request({
    url: '/ticket/sync/notify/summary/run',
    method: 'post',
    data,
  });
}

// 按工单号手动发送群消息
export function sendTicketSyncGroupPushByTicket(data) {
  return request({
    url: '/ticket/sync/notify/group/send-by-ticket',
    method: 'post',
    data,
  });
}

// 批量重跑工单自动分类
export function batchReclassifyTicketSync(data) {
  return request({
    url: '/ticket/sync/auto-category/reclassify',
    method: 'post',
    data,
  });
}

// 获取自动分类统计（未归类数量）
export function getTicketSyncAutoCategoryStats() {
  return request({
    url: '/ticket/sync/auto-category/stats',
    method: 'get',
  });
}

