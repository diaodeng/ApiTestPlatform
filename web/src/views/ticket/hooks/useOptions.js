/**
 * 工单选项加载 composable。
 *
 * 从 index.vue 提取所有选项加载和格式化函数（~30 个函数）。
 * 包括：项目/模块/版本/商家/Provider/Agent/Prompt/Push 选项加载，
 * 以及工单类型/状态/根因/解决方式等格式化辅助函数。
 */
import { ref } from 'vue'
import { listAiProviderOptions } from '@/api/system/aiprovider'
import { listAiPromptTemplateOptions } from '@/api/system/aiprompt'
import { all as listAllAgents } from '@/api/hrm/agent'
import { allPushConfig as listAllPushConfig } from '@/api/hrm/push'
import {
  getTicketLogPullVendorStoreOptions,
  listTicketLogPullProjectVendorMapOptions,
  getTicketStatClassificationOptions,
  listTicketProjectOptions,
  listTicketModuleOptions
} from '@/api/ticket/ticket'
// 分类选项从 API 动态加载（loadStatClassificationOptions），不使用静态枚举

export function useOptions() {
  // === 选项数据 refs ===
  const projectOptions = ref([])
  const projectVendorMapOptions = ref([])
  const formModuleOptions = ref([])
  const formVersionOptions = ref([])
  const queryModuleOptions = ref([])
  const queryModuleCodeOptions = ref([])
  const issueTypeOptions = ref([])
  const rootCauseTypeOptions = ref([])
  const solutionTypeOptions = ref([])
  const resolutionOptions = ref([])
  const problemPatternOptions = ref([])
  const agentOptions = ref([])
  const providerOptions = ref([])
  const analysisPromptOptions = ref([])
  const vendorOptions = ref([])
  const parameterExamples = ref([])
  const pushOptions = ref([])
  const detailVersionOptions = ref([])

  // === 商家/门店选项 ===
  function normalizeVendorOptions(rows = []) {
    return rows.map(item => ({
      vendorId: Number(item.vendorId),
      vendorCode: String(item.vendorCode || '').trim(),
      vendorName: String(item.vendorName || item.vendorId || '').trim(),
      label: buildVendorOptionLabel(item),
      stores: Array.isArray(item.stores)
        ? item.stores.map(store => ({
          storeId: String(store.storeId || '').trim(),
          storeCode: String(store.storeCode || '').trim(),
          sapOrgNo: String(store.sapOrgNo || '').trim(),
          storeName: String(store.storeName || store.storeId || '').trim(),
          label: buildStoreOptionLabel(store)
        }))
        : []
    }))
  }

  function buildVendorOptionLabel(vendor) {
    const name = String(vendor.vendorName || vendor.vendorId || '').trim()
    const code = String(vendor.vendorCode || '').trim()
    const id = String(vendor.vendorId || '').trim()
    return [name, code, id ? `[${id}]` : ''].filter(Boolean).join(' ')
  }

  function buildStoreOptionLabel(store) {
    const name = String(store.storeName || store.storeId || '').trim()
    const orgNo = String(store.storeCode || store.storeId || '').trim()
    const sapOrgNo = String(store.sapOrgNo || '').trim()
    return [name, orgNo ? `[${orgNo}]` : '', sapOrgNo ? `(${sapOrgNo})` : ''].filter(Boolean).join(' ')
  }

  function loadVendorOptions() {
    return getTicketLogPullVendorStoreOptions().then(response => {
      vendorOptions.value = normalizeVendorOptions(response.data?.vendors || [])
      parameterExamples.value = Array.isArray(response.data?.parameterExamples)
        ? response.data.parameterExamples
        : []
    })
  }

  function loadProjectVendorMapOptions() {
    return listTicketLogPullProjectVendorMapOptions().then(response => {
      projectVendorMapOptions.value = Array.isArray(response.data) ? response.data : []
    })
  }

  function getProjectVendorNo(projectId) {
    const resolvedProjectId = Number(projectId)
    if (!resolvedProjectId) return ''
    const mapping = projectVendorMapOptions.value.find(item => Number(item.projectId) === resolvedProjectId)
    return String(mapping?.venderNo || '').trim()
  }

  function applyProjectVendorMapping(projectId) {
    // Note: this also references logPullForm which is external - kept in index.vue
  }

  function getVendorStoreOptions(vendorId) {
    const resolvedVendorId = Number(vendorId)
    if (!vendorId && vendorId !== 0) return []
    const vendor = vendorOptions.value.find(v => Number(v.vendorId) === resolvedVendorId)
    return vendor?.stores || []
  }

  // === Provider / Agent / Prompt 选项 ===
  function loadProviderOptions() {
    return listAiProviderOptions().then(response => {
      providerOptions.value = response.data || []
    })
  }

  function loadAnalysisPromptOptions() {
    return listAiPromptTemplateOptions({
      template_category: 'analysis,common',
      enabled_only: true
    }).then(response => {
      analysisPromptOptions.value = response.data || []
    })
  }

  function getTicketAutomationLogPullConfig(ticketData = {}) {
    const extraData = ticketData.extraData || ticketData.extra_data || {}
    const automation = extraData.ticketAutomation || extraData.ticket_automation || {}
    return automation.logPullConfig || automation.log_pull_config || {}
  }

  function findAiProviderOption(providerCode) {
    const resolvedCode = String(providerCode || '').trim()
    if (!resolvedCode) return undefined
    return providerOptions.value.find(item => String(item.providerCode || '').trim() === resolvedCode)
  }

  function applyAiAnalysisProviderAgent(providerCode) {
    const provider = findAiProviderOption(providerCode)
    const providerAgentCode = String(provider?.agentCode || '').trim()
    if (providerAgentCode) {
      // Note: aiAnalysisTaskForm is external - caller needs to handle
      return providerAgentCode
    }
    return null
  }

  function handleAiAnalysisProviderChange(providerCode) {
    return applyAiAnalysisProviderAgent(providerCode)
  }

  function resolveDefaultAiPromptTemplateCodes(detail) {
    const contextCodes = detail?.latestAiAnalysis?.analysisContext?.selectedPromptTemplateCodes
    if (Array.isArray(contextCodes) && contextCodes.length) return contextCodes
    const config = getTicketAutomationLogPullConfig(detail || {})
    const rawCodes = config.promptTemplateCodes || config.prompt_template_codes || config.aiPromptTemplateCodes || config.ai_prompt_template_codes
    if (Array.isArray(rawCodes)) return rawCodes.map(item => String(item || '').trim()).filter(Boolean)
    if (typeof rawCodes === 'string') return rawCodes.split(',').map(item => item.trim()).filter(Boolean)
    return []
  }

  // === 版本选项 ===
  function loadDetailVersionOptions(projectId) {
    const resolvedId = Number(projectId)
    if (!resolvedId) {
      detailVersionOptions.value = []
      return
    }
    const mappings = Array.isArray(projectVendorMapOptions.value) ? projectVendorMapOptions.value : []
    const projectMappings = mappings.filter(item => Number(item.projectId) === resolvedId)
    const optionMap = new Map()
    for (const item of projectMappings) {
      const versionKey = String(item.versionKey || '').trim()
      if (versionKey && !optionMap.has(versionKey)) {
        optionMap.set(versionKey, {
          value: versionKey,
          label: `${versionKey} (${String(item.repoUrl || '').trim() || '-'})`
        })
      }
    }
    detailVersionOptions.value = Array.from(optionMap.values())
  }

  // === Push 选项 ===
  function loadPushOptions() {
    return listAllPushConfig().then(response => {
      pushOptions.value = Array.isArray(response.data) ? response.data : []
    })
  }

  // === 项目/模块选项 ===
  function loadProjectOptions() {
    return listTicketProjectOptions().then(response => {
      projectOptions.value = response.data || []
    })
  }

  function loadAgentOptions() {
    return listAllAgents().then(response => {
      agentOptions.value = (Array.isArray(response.data) ? response.data : [])
    })
  }

  function loadQueryModuleOptions(projectIds) {
    const ids = Array.isArray(projectIds) ? projectIds.filter(Boolean) : []
    if (!ids.length) {
      queryModuleOptions.value = []
      queryModuleCodeOptions.value = []
      return
    }
    return listTicketModuleOptions({ projectIds: ids }).then(response => {
      const modules = response.data || []
      queryModuleOptions.value = modules
      const codeSet = new Set()
      queryModuleCodeOptions.value = modules
        .map(item => String(item.moduleCode || '').trim())
        .filter(code => code && !codeSet.has(code) && codeSet.add(code))
        .map(code => ({ value: code, label: code }))
    })
  }

  function loadFormModuleOptions(projectId) {
    const resolvedId = Number(projectId)
    if (!resolvedId) {
      formModuleOptions.value = []
      formVersionOptions.value = []
      return
    }
    return listTicketModuleOptions({ projectIds: [resolvedId] }).then(response => {
      formModuleOptions.value = response.data || []
    }).then(() => {
      loadDetailVersionOptions(resolvedId)
    })
  }

  function loadFormVersionOptions(projectId) {
    loadDetailVersionOptions(projectId)
  }

  // === 格式化辅助函数 ===
  function getStatOptionLabel(options, value) {
    const text = String(value || '').trim()
    if (!text) return '-'
    const option = (options || []).find(item => item.value === text)
    return option?.label || text
  }

  function formatStatOption(options, value) {
    return getStatOptionLabel(options.value || options, value)
  }

  function formatProblemFlag(value) {
    if (value === true) return '真实问题'
    if (value === false) return '非问题'
    return '-'
  }

  function formatIssueType(row, localIssueTypeOptions) {
    const issueTypeName = row?.issueTypeName || row?.issue_type_name || ''
    if (issueTypeName) return issueTypeName
    const issueTypeId = row?.issueTypeId || row?.issue_type_id || ''
    if (!issueTypeId) return '-'
    const option = (localIssueTypeOptions || issueTypeOptions.value).find(item => item.value === String(issueTypeId).trim())
    return option?.label || '-'
  }

  function formatResolution(row) {
    const resolutionName = row?.resolutionName || row?.resolution_name || ''
    if (resolutionName) return resolutionName
    const resolutionCode = row?.resolutionCode || row?.resolution_code || ''
    return resolutionCode ? getStatOptionLabel(resolutionOptions.value, resolutionCode) : '-'
  }

  function formatProblemPattern(row) {
    const patternName = row?.problemPatternName || row?.problem_pattern_name || ''
    if (patternName) return patternName
    const patternCode = row?.problemPatternCode || row?.problem_pattern_code || ''
    return patternCode ? getStatOptionLabel(problemPatternOptions.value, patternCode) : '-'
  }

  // === 统计分类选项 ===
  function normalizeStatOptions(items = []) {
    return (Array.isArray(items) ? items : [])
      .map(item => ({
        value: String(item.value || item.code || '').trim(),
        label: String(item.label || item.name || item.value || item.code || '').trim()
      }))
      .filter(item => item.value)
  }

  function loadStatClassificationOptions() {
    return getTicketStatClassificationOptions().then(response => {
      const data = response.data || {}
      if (Array.isArray(data.issueTypes) && data.issueTypes.length) {
        issueTypeOptions.value = normalizeStatOptions(data.issueTypes)
      }
      if (Array.isArray(data.rootCauseTypes) && data.rootCauseTypes.length) {
        rootCauseTypeOptions.value = normalizeStatOptions(data.rootCauseTypes)
      }
      if (Array.isArray(data.solutionTypes) && data.solutionTypes.length) {
        solutionTypeOptions.value = normalizeStatOptions(data.solutionTypes)
      }
      if (Array.isArray(data.resolutionCodes) && data.resolutionCodes.length) {
        resolutionOptions.value = normalizeStatOptions(data.resolutionCodes)
      }
      if (Array.isArray(data.problemPatternCodes) && data.problemPatternCodes.length) {
        problemPatternOptions.value = normalizeStatOptions(data.problemPatternCodes)
      }
    })
  }

  return {
    // refs
    projectOptions, projectVendorMapOptions, formModuleOptions, formVersionOptions,
    queryModuleOptions, queryModuleCodeOptions, issueTypeOptions, rootCauseTypeOptions,
    solutionTypeOptions, resolutionOptions, problemPatternOptions,
    agentOptions, providerOptions, analysisPromptOptions, vendorOptions,
    parameterExamples, pushOptions, detailVersionOptions,
    // vendor/store functions
    normalizeVendorOptions, buildVendorOptionLabel, buildStoreOptionLabel,
    loadVendorOptions, loadProjectVendorMapOptions,
    getProjectVendorNo, applyProjectVendorMapping, getVendorStoreOptions,
    // provider/agent/prompt functions
    loadProviderOptions, loadAnalysisPromptOptions,
    getTicketAutomationLogPullConfig, findAiProviderOption,
    applyAiAnalysisProviderAgent, handleAiAnalysisProviderChange,
    resolveDefaultAiPromptTemplateCodes,
    // version functions
    loadDetailVersionOptions,
    // push functions
    loadPushOptions,
    // project/module functions
    loadProjectOptions, loadAgentOptions,
    loadQueryModuleOptions, loadFormModuleOptions, loadFormVersionOptions,
    // format helpers
    getStatOptionLabel, formatStatOption, formatProblemFlag,
    formatIssueType, formatResolution, formatProblemPattern,
    // stat classification
    normalizeStatOptions, loadStatClassificationOptions
  }
}
