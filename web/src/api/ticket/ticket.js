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

// 查询 Qdrant Collection 列表
export function listTicketSimilarityQdrantCollections(data) {
  return request({
    url: '/ticket/similarity/qdrant/collections',
    method: 'post',
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

// 查询工单详情
export function getTicket(ticketId) {
  return request({
    url: `/ticket/${ticketId}`,
    method: 'get',
  });
}

// 查询问题实例列表
export function listTicketIssues(query) {
  return request({
    url: '/ticket/issues/list',
    method: 'get',
    params: query,
  });
}

// 查询问题实例详情
export function getTicketIssue(issueId) {
  return request({
    url: `/ticket/issues/${issueId}`,
    method: 'get',
  });
}

// 新增问题实例
export function addTicketIssue(data) {
  return request({
    url: '/ticket/issues',
    method: 'post',
    data,
  });
}

// 修改问题实例
export function updateTicketIssue(data) {
  return request({
    url: '/ticket/issues',
    method: 'put',
    data,
  });
}

// 绑定工单到已有问题实例
export function bindTicketIssue(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/issue/bind`,
    method: 'post',
    data,
  });
}

// 新建问题实例并绑定当前工单
export function createAndBindTicketIssue(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/issue/create-and-bind`,
    method: 'post',
    data,
  });
}

// 从相似工单确认归入同一问题
export function bindTicketIssueFromSimilar(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/issue/bind-from-similar`,
    method: 'post',
    data,
  });
}

// 解除工单问题归因
export function unbindTicketIssue(ticketId) {
  return request({
    url: `/ticket/${ticketId}/issue/unbind`,
    method: 'post',
  });
}

// 新增工单补充关系
export function addTicketRelation(data) {
  return request({
    url: '/ticket/relations',
    method: 'post',
    data,
  });
}

// 确认工单补充关系
export function confirmTicketRelation(relationId) {
  return request({
    url: `/ticket/relations/${relationId}/confirm`,
    method: 'put',
  });
}

// 删除工单补充关系
export function delTicketRelation(relationId) {
  return request({
    url: `/ticket/relations/${relationId}`,
    method: 'delete',
  });
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

// 查询工单分类统计枚举选项
export function getTicketStatClassificationOptions() {
  return request({
    url: '/ticket/stat-classification/options',
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

// 查询日志拉取文本内容
export function getTicketLogPullContent(recordId, query) {
  return request({
    url: `/ticket/log-pulls/${recordId}/content`,
    method: 'get',
    params: query,
  });
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

// 保存工单RCA
export function saveTicketRca(ticketId, data) {
  return request({
    url: `/ticket/${ticketId}/rca`,
    method: 'put',
    data,
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
export function getTicketStatisticsTimeConfig() {
  return request({
    url: '/ticket/statistics/time-config',
    method: 'get',
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

// 新增知识库
export function addKnowledge(data) {
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

// 删除知识库
export function delKnowledge(articleId) {
  return request({
    url: `/ticket/knowledge/${articleId}`,
    method: 'delete',
  });
}
