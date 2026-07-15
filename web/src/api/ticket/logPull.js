import request from '@/utils/request';
import { getToken } from '@/utils/auth';
import { tansParams } from '@/utils/ruoyi';

function sanitizeQueryParams(query) {
  return Object.fromEntries(
    Object.entries(query || {}).filter(
      ([, value]) => value !== undefined && value !== null && value !== ''
    )
  );
}

// 查询日志拉取存储配置
export function getTicketLogPullStorageConfig() {
  return request({
    url: '/ticket/log-pull/storage-config',
    method: 'get',
  });
}

// 保存日志拉取存储配置
export function saveTicketLogPullStorageConfig(data) {
  return request({
    url: '/ticket/log-pull/storage-config',
    method: 'put',
    data,
  });
}

// 查询工单日志拉取记录
export function listTicketLogPulls(ticketId, query) {
  query['ticketId'] = ticketId;
  return request({
    url: `/ticket/log-pulls-by-ticket`,
    method: 'get',
    params: sanitizeQueryParams(query),
  });
}

// 查询日志拉取管理记录
export function listTicketLogPullRecords(query) {
  return request({
    url: '/ticket/log-pulls',
    method: 'get',
    params: sanitizeQueryParams(query),
  });
}

// 查询日志拉取商家/门店联动选项
export function getTicketLogPullVendorStoreOptions(vendorId) {
  return request({
    url: '/ticket/log-pull/vendor-store-options',
    method: 'get',
    params: vendorId ? { vendor_id: vendorId } : undefined,
  });
}

// 下载门店配置导入模板
export function downloadTicketLogPullStoreConfigTemplate() {
  return request({
    url: '/ticket/log-pull/store-config/template',
    method: 'get',
    responseType: 'blob',
  });
}

// 查询门店配置列表
export function listTicketLogPullStoreConfigs(query) {
  return request({
    url: '/ticket/log-pull/store-configs',
    method: 'get',
    params: sanitizeQueryParams(query),
  });
}

// 导入门店配置
export function importTicketLogPullStoreConfigs(data) {
  return request({
    url: '/ticket/log-pull/store-configs/import',
    method: 'post',
    data,
    headers: {
      'Content-Type': 'multipart/form-data',
      repeatSubmit: false,
    },
  });
}

// 查询项目商家映射列表
export function listTicketLogPullProjectVendorMaps(query) {
  return request({
    url: '/ticket/log-pull/project-vendor-maps',
    method: 'get',
    params: sanitizeQueryParams(query),
  });
}

// 查询项目商家映射选项
export function listTicketLogPullProjectVendorMapOptions() {
  return request({
    url: '/ticket/log-pull/project-vendor-maps/options',
    method: 'get',
  });
}

// 根据项目ID查询项目商家映射
export function getTicketLogPullProjectVendorMap(projectId) {
  return request({
    url: `/ticket/log-pull/project-vendor-maps/${projectId}`,
    method: 'get',
  });
}

// 保存项目商家映射
export function saveTicketLogPullProjectVendorMap(data) {
  return request({
    url: '/ticket/log-pull/project-vendor-maps',
    method: 'post',
    data,
  });
}

// 新增工单日志拉取任务
export function addTicketLogPull(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/log-pulls`,
    method: 'post',
    data,
  });
}

// 新增日志拉取管理记录
export function createTicketLogPullRecord(data) {
  return request({
    url: '/ticket/log-pulls',
    method: 'post',
    data,
  });
}

// 下载日志拉取压缩包
export function downloadTicketLogPull(recordId, source) {
  return request({
    url: `/ticket/log-pulls/${recordId}/download`,
    method: 'get',
    params: source ? { source } : undefined,
    responseType: 'blob',
  });
}

// 重新拉取日志任务
export function retryTicketLogPull(recordId) {
  return request({
    url: `/ticket/log-pulls/${recordId}/retry`,
    method: 'post',
  });
}

// 删除日志拉取记录
export function delTicketLogPull(recordId) {
  return request({
    url: `/ticket/log-pulls/${recordId}`,
    method: 'delete',
  });
}

// 重新下载日志压缩包
export function redownloadTicketLogPull(recordId) {
  return request({
    url: `/ticket/log-pulls/${recordId}/redownload`,
    method: 'post',
  });
}

// 查询日志拉取文本内容
export function getTicketLogPullContent(recordId, query) {
  return request({
    url: `/ticket/log-pulls/${recordId}/content`,
    method: 'get',
    params: query,
  });
}

// 流式查询日志拉取文本内容，按 NDJSON 事件逐块回调
export async function streamTicketLogPullContent(recordId, query, handlers = {}) {
  const baseURL = window.__APP_CONFIG__?.BASE_API || import.meta.env.VITE_APP_BASE_API || '';
  const queryText = tansParams(sanitizeQueryParams(query || {})).replace(/&$/, '');
  const url = `${baseURL}/ticket/log-pulls/${recordId}/content/stream${queryText ? `?${queryText}` : ''}`;
  const headers = {};
  if (getToken()) {
    headers.Authorization = `Bearer ${getToken()}`;
  }
  const response = await fetch(url, { method: 'GET', headers });
  if (!response.ok || !response.body) {
    throw new Error(`日志内容流式读取失败: ${response.status}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  const handleLine = rawLine => {
    const line = String(rawLine || '').trim();
    if (!line) return;
    const event = JSON.parse(line);
    const data = event.data || {};
    if (event.type === 'meta') {
      handlers.onMeta?.(data);
    } else if (event.type === 'chunk') {
      handlers.onChunk?.(data.text || '');
    } else if (event.type === 'done') {
      handlers.onDone?.(data);
    } else if (event.type === 'error') {
      throw new Error(data.message || '日志内容流式读取失败');
    }
  };
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    lines.forEach(handleLine);
  }
  buffer += decoder.decode();
  if (buffer.trim()) {
    handleLine(buffer);
  }
}

// 准备工单日志查看目录
export function prepareTicketLogs(ticketId, recordId) {
  return request({
    url: '/ticket/logs/prepare',
    method: 'post',
    data: { ticketId, recordId },
  });
}

// 查询工单日志文件列表
export function listTicketLogFiles(ticketId, recordId) {
  return request({
    url: '/ticket/logs/files',
    method: 'get',
    // GET 查询参数需要使用后端显式声明的 snake_case 字段名。
    params: { ticket_id: ticketId, record_id: recordId },
  });
}

// 搜索工单日志关键字
export function searchTicketLogs(data) {
  return request({
    url: '/ticket/logs/search',
    method: 'post',
    data,
  });
}

// 查询工单日志上下文
export function getTicketLogContext(query) {
  const params = { ...(query || {}) };
  // 上下文接口的 ticket_id 不是 Pydantic body，前端这里统一做一次兼容转换。
  if (params.ticketId !== undefined && params.ticket_id === undefined) {
    params.ticket_id = params.ticketId;
    delete params.ticketId;
  }
  return request({
    url: '/ticket/logs/context',
    method: 'get',
    params,
  });
}

// 提取工单日志异常摘要
export function getTicketLogErrors(data) {
  return request({
    url: '/ticket/logs/errors',
    method: 'post',
    data,
  });
}

