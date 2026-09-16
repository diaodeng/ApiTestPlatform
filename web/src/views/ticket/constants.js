export const ticketStatusOptions = [
  { label: '待受理', value: 'pending', type: 'info' },
  { label: '处理中', value: 'processing', type: 'warning' },
  { label: '待用户反馈', value: 'wait_user', type: 'warning' },
  { label: '待开发', value: 'wait_dev', type: 'warning' },
  { label: '待上线', value: 'wait_release', type: 'warning' },
  { label: '待验证', value: 'wait_verify', type: 'primary' },
  { label: '已解决', value: 'resolved', type: 'success' },
  { label: '已关闭', value: 'closed', type: 'success' },
  { label: '已驳回', value: 'rejected', type: 'danger' },
  { label: '非问题', value: 'non_problem', type: 'info' },
  { label: '设计如此', value: 'design_as_expected', type: 'info' },
  { label: '用户误操作', value: 'user_misoperation', type: 'info' },
  { label: '重复工单', value: 'duplicated', type: 'info' }
]

export const priorityOptions = [
  { label: 'P0', value: 'P0' },
  { label: 'P1', value: 'P1' },
  { label: 'P2', value: 'P2' },
  { label: 'P3', value: 'P3' },
  { label: 'P4', value: 'P4' }
]

export const severityOptions = [
  { label: '阻塞', value: 'blocker' },
  { label: '严重', value: 'critical' },
  { label: '主要', value: 'major' },
  { label: '次要', value: 'minor' },
  { label: '轻微', value: 'trivial' }
]

export const sourceOptions = [
  { label: '客户反馈', value: 'customer' },
  { label: '客服录入', value: 'support' },
  { label: '测试发现', value: 'test' },
  { label: '监控告警', value: 'monitor' },
  { label: '内部巡检', value: 'internal' }
]

export const eventTypeOptions = [
  { label: '排查记录', value: 'ANALYSIS' },
  { label: 'RCA', value: 'RCA' },
  { label: '复现记录', value: 'REPRODUCED' },
  { label: '日志分析', value: 'LOG_ANALYSIS' },
  { label: '数据库检查', value: 'DB_CHECK' },
  { label: '修复动作', value: 'FIX_APPLIED' },
  { label: '上线发布', value: 'DEPLOYED' },
  { label: '验证记录', value: 'VERIFIED' }
]

export const logPullStatusOptions = [
  { label: '待执行', value: 'created', type: 'info' },
  { label: '提交申请中', value: 'submitting', type: 'warning' },
  { label: '轮询处理中', value: 'polling', type: 'warning' },
  { label: '下载中', value: 'downloading', type: 'warning' },
  { label: '解析中', value: 'processing', type: 'primary' },
  { label: '成功', value: 'success', type: 'success' },
  { label: '外部失败', value: 'failed', type: 'danger' },
  { label: '程序异常', value: 'exception', type: 'danger' },
  { label: '已取消', value: 'cancelled', type: 'info' }
]

export const logPullDataTypeOptions = [
  { label: '日志', value: 1 },
  { label: 'DB', value: 2 }
]

export const logPullStorageModeOptions = [
  { label: '本地', value: 'local' },
  { label: 'FTP', value: 'ftp' }
]

export const ticketProcessStatusOptions = [
  { label: '未拉取', value: 'no_log_pull' },
  { label: '日志待执行', value: 'log_pull_created' },
  { label: '日志拉取中', value: 'log_pull_running' },
  { label: '提交申请中', value: 'log_pull_submitting' },
  { label: '轮询处理中', value: 'log_pull_polling' },
  { label: '下载中', value: 'log_pull_downloading' },
  { label: '解析中', value: 'log_pull_processing' },
  { label: '日志拉取成功', value: 'log_pull_success' },
  { label: '拉取失败', value: 'log_pull_failed' },
  { label: 'AI未分析', value: 'ai_not_analyzed' },
  { label: 'AI分析中', value: 'ai_running' },
  { label: 'AI恢复中', value: 'ai_pending_recovery' },
  { label: 'AI分析完成', value: 'ai_success' },
  { label: 'AI分析失败', value: 'ai_failed' }
]

export function getOptionLabel(options, value) {
  return options.find(item => item.value === value)?.label || value || '-'
}

/**
 * 自动日志拉取触发场景选项，用于"拉取人"列 tooltip 展示。
 */
export const logPullSourceSceneOptions = [
  { label: '外部同步', value: 'external_sync' },
  { label: '远端拉取', value: 'remote_pull' },
  { label: '多维表格拉取', value: 'bitable_pull' },
  { label: '手工创建', value: 'manual_create' }
]

/**
 * 获取自动拉取场景的中文标签。
 * @param {string} value 场景编码（external_sync 等）
 * @returns {string} 中文标签，未知或为空时返回原值或"未知场景"
 */
export function getLogPullSourceSceneLabel(value) {
  if (!value) return '未知场景'
  return logPullSourceSceneOptions.find(item => item.value === value)?.label || value
}

export function getStatusTagType(value) {
  return ticketStatusOptions.find(item => item.value === value)?.type || 'info'
}

export function getLogPullStatusTagType(value) {
  return logPullStatusOptions.find(item => item.value === value)?.type || 'info'
}

/**
 * 解析工单的外部详情链接。
 *
 * 多级兜底取值，与后端 `_decorate_ticket_item` 的同步摘要兜底互补：
 * ticketUrl（含后端装饰后的兜底值）→ syncSummary → extraData.externalSync.source。
 * @param {object} ticketRow 工单行数据（兼容 camelCase / snake_case）
 * @returns {string} 外部链接，无链接时返回空字符串
 */
export function resolveTicketDetailUrl(ticketRow) {
  const row = ticketRow || {}
  const syncSummary = row.syncSummary || row.sync_summary || {}
  const extraData = row.extraData || row.extra_data || {}
  const externalSync = extraData.externalSync || extraData.external_sync || {}
  const source = externalSync.source || {}
  const value = String(
    row.ticketUrl
      || row.ticket_url
      || row.url
      || syncSummary.ticketUrl
      || syncSummary.ticket_url
      || syncSummary.sourceRecordUrl
      || syncSummary.source_record_url
      || source.ticketUrl
      || source.ticket_url
      || source.recordUrl
      || source.record_url
      || ''
  ).trim()
  return value || ''
}
