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

export function getOptionLabel(options, value) {
  return options.find(item => item.value === value)?.label || value || '-'
}

export function getStatusTagType(value) {
  return ticketStatusOptions.find(item => item.value === value)?.type || 'info'
}
