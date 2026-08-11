/**
 * 工单工作流配置 composable。
 *
 * 从 index.vue 提取：
 * - workflowConfig: 工作流状态节点和流转规则
 * - ticketStatusOptions: 动态状态下拉选项（合并默认枚举）
 * - statusTransitionOptions: 当前状态可流转的目标状态
 * - getStatusTagType: 状态标签颜色映射
 * - loadWorkflowConfig: 加载工作流配置
 */
import { ref, computed } from 'vue'
import { getTicketWorkflow } from '@/api/ticket/ticket'
import {
  getStatusTagType as getDefaultStatusTagType,
  ticketStatusOptions as defaultTicketStatusOptions
} from '@/views/ticket/constants'

export function useWorkflow(currentTicketStatus) {
  /** 工作流状态节点和流转规则 */
  const workflowConfig = ref({
    statuses: [],
    transitions: []
  })

  /**
   * 将工作流状态节点规范化为下拉选项。
   * @param {Array} statuses 工作流状态节点列表
   * @returns {Array} 规范化的 { label, value, type, orderNum } 数组
   */
  function normalizeWorkflowStatusOptions(statuses = []) {
    return (statuses || [])
      .map(item => {
        const value = String(item.code || '').trim()
        if (!value) {
          return null
        }
        const fallback = defaultTicketStatusOptions.find(option => option.value === value)
        return {
          label: String(item.name || fallback?.label || value).trim(),
          value,
          type: fallback?.type || 'info',
          orderNum: Number(item.orderNum ?? item.order_num ?? 0)
        }
      })
      .filter(Boolean)
      .sort((a, b) => a.orderNum - b.orderNum)
  }

  /**
   * 获取工单状态标签颜色类型。
   * @param {string} value 状态值
   * @returns {string} Element UI tag type
   */
  function getStatusTagType(value) {
    return ticketStatusOptions.value.find(item => item.value === value)?.type || getDefaultStatusTagType(value)
  }

  /** 加载工作流配置（状态节点 + 流转规则） */
  function loadWorkflowConfig() {
    return getTicketWorkflow().then(response => {
      workflowConfig.value = response.data || { statuses: [], transitions: [] }
    }).catch(() => {
      workflowConfig.value = { statuses: [], transitions: [] }
    })
  }

  /** 动态状态下拉选项，若无自定义工作流则回退到默认枚举 */
  const ticketStatusOptions = computed(() => {
    const dynamicOptions = normalizeWorkflowStatusOptions(workflowConfig.value.statuses)
    return dynamicOptions.length ? dynamicOptions : defaultTicketStatusOptions
  })

  /** 当前状态可流转的目标状态列表 */
  const statusTransitionOptions = computed(() => {
    const fromStatus = String(currentTicketStatus?.value || '').trim()
    if (!fromStatus) {
      return []
    }
    const toStatusSet = new Set(
      (workflowConfig.value.transitions || [])
        .filter(item => String(item.fromStatus || '').trim() === fromStatus)
        .map(item => String(item.toStatus || '').trim())
        .filter(Boolean)
    )
    return ticketStatusOptions.value.filter(item => toStatusSet.has(item.value))
  })

  return {
    workflowConfig,
    ticketStatusOptions,
    statusTransitionOptions,
    normalizeWorkflowStatusOptions,
    getStatusTagType,
    loadWorkflowConfig
  }
}
