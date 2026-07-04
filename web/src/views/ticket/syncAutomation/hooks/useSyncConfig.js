/**
 * syncAutomation 配置管理 composable。
 * 包含：form 状态、load/save、配置规范化、映射文本管理。
 *
 * NOTE: 此文件从 index.vue <script> 中提取，拆分后需保持与原逻辑完全一致。
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
    {
      key: 'projectMappings', label: '项目映射',
      description: '示例：[{"keywords":["支付中心","pay-center"],"projectId":1001,"projectName":"支付平台"}]',
      rows: 6,
    },
    {
      key: 'moduleMappings', label: '模块映射',
      description: '示例：[{"keywords":["订单服务","order-service"],"moduleId":2001,"moduleName":"订单模块"}]',
      rows: 6,
    },
    {
      key: 'vendorMappings', label: '商家映射',
      description: '示例：[{"keywords":["京东","jd"],"vendorId":3001,"vendorName":"京东商户"}]',
      rows: 6,
    },
    {
      key: 'storeMappings', label: '门店映射',
      description: '示例：[{"keywords":["北京一店","bj-01"],"storeId":4001,"storeName":"北京一店"}]',
      rows: 6,
    },
    {
      key: 'statusMappings', label: '状态映射',
      description: '示例：[{"keywords":["处理中","processing"],"status":"PROCESSING"}]',
      rows: 6,
    },
    {
      key: 'assigneeMappings', label: '处理人映射',
      description: '示例：[{"keywords":["张三"],"userId":5001,"userName":"张三","email":"zhangsan@example.com"}]',
      rows: 6,
    },
  ]

  const notifySendModes = [
    { label: '推送配置(机器人)', value: 'push_config' },
    { label: '飞书应用身份', value: 'feishu_app' },
    { label: '两种都发', value: 'hybrid' },
  ]

  const groupPushAutoStatusOptions = ['2. 1.5线处理', '3. 待产研处理', '4. 产研处理中']

  const externalSyncRequiredFieldOptions = [
    { label: 'ticketNo - 工单号', value: 'ticketNo' },
    { label: 'description - 问题描述', value: 'description' },
    { label: 'internalPriority - 内部优先级', value: 'internalPriority' },
    { label: 'ticketVender - 商家/供应商', value: 'ticketVender' },
    { label: 'ticketModle - 模块', value: 'ticketModle' },
    { label: 'createTime - 创建时间', value: 'createTime' },
    { label: 'reporterName - 1线处理人/报告人', value: 'reporterName' },
    { label: 'currentAssigneeName - 当前处理人', value: 'currentAssigneeName' },
    { label: 'internalOwner - 内部负责人', value: 'internalOwner' },
    { label: 'recordId - 飞书多维记录ID', value: 'recordId' },
  ]

  /** 外部字段模型选项：基于 form.externalFieldModel.fields 派生，用于接口字段下拉。 */
  const externalFieldModelOptions = computed(() =>
    Array.isArray(form.externalFieldModel?.fields)
      ? form.externalFieldModel.fields
          .map((item) => ({
            label: `${String(item?.fieldName || '').trim()} - ${String(item?.label || '').trim() || String(item?.fieldName || '').trim()}`,
            value: String(item?.fieldName || '').trim(),
          }))
          .filter((item) => item.value)
      : []
  )

  const personDataSourceOptions = [
    { label: '飞书多维表格统计', value: 'bitable' },
    { label: '本地工单数据统计', value: 'local' },
  ]

  const summaryDataSourceOptions = [
    { label: '本地工单数据统计', value: 'local' },
    { label: '飞书多维表格统计', value: 'bitable' },
  ]

  const personLocalTimeFieldOptions = [
    { label: '更新时间(update_time)', value: 'update_time' },
    { label: '创建时间(create_time)', value: 'create_time' },
    { label: '开始时间(started_at)', value: 'started_at' },
    { label: '解决时间(resolved_at)', value: 'resolved_at' },
    { label: '关闭时间(closed_at)', value: 'closed_at' },
  ]

  const summaryTimeFieldOptions = [
    { label: '创建时间', value: 'create_time' },
    { label: '更新时间', value: 'update_time' },
    { label: '关闭时间', value: 'closed_at' },
    { label: '解决时间', value: 'resolved_at' },
  ]

  const rules = {
    defaultPullLimit: [{ required: true, message: '默认拉取数量不能为空', trigger: 'change' }],
  }

  function createRemoteRequiredValidator(message) {
    return (_rule, value, callback) => {
      if (!form.remoteSync.enabled) {
        callback()
        return
      }
      if (String(value ?? '').trim()) {
        callback()
        return
      }
      callback(new Error(message))
    }
  }

  const remoteRules = {
    pullUrl: [{ validator: createRemoteRequiredValidator('拉取地址不能为空'), trigger: 'blur' }],
    ackUrl: [{ validator: createRemoteRequiredValidator('回写地址不能为空'), trigger: 'blur' }],
    consumer: [{ validator: createRemoteRequiredValidator('消费者标识不能为空'), trigger: 'blur' }],
    limit: [{ required: true, message: '每次拉取数量不能为空', trigger: 'change' }],
    timeoutSec: [{ required: true, message: '抓取超时不能为空', trigger: 'change' }],
  }

  const defaultStatClassification = {
    issueTypes: [
      { value: 'system_bug', label: '系统Bug', isProblem: true },
      { value: 'data_error', label: '数据错误', isProblem: true },
      { value: 'config_issue', label: '配置问题', isProblem: true },
      { value: 'performance_issue', label: '性能问题', isProblem: true },
      { value: 'support_consulting', label: '支持咨询', isProblem: false },
      { value: 'requirement_consulting', label: '需求咨询', isProblem: false },
      { value: 'user_operation', label: '用户操作问题', isProblem: false },
      { value: 'api_exception', label: '接口异常', isProblem: true },
    ],
    rootCauseTypes: [
      { value: 'code_defect', label: '代码缺陷' },
      { value: 'config_error', label: '配置错误' },
      { value: 'data_exception', label: '数据异常' },
      { value: 'third_party', label: '第三方问题' },
      { value: 'network_issue', label: '网络问题' },
      { value: 'environment_issue', label: '环境问题' },
      { value: 'operation_mistake', label: '操作失误' },
      { value: 'requirement_design', label: '需求设计问题' },
      { value: 'unknown', label: '未知' },
    ],
    solutionTypes: [
      { value: 'code_fix', label: '代码修复' },
      { value: 'config_fix', label: '配置修复' },
      { value: 'data_fix', label: '数据修复' },
      { value: 'temporary_workaround', label: '临时处理' },
      { value: 'manual_process', label: '人工处理' },
      { value: 'no_action', label: '无需处理' },
    ],
    resolutions: [
      { value: 'fixed', label: '已修复', isProblem: true },
      { value: 'non_problem', label: '非问题', isProblem: false },
      { value: 'data_processed', label: '数据已处理', isProblem: true },
      { value: 'config_fixed', label: '配置已修复', isProblem: true },
      { value: 'user_canceled', label: '用户撤销', isProblem: false },
      { value: 'duplicated', label: '重复工单', isProblem: false },
      { value: 'cannot_reproduce', label: '无法复现', isProblem: null },
      { value: 'as_designed', label: '需求如此', isProblem: false },
      { value: 'transferred', label: '已转其他团队', isProblem: null },
    ],
    problemPatterns: [
      {
        value: 'memory_leak',
        label: '内存泄露',
        moduleCode: '',
        issueTypeId: 'performance_issue',
        isProblem: true,
        rootCauseType: 'code_defect',
        resolutionCode: 'fixed',
        description: '进程内存持续增长、未释放或最终 OOM 的问题模式。',
        positiveExamples: ['内存泄露', '内存泄漏', 'memory leak', 'OOM'],
        negativeExamples: ['单次内存高峰', '磁盘空间不足'],
        enabled: true,
      },
      {
        value: 'coupon_280_paper_rule',
        label: '280开头券为纸质券规则说明',
        moduleCode: 'coupon',
        issueTypeId: 'support_consulting',
        isProblem: false,
        rootCauseType: 'requirement_design',
        resolutionCode: 'as_designed',
        description: '用户反馈280开头券不能按电子券处理，实际业务规则定义为纸质券。',
        positiveExamples: ['280开头券', '纸质券', '券规则说明'],
        negativeExamples: ['电子券接口报错', '券配置错误'],
        enabled: true,
      },
    ],
  }

  function createDefaultForm() {
    return {
      autoRunOnSync: false,
      autoTranslateOnSync: true,
      defaultPullLimit: 50,
      feishuAuth: { appId: '', appSecret: '' },
      bitableCommon: {
        appId: '', appSecret: '', appToken: '', tableId: '', viewId: '',
        pageSize: 500, filterFormula: '',
      },
      externalFieldModel: {
        fields: externalSyncRequiredFieldOptions.map((item) => ({
          fieldName: item.value,
          label: item.label.split(' - ')[1] || item.value,
          required: ['ticketNo', 'description', 'internalPriority', 'ticketVender', 'ticketModle', 'createTime', 'reporterName'].includes(item.value),
          category: 'basic',
          description: '',
        })),
      },
      remoteSync: {
        enabled: false, pullUrl: '', ackUrl: '', consumer: '',
        sourceSystem: 'public', limit: 50, includeClosed: true,
        autoTranslateOnPull: true, timeoutSec: 30,
        headers: { cookie: '', authorization: '', origin: '' },
      },
      groupPush: {
        enabled: false, sendMode: 'push_config', pushIds: [], appChatIds: [],
        autoPushStatuses: ['2. 1.5线处理', '3. 待产研处理', '4. 产研处理中'],
        priorityRoutes: [
          { priorities: ['P1'], pushIds: [], chatIds: [] },
          { priorities: ['P2'], pushIds: [], chatIds: [] },
          { priorities: ['P3', 'P4'], pushIds: [], chatIds: [] },
        ],
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
      externalSyncBitable: {
        enabled: false, appId: '', appSecret: '', appToken: '', tableId: '', viewId: '',
      },
      bitablePull: {
        enabled: false, appId: '', appSecret: '', appToken: '', tableId: '', viewId: '',
        pageSize: 200, filterFormula: '',
        sourceSystem: 'feishu_bitable_pull',
        ticketNoField: 'ticketNo', updatedAtField: '', sortField: '',
        includeRecordUrl: true, forceSync: false, fieldMappings: [],
        automation: {
          autoIdentify: true, autoLogPull: false, autoAiAnalysis: false, autoTranslate: true,
        },
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
      projectMappings: [],
      moduleMappings: [],
      vendorMappings: [],
      storeMappings: [],
      statusMappings: [],
      assigneeMappings: [],
      posPatterns: [],
      scoPatterns: [],
      versionPatterns: [],
      logPullDefaults: {
        commandDataType: 1, fileMaxSize: 500, zipMaxSize: 500,
        storageMode: 'local', rangeBeforeMinutes: 10, rangeAfterMinutes: 10,
        autoAiEnabled: false, aiAgentCode: '', aiProviderCode: '',
      },
      promptTemplates: { classificationHint: '' },
      aiClassification: {
        enabled: false,
        runOnExternalSync: false,
        runOnRemotePull: false,
        runOnManualCreate: false,
        runOnStatusChange: false,
        statusChangeTriggerStatuses: [],
        statusChangeForceReclassify: false,
        providerCode: '',
        promptCode: 'ticket_stat_classify_default',
        promptContent: '',
      },
      statClassification: normalizeStatClassificationConfig(),
      externalSyncRequiredFields: [
        'ticketNo', 'description', 'internalPriority', 'ticketVender',
        'ticketModle', 'createTime', 'reporterName',
      ],
    }
  }

  const form = reactive(createDefaultForm())

  // === 规范化辅助函数 ===

  function normalizeArray(value, fallback = []) {
    if (Array.isArray(value)) return value
    if (typeof value === 'string' && value.trim()) {
      try { const parsed = JSON.parse(value); return Array.isArray(parsed) ? parsed : fallback }
      catch (e) { return fallback }
    }
    return fallback
  }

  function normalizeDateTimeText(value) {
    const text = String(value || '').trim()
    if (!text) {
      return ''
    }
    const normalized = text.replace('T', ' ')
    const fullMatch = normalized.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)
    if (fullMatch?.[0]) {
      return fullMatch[0]
    }
    const minuteMatch = normalized.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/)
    if (minuteMatch?.[0]) {
      return `${minuteMatch[0]}:00`
    }
    return text
  }

  function normalizeWorkflowStatusOptions(statuses = []) {
    if (!Array.isArray(statuses)) return []
    return statuses
      .map((item) => {
        const value = String(item.code || item.value || '').trim()
        const label = String(item.name || item.label || value).trim()
        return value ? { value, label: label || value } : null
      })
      .filter(Boolean)
  }

  function normalizeStatOptionRows(value, fallback = [], allowProblemFlag = false) {
    const sourceRows = Array.isArray(value) ? value : fallback
    const seenValues = new Set()
    const rows = []
    sourceRows.forEach((item) => {
      const optionValue = String(item?.value || item?.code || item?.id || '').trim()
      const optionLabel = String(item?.label || item?.name || optionValue).trim()
      if (!optionValue || seenValues.has(optionValue)) return
      const row = { value: optionValue, label: optionLabel || optionValue }
      if (allowProblemFlag) {
        row.isProblem = typeof item?.isProblem === 'boolean' ? item.isProblem : null
      }
      const remark = String(item?.remark || '').trim()
      if (remark) row.remark = remark
      ;[
        'moduleCode', 'issueTypeId', 'rootCauseType', 'resolutionCode',
        'description', 'positiveExamples', 'negativeExamples', 'enabled',
      ].forEach((key) => {
        if (Object.prototype.hasOwnProperty.call(item || {}, key)) {
          row[key] = item[key]
        }
      })
      rows.push(row)
      seenValues.add(optionValue)
    })
    return rows.length ? rows : fallback.map((item) => ({ ...item }))
  }

  function normalizeStatClassificationConfig(value = {}) {
    const source = value && typeof value === 'object' ? value : {}
    return {
      issueTypes: normalizeStatOptionRows(source.issueTypes, defaultStatClassification.issueTypes, true),
      rootCauseTypes: normalizeStatOptionRows(source.rootCauseTypes, defaultStatClassification.rootCauseTypes),
      solutionTypes: normalizeStatOptionRows(source.solutionTypes, defaultStatClassification.solutionTypes),
      resolutions: normalizeStatOptionRows(source.resolutions, defaultStatClassification.resolutions, true),
      problemPatterns: normalizeStatOptionRows(source.problemPatterns, defaultStatClassification.problemPatterns, true),
    }
  }

  function parseJsonArray(text, fallback = []) {
    if (!String(text || '').trim()) {
      return fallback
    }
    try {
      const parsed = JSON.parse(text)
      return Array.isArray(parsed) ? parsed : fallback
    } catch (error) {
      throw new Error('请检查JSON数组格式是否正确')
    }
  }

  // === Config load ===

  function applyConfig(payload) {
    form.autoRunOnSync = Boolean(payload.autoRunOnSync)
    form.autoTranslateOnSync = payload.autoTranslateOnSync !== false
    form.defaultPullLimit = Number(payload.defaultPullLimit || 50)
    form.statClassification = normalizeStatClassificationConfig(payload.statClassification)

    const feishuAuth = payload.feishuAuth || {}
    form.feishuAuth = {
      appId: feishuAuth.appId || '',
      appSecret: feishuAuth.appSecret || '',
    }

    const bitableCommon = payload.bitableCommon || {}
    form.bitableCommon = {
      appId: bitableCommon.appId || '',
      appSecret: bitableCommon.appSecret || '',
      appToken: bitableCommon.appToken || '',
      tableId: bitableCommon.tableId || '',
      viewId: bitableCommon.viewId || '',
      pageSize: Number(bitableCommon.pageSize || 500),
      filterFormula: bitableCommon.filterFormula || '',
    }

    const externalFieldModel = payload.externalFieldModel || {}
    form.externalFieldModel = {
      fields: Array.isArray(externalFieldModel.fields)
        ? externalFieldModel.fields.map((item) => ({
            fieldName: String(item?.fieldName || '').trim(),
            label: String(item?.label || '').trim(),
            required: Boolean(item?.required),
            category: String(item?.category || 'custom').trim(),
            description: String(item?.description || '').trim(),
          }))
        : createDefaultForm().externalFieldModel.fields,
    }

    const remoteSync = payload.remoteSync || {}
    form.remoteSync = {
      enabled: Boolean(remoteSync.enabled),
      pullUrl: remoteSync.pullUrl || '',
      ackUrl: remoteSync.ackUrl || '',
      consumer: remoteSync.consumer || '',
      sourceSystem: remoteSync.sourceSystem || 'public',
      limit: Number(remoteSync.limit || 50),
      includeClosed: remoteSync.includeClosed !== false,
      autoTranslateOnPull: remoteSync.autoTranslateOnPull !== false,
      timeoutSec: Number(remoteSync.timeoutSec || 30),
      headers: {
        cookie: remoteSync.headers?.cookie || '',
        authorization: remoteSync.headers?.authorization || '',
        origin: remoteSync.headers?.origin || '',
      },
    }

    const externalSyncBitable = payload.externalSyncBitable || {}
    form.externalSyncBitable = {
      enabled: Boolean(externalSyncBitable.enabled),
      appId: externalSyncBitable.appId || '',
      appSecret: externalSyncBitable.appSecret || '',
      appToken: externalSyncBitable.appToken || '',
      tableId: externalSyncBitable.tableId || '',
      viewId: externalSyncBitable.viewId || '',
    }

    const bitablePull = payload.bitablePull || {}
    form.bitablePull = {
      enabled: Boolean(bitablePull.enabled),
      appId: bitablePull.appId || '',
      appSecret: bitablePull.appSecret || '',
      appToken: bitablePull.appToken || '',
      tableId: bitablePull.tableId || '',
      viewId: bitablePull.viewId || '',
      pageSize: Number(bitablePull.pageSize || 200),
      filterFormula: bitablePull.filterFormula || '',
      sourceSystem: bitablePull.sourceSystem || 'feishu_bitable_pull',
      ticketNoField: bitablePull.ticketNoField || 'ticketNo',
      updatedAtField: bitablePull.updatedAtField || '',
      sortField: bitablePull.sortField || '',
      includeRecordUrl: bitablePull.includeRecordUrl !== false,
      forceSync: Boolean(bitablePull.forceSync),
      fieldMappings: Array.isArray(bitablePull.fieldMappings)
        ? bitablePull.fieldMappings.map((item) => ({
            sourceField: String(item?.sourceField || '').trim(),
            targetField: String(item?.targetField || '').trim(),
            defaultValue: item?.defaultValue ?? '',
            joinSeparator: String(item?.joinSeparator || ',').trim() || ',',
          }))
        : [],
      automation: {
        autoIdentify: bitablePull.automation?.autoIdentify !== false,
        autoLogPull: Boolean(bitablePull.automation?.autoLogPull),
        autoAiAnalysis: Boolean(bitablePull.automation?.autoAiAnalysis),
        autoTranslate: bitablePull.automation?.autoTranslate !== false,
      },
    }

    const groupPush = payload.groupPush || {}
    form.groupPush = {
      enabled: Boolean(groupPush.enabled),
      sendMode: groupPush.sendMode || 'push_config',
      pushIds: Array.isArray(groupPush.pushIds)
        ? groupPush.pushIds.map((item) => Number(item)).filter((item) => Number.isFinite(item))
        : [],
      appChatIds: Array.isArray(groupPush.appChatIds)
        ? groupPush.appChatIds.map((item) => String(item).trim()).filter(Boolean)
        : [],
      autoPushStatuses: Array.isArray(groupPush.autoPushStatuses)
        ? groupPush.autoPushStatuses.map((item) => String(item || '').trim()).filter(Boolean)
        : ['2. 1.5线处理', '3. 待产研处理', '4. 产研处理中'],
      priorityRoutes: Array.isArray(groupPush.priorityRoutes)
        ? groupPush.priorityRoutes.map((route) => ({
            priorities: Array.isArray(route?.priorities)
              ? route.priorities.map((item) => String(item).trim()).filter(Boolean)
              : [],
            pushIds: Array.isArray(route?.pushIds)
              ? route.pushIds.map((item) => Number(item)).filter((item) => Number.isFinite(item))
              : [],
            chatIds: Array.isArray(route?.chatIds)
              ? route.chatIds.map((item) => String(item).trim()).filter(Boolean)
              : [],
          }))
        : [],
      sendAfterExternalSync: Boolean(groupPush.sendAfterExternalSync),
      sendAfterRemotePull: Boolean(groupPush.sendAfterRemotePull),
      autoSendAfterTime: normalizeDateTimeText(groupPush.autoSendAfterTime || groupPush.auto_send_after_time),
      template: groupPush.template || '',
      manualTemplate: groupPush.manualTemplate || '',
    }
    if (!form.groupPush.priorityRoutes.length) {
      form.groupPush.priorityRoutes = [
        { priorities: ['P1'], pushIds: [], chatIds: [] },
        { priorities: ['P2'], pushIds: [], chatIds: [] },
        { priorities: ['P3', 'P4'], pushIds: [], chatIds: [] },
      ]
    }

    const messageSync = payload.messageSync || {}
    form.messageSync = {
      enabled: Boolean(messageSync.enabled),
      feishuEventEnabled: Boolean(messageSync.feishuEventEnabled),
      feishuWsEnabled: Boolean(messageSync.feishuWsEnabled),
      feishuWsEncryptKey: messageSync.feishuWsEncryptKey || '',
      feishuWsVerificationToken: messageSync.feishuWsVerificationToken || '',
      allowedChatIds: Array.isArray(messageSync.allowedChatIds)
        ? messageSync.allowedChatIds.map((item) => String(item || '').trim()).filter(Boolean)
        : [],
      ignoreBotOpenIds: Array.isArray(messageSync.ignoreBotOpenIds)
        ? messageSync.ignoreBotOpenIds.map((item) => String(item || '').trim()).filter(Boolean)
        : [],
      syncFeishuCommentToTicket: messageSync.syncFeishuCommentToTicket !== false,
      syncFeishuCommentToBitable: Boolean(messageSync.syncFeishuCommentToBitable),
      syncTicketCommentToBitable: Boolean(messageSync.syncTicketCommentToBitable),
      syncTicketCommentToFeishuThread: Boolean(messageSync.syncTicketCommentToFeishuThread),
      syncBitableNewStepToFeishuThread: Boolean(messageSync.syncBitableNewStepToFeishuThread),
      bitableStepReasonField: messageSync.bitableStepReasonField || 'stepReason',
      bitableTicketNoField: messageSync.bitableTicketNoField || 'ticketNo',
      appendStepReasonFormat: messageSync.appendStepReasonFormat || '{date} {user}：{content}',
    }

    const personReminder = payload.personReminder || {}
    form.personReminder = {
      enabled: Boolean(personReminder.enabled),
      sendMode: personReminder.sendMode || 'push_config',
      dataSource: ['bitable', 'local'].includes(String(personReminder.dataSource || '').trim().toLowerCase())
        ? String(personReminder.dataSource || '').trim().toLowerCase()
        : 'bitable',
      pushIds: Array.isArray(personReminder.pushIds)
        ? personReminder.pushIds.map((item) => Number(item)).filter((item) => Number.isFinite(item))
        : [],
      appId: personReminder.appId || '',
      appSecret: personReminder.appSecret || '',
      feishuAppId: personReminder.feishuAppId || '',
      feishuAppSecret: personReminder.feishuAppSecret || '',
      appToken: personReminder.appToken || '',
      tableId: personReminder.tableId || '',
      viewId: personReminder.viewId || '',
      filterFormula: personReminder.filterFormula || '',
      personField: personReminder.personField || '',
      timeField: personReminder.timeField || '',
      thresholdMinutes: Number(personReminder.thresholdMinutes || 30),
      messageTemplate: personReminder.messageTemplate || '',
      rowsMarkdownTemplate: personReminder.rowsMarkdownTemplate || '',
      maxRowsPerPerson: Number(personReminder.maxRowsPerPerson || 20),
      pageSize: Number(personReminder.pageSize || 500),
    }

    const summaryReport = payload.summaryReport || {}
    form.summaryReport = {
      enabled: Boolean(summaryReport.enabled),
      sendMode: summaryReport.sendMode || 'push_config',
      dataSource: ['bitable', 'local'].includes(String(summaryReport.dataSource || '').trim().toLowerCase())
        ? String(summaryReport.dataSource || '').trim().toLowerCase()
        : 'local',
      pushIds: Array.isArray(summaryReport.pushIds)
        ? summaryReport.pushIds.map((item) => Number(item)).filter((item) => Number.isFinite(item))
        : [],
      appChatIds: Array.isArray(summaryReport.appChatIds)
        ? summaryReport.appChatIds.map((item) => String(item).trim()).filter(Boolean)
        : [],
      appId: summaryReport.appId || '',
      appSecret: summaryReport.appSecret || '',
      timeField: summaryReport.timeField || 'create_time',
      appToken: summaryReport.appToken || '',
      tableId: summaryReport.tableId || '',
      viewId: summaryReport.viewId || '',
      filterFormula: summaryReport.filterFormula || '',
      statusField: summaryReport.statusField || '状态',
      categoryField: summaryReport.categoryField || '分类',
      priorityField: summaryReport.priorityField || '优先级',
      bitableTimeField: summaryReport.bitableTimeField || '',
      pageSize: Number(summaryReport.pageSize || 500),
      aiEnabled: Boolean(summaryReport.aiEnabled),
      aiProviderCode: summaryReport.aiProviderCode || '',
      aiPromptCode: summaryReport.aiPromptCode || '',
      windowMinutes: Number(summaryReport.windowMinutes || 60),
      endDelayMinutes: Number(summaryReport.endDelayMinutes || 0),
      startTime: summaryReport.startTime || '',
      endTime: summaryReport.endTime || '',
      includeClosed: summaryReport.includeClosed !== false,
      messageTemplate: summaryReport.messageTemplate || '',
    }

    const aiClassification = payload.aiClassification || {}
    form.aiClassification = {
      enabled: Boolean(aiClassification.enabled),
      runOnExternalSync: Boolean(aiClassification.runOnExternalSync),
      runOnRemotePull: Boolean(aiClassification.runOnRemotePull),
      runOnManualCreate: Boolean(aiClassification.runOnManualCreate),
      runOnStatusChange: Boolean(aiClassification.runOnStatusChange),
      statusChangeTriggerStatuses: Array.isArray(aiClassification.statusChangeTriggerStatuses)
        ? aiClassification.statusChangeTriggerStatuses.map((item) => String(item || '').trim()).filter(Boolean)
        : [],
      statusChangeForceReclassify: Boolean(aiClassification.statusChangeForceReclassify),
      providerCode: aiClassification.providerCode || '',
      promptCode: aiClassification.promptCode || 'ticket_stat_classify_default',
      promptContent: aiClassification.promptContent || '',
    }

    form.projectMappings = normalizeArray(payload.projectMappings)
    form.moduleMappings = normalizeArray(payload.moduleMappings)
    form.vendorMappings = normalizeArray(payload.vendorMappings)
    form.storeMappings = normalizeArray(payload.storeMappings)
    form.statusMappings = normalizeArray(payload.statusMappings)
    form.assigneeMappings = normalizeArray(payload.assigneeMappings)
    form.posPatterns = normalizeArray(payload.posPatterns)
    form.scoPatterns = normalizeArray(payload.scoPatterns)
    form.versionPatterns = normalizeArray(payload.versionPatterns)

    mappingTexts.projectMappings = JSON.stringify(normalizeArray(payload.projectMappings), null, 2)
    mappingTexts.moduleMappings = JSON.stringify(normalizeArray(payload.moduleMappings), null, 2)
    mappingTexts.vendorMappings = JSON.stringify(normalizeArray(payload.vendorMappings), null, 2)
    mappingTexts.storeMappings = JSON.stringify(normalizeArray(payload.storeMappings), null, 2)
    mappingTexts.statusMappings = JSON.stringify(normalizeArray(payload.statusMappings), null, 2)
    mappingTexts.assigneeMappings = JSON.stringify(normalizeArray(payload.assigneeMappings), null, 2)
    posPatternsText.value = JSON.stringify(normalizeArray(payload.posPatterns), null, 2)
    scoPatternsText.value = JSON.stringify(normalizeArray(payload.scoPatterns), null, 2)
    versionPatternsText.value = JSON.stringify(normalizeArray(payload.versionPatterns), null, 2)

    const logPullDefaults = payload.logPullDefaults || {}
    form.logPullDefaults = {
      commandDataType: Number(logPullDefaults.commandDataType || 1),
      fileMaxSize: Number(logPullDefaults.fileMaxSize || 500),
      zipMaxSize: Number(logPullDefaults.zipMaxSize || 500),
      storageMode: logPullDefaults.storageMode || 'local',
      rangeBeforeMinutes: Number(logPullDefaults.rangeBeforeMinutes || 10),
      rangeAfterMinutes: Number(logPullDefaults.rangeAfterMinutes || 10),
      autoAiEnabled: Boolean(logPullDefaults.autoAiEnabled),
      aiAgentCode: logPullDefaults.aiAgentCode || '',
      aiProviderCode: logPullDefaults.aiProviderCode || '',
    }

    const promptTemplates = payload.promptTemplates || {}
    form.promptTemplates = {
      classificationHint: promptTemplates.classificationHint || '',
    }

    form.externalSyncRequiredFields = normalizeArray(
      payload.externalSyncRequiredFields,
      ['ticketNo', 'description', 'internalPriority', 'ticketVender', 'ticketModle', 'createTime', 'reporterName']
    )
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
    }).catch(() => {
      workflowStatusOptions.value = []
    })
  }

  // === Save ===

  function validateElForm(refName) {
    return new Promise((resolve) => {
      const formRef = proxy.$refs[refName]
      if (!formRef || typeof formRef.validate !== 'function') {
        resolve(true)
        return
      }
      formRef.validate((valid) => resolve(valid))
    })
  }

  async function handleSave() {
    const [basicValid, remoteValid] = await Promise.all([
      validateElForm('formRef'),
      validateElForm('remoteFormRef'),
    ])
    if (!basicValid || !remoteValid) return

    saving.value = true
    try {
      const payload = JSON.parse(JSON.stringify(form))
      mappingSections.forEach((item) => {
        payload[item.key] = parseJsonArray(mappingTexts[item.key])
      })
      payload.posPatterns = parseJsonArray(posPatternsText.value)
      payload.scoPatterns = parseJsonArray(scoPatternsText.value)
      payload.versionPatterns = parseJsonArray(versionPatternsText.value)

      payload.feishuAuth = {
        appId: String(payload.feishuAuth?.appId || '').trim(),
        appSecret: String(payload.feishuAuth?.appSecret || '').trim(),
      }
      payload.bitableCommon = {
        appId: String(payload.bitableCommon?.appId || '').trim(),
        appSecret: String(payload.bitableCommon?.appSecret || '').trim(),
        appToken: String(payload.bitableCommon?.appToken || '').trim(),
        tableId: String(payload.bitableCommon?.tableId || '').trim(),
        viewId: String(payload.bitableCommon?.viewId || '').trim(),
        pageSize: Math.min(Math.max(Number(payload.bitableCommon?.pageSize || 500), 1), 500),
        filterFormula: String(payload.bitableCommon?.filterFormula || '').trim(),
      }
      payload.externalFieldModel = {
        fields: Array.isArray(payload.externalFieldModel?.fields)
          ? payload.externalFieldModel.fields
              .map((item) => ({
                fieldName: String(item?.fieldName || '').trim(),
                label: String(item?.label || '').trim(),
                required: Boolean(item?.required),
                category: String(item?.category || 'custom').trim(),
                description: String(item?.description || '').trim(),
              }))
              .filter((item) => item.fieldName)
          : [],
      }
      payload.groupPush.appChatIds = Array.isArray(payload.groupPush?.appChatIds)
        ? payload.groupPush.appChatIds.map((item) => String(item || '').trim()).filter(Boolean)
        : []
      payload.groupPush.autoPushStatuses = Array.isArray(payload.groupPush?.autoPushStatuses)
        ? Array.from(new Set(payload.groupPush.autoPushStatuses.map((item) => String(item || '').trim()).filter(Boolean)))
        : []
      payload.groupPush.autoSendAfterTime = normalizeDateTimeText(payload.groupPush?.autoSendAfterTime)
      payload.groupPush.priorityRoutes = Array.isArray(payload.groupPush?.priorityRoutes)
        ? payload.groupPush.priorityRoutes
            .map((route) => ({
              priorities: Array.isArray(route?.priorities)
                ? route.priorities.map((item) => String(item || '').trim().toUpperCase()).filter(Boolean)
                : [],
              pushIds: Array.isArray(route?.pushIds)
                ? route.pushIds.map((item) => Number(item)).filter((item) => Number.isFinite(item))
                : [],
              chatIds: Array.isArray(route?.chatIds)
                ? route.chatIds.map((item) => String(item || '').trim()).filter(Boolean)
                : [],
            }))
            .filter((route) => route.priorities.length > 0)
        : []
      payload.messageSync = {
        enabled: Boolean(payload.messageSync?.enabled),
        feishuEventEnabled: Boolean(payload.messageSync?.feishuEventEnabled),
        feishuWsEnabled: Boolean(payload.messageSync?.feishuWsEnabled),
        feishuWsEncryptKey: String(payload.messageSync?.feishuWsEncryptKey || '').trim(),
        feishuWsVerificationToken: String(payload.messageSync?.feishuWsVerificationToken || '').trim(),
        allowedChatIds: Array.isArray(payload.messageSync?.allowedChatIds)
          ? payload.messageSync.allowedChatIds.map((item) => String(item || '').trim()).filter(Boolean)
          : [],
        ignoreBotOpenIds: Array.isArray(payload.messageSync?.ignoreBotOpenIds)
          ? payload.messageSync.ignoreBotOpenIds.map((item) => String(item || '').trim()).filter(Boolean)
          : [],
        syncFeishuCommentToTicket: payload.messageSync?.syncFeishuCommentToTicket !== false,
        syncFeishuCommentToBitable: Boolean(payload.messageSync?.syncFeishuCommentToBitable),
        syncTicketCommentToBitable: Boolean(payload.messageSync?.syncTicketCommentToBitable),
        syncTicketCommentToFeishuThread: Boolean(payload.messageSync?.syncTicketCommentToFeishuThread),
        syncBitableNewStepToFeishuThread: Boolean(payload.messageSync?.syncBitableNewStepToFeishuThread),
        bitableStepReasonField: String(payload.messageSync?.bitableStepReasonField || 'stepReason').trim(),
        bitableTicketNoField: String(payload.messageSync?.bitableTicketNoField || 'ticketNo').trim(),
        appendStepReasonFormat: String(payload.messageSync?.appendStepReasonFormat || '{date} {user}：{content}').trim(),
      }
      payload.externalSyncBitable = {
        enabled: Boolean(payload.externalSyncBitable?.enabled),
        appId: String(payload.externalSyncBitable?.appId || '').trim(),
        appSecret: String(payload.externalSyncBitable?.appSecret || '').trim(),
        appToken: String(payload.externalSyncBitable?.appToken || '').trim(),
        tableId: String(payload.externalSyncBitable?.tableId || '').trim(),
        viewId: String(payload.externalSyncBitable?.viewId || '').trim(),
      }
      payload.bitablePull = {
        enabled: Boolean(payload.bitablePull?.enabled),
        appId: String(payload.bitablePull?.appId || '').trim(),
        appSecret: String(payload.bitablePull?.appSecret || '').trim(),
        appToken: String(payload.bitablePull?.appToken || '').trim(),
        tableId: String(payload.bitablePull?.tableId || '').trim(),
        viewId: String(payload.bitablePull?.viewId || '').trim(),
        pageSize: Math.min(Math.max(Number(payload.bitablePull?.pageSize || 200), 1), 500),
        filterFormula: String(payload.bitablePull?.filterFormula || '').trim(),
        sourceSystem: String(payload.bitablePull?.sourceSystem || 'feishu_bitable_pull').trim(),
        ticketNoField: String(payload.bitablePull?.ticketNoField || 'ticketNo').trim(),
        updatedAtField: String(payload.bitablePull?.updatedAtField || '').trim(),
        sortField: String(payload.bitablePull?.sortField || '').trim(),
        includeRecordUrl: Boolean(payload.bitablePull?.includeRecordUrl),
        forceSync: Boolean(payload.bitablePull?.forceSync),
        fieldMappings: Array.isArray(payload.bitablePull?.fieldMappings)
          ? payload.bitablePull.fieldMappings
              .map((item) => ({
                sourceField: String(item?.sourceField || '').trim(),
                targetField: String(item?.targetField || '').trim(),
                defaultValue: item?.defaultValue ?? '',
                joinSeparator: String(item?.joinSeparator || ',').trim() || ',',
              }))
              .filter((item) => item.sourceField && item.targetField)
          : [],
        automation: {
          autoIdentify: payload.bitablePull?.automation?.autoIdentify !== false,
          autoLogPull: Boolean(payload.bitablePull?.automation?.autoLogPull),
          autoAiAnalysis: Boolean(payload.bitablePull?.automation?.autoAiAnalysis),
          autoTranslate: payload.bitablePull?.automation?.autoTranslate !== false,
        },
      }
      payload.personReminder.appId = String(payload.personReminder?.appId || '').trim()
      payload.personReminder.appSecret = String(payload.personReminder?.appSecret || '').trim()
      payload.personReminder.rowsMarkdownTemplate = String(payload.personReminder?.rowsMarkdownTemplate || '').trim()
      payload.personReminder.dataSource = ['bitable', 'local'].includes(
        String(payload.personReminder?.dataSource || '').trim().toLowerCase()
      )
        ? String(payload.personReminder?.dataSource || '').trim().toLowerCase()
        : 'bitable'
      payload.personReminder.feishuAppId = payload.personReminder.appId
      payload.personReminder.feishuAppSecret = payload.personReminder.appSecret
      payload.summaryReport.appChatIds = Array.isArray(payload.summaryReport?.appChatIds)
        ? payload.summaryReport.appChatIds.map((item) => String(item || '').trim()).filter(Boolean)
        : []
      payload.summaryReport.dataSource = ['bitable', 'local'].includes(
        String(payload.summaryReport?.dataSource || '').trim().toLowerCase()
      )
        ? String(payload.summaryReport?.dataSource || '').trim().toLowerCase()
        : 'local'
      payload.summaryReport.appId = String(payload.summaryReport?.appId || '').trim()
      payload.summaryReport.appSecret = String(payload.summaryReport?.appSecret || '').trim()
      payload.summaryReport.appToken = String(payload.summaryReport?.appToken || '').trim()
      payload.summaryReport.tableId = String(payload.summaryReport?.tableId || '').trim()
      payload.summaryReport.viewId = String(payload.summaryReport?.viewId || '').trim()
      payload.summaryReport.filterFormula = String(payload.summaryReport?.filterFormula || '').trim()
      payload.summaryReport.statusField = String(payload.summaryReport?.statusField || '状态').trim() || '状态'
      payload.summaryReport.categoryField = String(payload.summaryReport?.categoryField || '分类').trim() || '分类'
      payload.summaryReport.priorityField = String(payload.summaryReport?.priorityField || '优先级').trim() || '优先级'
      payload.summaryReport.bitableTimeField = String(payload.summaryReport?.bitableTimeField || '').trim()
      payload.summaryReport.pageSize = Math.min(Math.max(Number(payload.summaryReport?.pageSize || 500), 1), 500)
      payload.summaryReport.aiEnabled = Boolean(payload.summaryReport?.aiEnabled)
      payload.summaryReport.aiProviderCode = String(payload.summaryReport?.aiProviderCode || '').trim()
      payload.summaryReport.aiPromptCode = String(payload.summaryReport?.aiPromptCode || '').trim()
      payload.aiClassification = {
        enabled: Boolean(payload.aiClassification?.enabled),
        runOnExternalSync: Boolean(payload.aiClassification?.runOnExternalSync),
        runOnRemotePull: Boolean(payload.aiClassification?.runOnRemotePull),
        runOnManualCreate: Boolean(payload.aiClassification?.runOnManualCreate),
        runOnStatusChange: Boolean(payload.aiClassification?.runOnStatusChange),
        statusChangeTriggerStatuses: Array.isArray(payload.aiClassification?.statusChangeTriggerStatuses)
          ? Array.from(new Set(payload.aiClassification.statusChangeTriggerStatuses.map((item) => String(item || '').trim()).filter(Boolean)))
          : [],
        statusChangeForceReclassify: Boolean(payload.aiClassification?.statusChangeForceReclassify),
        providerCode: String(payload.aiClassification?.providerCode || '').trim(),
        promptCode: String(payload.aiClassification?.promptCode || '').trim() || 'ticket_stat_classify_default',
        promptContent: '',
      }
      payload.externalSyncRequiredFields = Array.isArray(payload.externalSyncRequiredFields)
        ? Array.from(new Set(payload.externalSyncRequiredFields.map((item) => String(item || '').trim()).filter(Boolean)))
        : payload.externalFieldModel.fields.filter((item) => item.required).map((item) => item.fieldName)
      payload.statClassification = normalizeStatClassificationConfig(payload.statClassification)

      await saveTicketSyncAutomationConfig(payload)
      proxy.$modal.msgSuccess('保存成功')
      loadConfig()
    } catch (error) {
      proxy.$modal.msgError(error?.message || '保存失败，请检查配置内容')
    } finally {
      saving.value = false
    }
  }

  // === Stat option management ===
  function addStatOption(groupKey) {
    if (!Array.isArray(form.statClassification[groupKey])) {
      form.statClassification[groupKey] = []
    }
    form.statClassification[groupKey].push({
      value: '',
      label: '',
      remark: '',
      ...(groupKey === 'issueTypes' || groupKey === 'resolutions' || groupKey === 'problemPatterns' ? { isProblem: null } : {}),
      ...(groupKey === 'problemPatterns'
        ? {
            moduleCode: '',
            issueTypeId: '',
            rootCauseType: '',
            resolutionCode: '',
            description: '',
            positiveExamples: [],
            negativeExamples: [],
            enabled: true,
          }
        : {}),
    })
  }

  function removeStatOption(groupKey, index) {
    if (!Array.isArray(form.statClassification[groupKey])) return
    form.statClassification[groupKey].splice(index, 1)
  }

  function addExternalFieldModel() {
    if (!Array.isArray(form.externalFieldModel.fields)) {
      form.externalFieldModel.fields = []
    }
    form.externalFieldModel.fields.push({
      fieldName: '',
      label: '',
      required: false,
      category: 'custom',
      description: '',
    })
  }

  function removeExternalFieldModel(index) {
    if (!Array.isArray(form.externalFieldModel.fields)) return
    form.externalFieldModel.fields.splice(index, 1)
  }

  function addBitablePullFieldMapping() {
    if (!Array.isArray(form.bitablePull.fieldMappings)) {
      form.bitablePull.fieldMappings = []
    }
    form.bitablePull.fieldMappings.push({ sourceField: '', targetField: '', defaultValue: '', joinSeparator: ',' })
  }

  function removeBitablePullFieldMapping(index) {
    if (!Array.isArray(form.bitablePull.fieldMappings)) {
      return
    }
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
