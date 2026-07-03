/**
 * syncAutomation 配置管理 composable。
 * 包含：form 状态、load/save、配置规范化、映射文本管理。
 */
import { ref, reactive, computed } from 'vue'
import {
  getTicketSyncAutomationConfig,
  saveTicketSyncAutomationConfig,
  getTicketWorkflow
} from '@/api/ticket/ticket'

export function useSyncConfig(proxy) {
  const loading = ref(false)
  const saving = ref(false)
  const workflowStatusOptions = ref([])

  const mappingTexts = reactive({
    projectMappings: '[]', moduleMappings: '[]', vendorMappings: '[]',
    storeMappings: '[]', statusMappings: '[]', assigneeMappings: '[]',
  })
  const posPatternsText = ref('[]')
  const scoPatternsText = ref('[]')
  const versionPatternsText = ref('[]')

  const mappingSections = [
    { key: 'projectMappings', label: '项目映射', hint: '外部项目名 -> 内部 project_id' },
    { key: 'moduleMappings', label: '模块映射', hint: '外部模块名 -> 内部 module_id' },
    { key: 'vendorMappings', label: '商家映射', hint: '外部商家名 -> 内部 vendor_id' },
    { key: 'storeMappings', label: '门店映射', hint: '外部门店名 -> 内部 store_id' },
    { key: 'statusMappings', label: '状态映射', hint: '外部状态 -> 内部状态编码' },
    { key: 'assigneeMappings', label: '处理人映射', hint: '外部处理人 -> 内部用户 ID' },
  ]

  const notifySendModes = [
    { value: 'push_config', label: '推送配置' },
    { value: 'app_chat', label: '应用群聊' },
  ]
  const groupPushAutoStatusOptions = ['2. 1.5线处理', '3. 待产研处理', '4. 产研处理中']
  const externalSyncRequiredFieldOptions = [
    'ticketNo', 'description', 'internalPriority', 'ticketVender',
    'ticketModle', 'createTime', 'reporterName'
  ]
  const personDataSourceOptions = [
    { value: 'current_assignee', label: '当前处理人' },
    { value: 'first_line_assignee', label: '1线人员' },
    { value: 'internal_owner', label: '内部负责人' },
  ]
  const summaryDataSourceOptions = [
    { value: 'submit_time', label: '提交时间' },
    { value: 'create_time', label: '创建时间' },
  ]
  const personLocalTimeFieldOptions = [
    { value: 'submit_time', label: '提交时间' },
    { value: 'create_time', label: '创建时间' },
    { value: 'last_modified_time', label: '最后修改时间' },
  ]
  const summaryTimeFieldOptions = [
    { value: 'submit_time', label: '提交时间' },
    { value: 'create_time', label: '创建时间' },
  ]

  const externalFieldModelOptions = computed(() =>
    workflowStatusOptions.value.map(item => ({ value: item.value, label: item.label }))
  )

  const rules = {
    pushIds: [{ required: true, message: '请选择推送渠道', trigger: 'change' }],
    ticketNo: [{ required: true, message: '请输入工单号', trigger: 'blur' }],
  }

  function createRemoteRequiredValidator(message) {
    return (rule, value, callback) => {
      const rows = normalizeArray(value)
      if (!rows.length) { callback(new Error(message)); return }
      callback()
    }
  }

  const remoteRules = {
    syncRemoteConsumer: [
      { required: true, message: '请输入远程同步 consumer 标识', trigger: 'blur' }
    ],
    syncRemotePullUrl: [
      { required: true, message: '请输入拉取工单 URL', trigger: 'blur' }
    ],
  }

  const defaultStatClassification = {
    issueTypes: [],
    rootCauseTypes: [
      { value: 'product_defect', label: '产品缺陷' },
      { value: 'config_issue', label: '配置问题' },
      { value: 'data_issue', label: '数据问题' },
      { value: 'third_party', label: '第三方依赖' },
      { value: 'operation_error', label: '操作失误' },
      { value: 'demand_change', label: '需求变更' },
      { value: 'other', label: '其他' },
    ],
    solutionTypes: [
      { value: 'code_fix', label: '代码修复' },
      { value: 'config_fix', label: '配置修正' },
      { value: 'data_fix', label: '数据修正' },
      { value: 'process_improve', label: '流程优化' },
      { value: 'workaround', label: '临时方案' },
      { value: 'no_action', label: '无需处理' },
    ],
    resolutionCodes: [
      { value: 'resolved', label: '已解决' },
      { value: 'wont_fix', label: '不予修复' },
      { value: 'duplicate', label: '重复工单' },
      { value: 'not_reproducible', label: '无法复现' },
      { value: 'by_design', label: '设计如此' },
    ],
    problemPatternCodes: [
      { value: 'payment_timeout', label: '支付超时', remark: '支付接口超时或未响应' },
      { value: 'order_sync_fail', label: '订单同步失败', remark: '订单数据同步异常' },
    ],
  }

  function createDefaultForm() {
    return {
      autoRunOnSync: false,
      autoTranslateOnSync: true,
      defaultPullLimit: 50,
      feishuAuth: { appId: '', appSecret: '' },
      bitableCommon: { appId: '', appSecret: '', appToken: '', tableId: '', viewId: '', pageSize: 500, filterFormula: '' },
      externalFieldModel: [],
      externalSyncRequiredFields: [...externalSyncRequiredFieldOptions],
      externalSyncBitable: { enabled: false, appId: '', appSecret: '', appToken: '', tableId: '', viewId: '' },
      bitablePull: {
        enabled: false, appId: '', appSecret: '',
        appToken: '', tableId: '', viewId: '',
        pageSize: 200, filterFormula: '',
        sourceSystem: 'feishu_bitable_pull',
        ticketNoField: 'ticketNo', updatedAtField: '', sortField: '',
        includeRecordUrl: true, forceSync: false, fieldMappings: [],
        automation: { autoIdentify: true, autoLogPull: false, autoAiAnalysis: false, autoTranslate: true },
      },
      groupPush: {
        enabled: false, sendMode: 'push_config', pushIds: [], appChatIds: [],
        autoPushStatuses: [...groupPushAutoStatusOptions],
        priorityRoutes: [],
        sendAfterExternalSync: false, sendAfterRemotePull: false,
        autoSendAfterTime: '', template: '', manualTemplate: '',
      },
      messageSync: {
        enabled: false, feishuEventEnabled: false, feishuWsEnabled: false,
        feishuWsEncryptKey: '', feishuWsVerificationToken: '',
        allowedChatIds: [], ignoreBotOpenIds: [],
        syncFeishuCommentToTicket: true, syncFeishuCommentToBitable: false,
        syncTicketCommentToBitable: false, syncTicketCommentToFeishuThread: false,
        syncBitableNewStepToFeishuThread: false,
        bitableStepReasonField: 'stepReason', bitableTicketNoField: 'ticketNo',
        appendStepReasonFormat: '{date} {user}：{content}',
      },
      personReminder: {
        enabled: false, sendMode: 'push_config', dataSource: 'bitable',
        pushIds: [], appId: '', appSecret: '',
        feishuAppId: '', feishuAppSecret: '',
        appToken: '', tableId: '', viewId: '', filterFormula: '',
        personField: '', timeField: '', thresholdMinutes: 30,
        messageTemplate: '', maxRowsPerPerson: 20, rowsMarkdownTemplate: '', pageSize: 500,
      },
      summaryReport: {
        enabled: false, sendMode: 'push_config', dataSource: 'local',
        pushIds: [], appChatIds: [], appId: '', appSecret: '',
        timeField: 'create_time', appToken: '', tableId: '', viewId: '', filterFormula: '',
        statusField: '状态', categoryField: '分类', priorityField: '优先级',
        bitableTimeField: '', pageSize: 500,
        aiEnabled: false, aiProviderCode: '', aiPromptCode: '',
        windowMinutes: 60, endDelayMinutes: 0,
        startTime: '', endTime: '', includeClosed: true, messageTemplate: '',
      },
      remoteSync: {
        enabled: false, pullUrl: '', ackUrl: '', consumer: '',
        sourceSystem: 'public', limit: 50, includeClosed: true,
        autoTranslateOnPull: true, timeoutSec: 30,
        headers: { cookie: '', authorization: '', origin: '' },
      },
      statClassification: JSON.parse(JSON.stringify(defaultStatClassification)),
      aiClassification: {
        enabled: false, runOnExternalSync: false, runOnRemotePull: false,
        runOnManualCreate: false, runOnStatusChange: false,
        statusChangeTriggerStatuses: [], statusChangeForceReclassify: false,
        providerCode: '', promptCode: 'ticket_stat_classify_default', promptContent: '',
      },
      logPullDefaults: {
        commandDataType: 1, fileMaxSize: 500, zipMaxSize: 500,
        storageMode: 'local', rangeBeforeMinutes: 10, rangeAfterMinutes: 10,
        autoAiEnabled: false, aiAgentCode: '', aiProviderCode: '',
      },
      promptTemplates: { classificationHint: '' },
    }
  }

  const form = reactive(createDefaultForm())

  // === 规范化辅助函数 ===
  function normalizeArray(value, fallback = []) {
    if (Array.isArray(value)) return value
    if (typeof value === 'string') {
      try { const parsed = JSON.parse(value); return Array.isArray(parsed) ? parsed : fallback }
      catch (e) { return fallback }
    }
    return fallback
  }

  function normalizeStatOptionRows(value, fallback = [], allowProblemFlag = false) {
    const sourceRows = Array.isArray(value) ? value : fallback
    const seenValues = new Set()
    const rows = []
    for (const item of sourceRows) {
      const optionValue = String(item?.value || item?.code || item?.id || '').trim()
      const optionLabel = String(item?.label || item?.name || optionValue).trim()
      if (!optionValue || seenValues.has(optionValue)) continue
      seenValues.add(optionValue)
      const row = { value: optionValue, label: optionLabel }
      const remark = String(item?.remark || '').trim()
      if (remark) row.remark = remark
      rows.push(row)
    }
    return rows
  }

  function normalizeStatClassificationConfig(value = {}) {
    const source = value && typeof value === 'object' ? value : {}
    return {
      issueTypes: normalizeStatOptionRows(source.issueTypes),
      rootCauseTypes: normalizeStatOptionRows(source.rootCauseTypes, defaultStatClassification.rootCauseTypes),
      solutionTypes: normalizeStatOptionRows(source.solutionTypes, defaultStatClassification.solutionTypes),
      resolutionCodes: normalizeStatOptionRows(source.resolutionCodes, defaultStatClassification.resolutionCodes),
      problemPatternCodes: normalizeStatOptionRows(source.problemPatternCodes, defaultStatClassification.problemPatternCodes, true),
    }
  }

  function normalizeDateTimeText(value) {
    const text = String(value || '').trim()
    if (!text) return ''
    const normalized = text.replace('T', ' ')
    const fullMatch = normalized.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)
    if (fullMatch) return fullMatch[0]
    const minuteMatch = normalized.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/)
    if (minuteMatch) return minuteMatch[0] + ':00'
    return text.substring(0, 19)
  }

  function normalizeWorkflowStatusOptions(statuses = []) {
    return (statuses || []).map(item => {
      const value = String(item.code || item.value || '').trim()
      const label = String(item.name || item.label || value).trim()
      return value ? { value, label } : null
    }).filter(Boolean)
  }

  function parseJsonArray(text, fallback = []) {
    try { const parsed = JSON.parse(text || '[]'); return Array.isArray(parsed) ? parsed : fallback }
    catch (e) { return fallback }
  }

  // === Config load/save ===
  function applyConfig(payload) {
    if (!payload || typeof payload !== 'object') return
    const feishuAuth = payload.feishuAuth || {}
    form.feishuAuth.appId = feishuAuth.appId || ''
    form.feishuAuth.appSecret = feishuAuth.appSecret || ''
    const bitableCommon = payload.bitableCommon || {}
    form.bitableCommon.appToken = bitableCommon.appToken || ''
    form.bitableCommon.tableId = bitableCommon.tableId || ''
    form.externalFieldModel = normalizeArray(payload.externalFieldModel || [])
    form.externalSyncRequiredFields = normalizeArray(payload.externalSyncRequiredFields || externalSyncRequiredFieldOptions)
    if (payload.externalSyncBitable) {
      const b = payload.externalSyncBitable
      form.externalSyncBitable = {
        appToken: b.appToken || '', tableId: b.tableId || '',
        filterConfig: typeof b.filterConfig === 'string' ? b.filterConfig : JSON.stringify(b.filterConfig || {}),
        fieldMappings: normalizeArray(b.fieldMappings || []),
      }
    }
    if (payload.bitablePull) {
      const p = payload.bitablePull
      form.bitablePull = {
        enabled: !!p.enabled, appId: p.appId || '', appSecret: p.appSecret || '',
        appToken: p.appToken || '', tableId: p.tableId || '', viewId: p.viewId || '',
        pageSize: p.pageSize || 200, filterFormula: p.filterFormula || '',
        sourceSystem: p.sourceSystem || 'feishu_bitable_pull',
        ticketNoField: p.ticketNoField || 'ticketNo',
        updatedAtField: p.updatedAtField || '', sortField: p.sortField || '',
        includeRecordUrl: p.includeRecordUrl !== false, forceSync: !!p.forceSync,
        fieldMappings: normalizeArray(p.fieldMappings || []),
        automation: {
          autoIdentify: p.automation?.autoIdentify !== false,
          autoLogPull: !!p.automation?.autoLogPull,
          autoAiAnalysis: !!p.automation?.autoAiAnalysis,
          autoTranslate: p.automation?.autoTranslate !== false,
        },
      }
    }
    if (payload.groupPush) Object.assign(form.groupPush, payload.groupPush)
    if (payload.messageSync) Object.assign(form.messageSync, payload.messageSync)
    if (payload.personReminder) Object.assign(form.personReminder, payload.personReminder)
    if (payload.summaryReport) Object.assign(form.summaryReport, payload.summaryReport)
    if (payload.remoteSync) Object.assign(form.remoteSync, payload.remoteSync)
    if (payload.statClassification) {
      form.statClassification = normalizeStatClassificationConfig(payload.statClassification)
    }
    if (payload.aiClassification) {
      form.aiClassification = {
        enabled: !!payload.aiClassification.enabled,
        providerCode: payload.aiClassification.providerCode || '',
        promptCode: payload.aiClassification.promptCode || '',
        statusTriggers: normalizeArray(payload.aiClassification.statusTriggers || []),
        forceReclassify: !!payload.aiClassification.forceReclassify,
      }
    }
    if (payload.logPullDefaults) Object.assign(form.logPullDefaults, payload.logPullDefaults)
    if (payload.promptTemplates) Object.assign(form.promptTemplates, payload.promptTemplates)
    if (payload.autoRunOnSync !== undefined) form.autoRunOnSync = !!payload.autoRunOnSync
    if (payload.autoTranslateOnSync !== undefined) form.autoTranslateOnSync = !!payload.autoTranslateOnSync
    if (payload.defaultPullLimit !== undefined) form.defaultPullLimit = payload.defaultPullLimit
    mappingTexts.projectMappings = JSON.stringify(normalizeArray(payload.projectMappings), null, 2)
    mappingTexts.moduleMappings = JSON.stringify(normalizeArray(payload.moduleMappings), null, 2)
    mappingTexts.vendorMappings = JSON.stringify(normalizeArray(payload.vendorMappings), null, 2)
    mappingTexts.storeMappings = JSON.stringify(normalizeArray(payload.storeMappings), null, 2)
    mappingTexts.statusMappings = JSON.stringify(normalizeArray(payload.statusMappings), null, 2)
    mappingTexts.assigneeMappings = JSON.stringify(normalizeArray(payload.assigneeMappings), null, 2)
    posPatternsText.value = JSON.stringify(normalizeArray(payload.posPatterns), null, 2)
    scoPatternsText.value = JSON.stringify(normalizeArray(payload.scoPatterns), null, 2)
    versionPatternsText.value = JSON.stringify(normalizeArray(payload.versionPatterns), null, 2)
  }

  function loadConfig() {
    loading.value = true
    return getTicketSyncAutomationConfig().then(res => {
      applyConfig((res.data && res.data.configValue) || res.data || {})
    }).finally(() => { loading.value = false })
  }

  function loadWorkflowStatuses() {
    return getTicketWorkflow().then(res => {
      workflowStatusOptions.value = normalizeWorkflowStatusOptions(res.data?.statuses || [])
    })
  }

  // === Save ===
  function validateElForm(refName) {
    return new Promise((resolve) => {
      proxy.$refs[refName]?.validate(valid => resolve(valid))
    })
  }

  async function handleSave() {
    saving.value = true
    try {
      const payload = {
        autoRunOnSync: form.autoRunOnSync,
        autoTranslateOnSync: form.autoTranslateOnSync,
        defaultPullLimit: form.defaultPullLimit,
        feishuAuth: { ...form.feishuAuth },
        bitableCommon: { ...form.bitableCommon },
        externalFieldModel: [...form.externalFieldModel],
        externalSyncRequiredFields: [...form.externalSyncRequiredFields],
        externalSyncBitable: { ...form.externalSyncBitable },
        bitablePull: {
          ...form.bitablePull,
          fieldMappings: [...form.bitablePull.fieldMappings],
        },
        groupPush: { ...form.groupPush },
        messageSync: { ...form.messageSync },
        personReminder: { ...form.personReminder },
        summaryReport: { ...form.summaryReport },
        remoteSync: { ...form.remoteSync },
        statClassification: JSON.parse(JSON.stringify(form.statClassification)),
        aiClassification: { ...form.aiClassification },
        logPullDefaults: { ...form.logPullDefaults },
        promptTemplates: { ...form.promptTemplates },
        projectMappings: parseJsonArray(mappingTexts.projectMappings),
        moduleMappings: parseJsonArray(mappingTexts.moduleMappings),
        vendorMappings: parseJsonArray(mappingTexts.vendorMappings),
        storeMappings: parseJsonArray(mappingTexts.storeMappings),
        statusMappings: parseJsonArray(mappingTexts.statusMappings),
        assigneeMappings: parseJsonArray(mappingTexts.assigneeMappings),
        posPatterns: parseJsonArray(posPatternsText.value),
        scoPatterns: parseJsonArray(scoPatternsText.value),
        versionPatterns: parseJsonArray(versionPatternsText.value),
      }
      const result = await saveTicketSyncAutomationConfig(payload)
      proxy.$modal.msgSuccess(result.msg || '保存成功')
    } catch (e) { console.error(e) }
    finally { saving.value = false }
  }

  // === Stat option management ===
  function addStatOption(groupKey) {
    if (!form.statClassification[groupKey]) return
    form.statClassification[groupKey].push({ value: '', label: '', remark: '' })
  }
  function removeStatOption(groupKey, index) {
    form.statClassification[groupKey]?.splice(index, 1)
  }
  function addExternalFieldModel() {
    form.externalFieldModel.push({ fieldKey: '', fieldName: '', fieldType: 'string' })
  }
  function removeExternalFieldModel(index) { form.externalFieldModel.splice(index, 1) }
  function addBitablePullFieldMapping() {
    form.bitablePull.fieldMappings.push({ sourceField: '', targetField: '' })
  }
  function removeBitablePullFieldMapping(index) {
    form.bitablePull.fieldMappings.splice(index, 1)
  }

  return {
    loading, saving, workflowStatusOptions,
    mappingTexts, posPatternsText, scoPatternsText, versionPatternsText,
    mappingSections, notifySendModes, groupPushAutoStatusOptions,
    externalSyncRequiredFieldOptions, personDataSourceOptions,
    summaryDataSourceOptions, personLocalTimeFieldOptions,
    summaryTimeFieldOptions, externalFieldModelOptions,
    rules, remoteRules, defaultStatClassification,
    form, createDefaultForm,
    normalizeArray, normalizeStatOptionRows, normalizeStatClassificationConfig,
    normalizeDateTimeText, normalizeWorkflowStatusOptions, parseJsonArray,
    applyConfig, loadConfig, loadWorkflowStatuses,
    validateElForm, handleSave,
    addStatOption, removeStatOption, addExternalFieldModel,
    removeExternalFieldModel, addBitablePullFieldMapping, removeBitablePullFieldMapping,
  }
}
