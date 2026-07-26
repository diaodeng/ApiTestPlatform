<script setup name="TicketDetailWithList">
  import { computed, getCurrentInstance, reactive, ref, toRefs, watch } from 'vue';
  import TicketDetailOverviewTab from './detail-tabs/TicketDetailOverviewTab.vue';
  import TicketDetailLogPullTab from './detail-tabs/TicketDetailLogPullTab.vue';
  import TicketDetailCollabTab from './detail-tabs/TicketDetailCollabTab.vue';
  import TicketDetailCommentsTab from './detail-tabs/TicketDetailCommentsTab.vue';
  import TicketDetailHistoryTab from './detail-tabs/TicketDetailHistoryTab.vue';
  import {
    addTicketAiAnalysis,
    createAndBindTicketIssue,
    getTicket,
    getTicketLogPullProjectVendorMap,
    listTicketAiAnalysisTasks,
    retryTicketAiAnalysis,
    saveTicketLogPullProjectVendorMap,
    translateTicketDescription,
    unbindTicketIssue,
  } from '@/api/ticket/ticket';
  import {
    getLogPullStatusTagType,
    getOptionLabel,
    logPullStatusOptions,
    severityOptions,
    sourceOptions,
  } from '../constants';
  import { useAiRepoMapping } from '../hooks/useAiRepoMapping';
  import { useOptions } from '../hooks/useOptions';
  import { useWorkflow } from '../hooks/useWorkflow';
  import {
    buildTicketAiPreferenceDefaults,
    saveTicketAiPreferencePatch,
  } from '../hooks/useTicketAiPreference';

  const props = defineProps({
    open: {
      type: Boolean,
      default: false,
    },
    ticketId: {
      type: [Number, String],
      default: undefined,
    },
  });

  const emit = defineEmits(['update:open', 'changed', 'closed']);

  const { proxy } = getCurrentInstance();
  const currentTicketId = ref();
  const detailOpen = computed({
    get: () => props.open,
    set: (value) => emit('update:open', value),
  });

  /**
   * 通知父组件详情数据已改变，父组件只需要按需刷新列表。
   * @returns {Promise<void>} 与原 getList 调用兼容的 Promise
   */
  function emitChanged() {
    emit('changed');
    return Promise.resolve();
  }

  const {
    projectOptions,
    rootCauseTypeOptions,
    solutionTypeOptions,
    agentOptions,
    providerOptions,
    analysisPromptOptions,
    detailVersionOptions,
    loadProjectVendorMapOptions,
    loadProviderOptions,
    loadAnalysisPromptOptions,
    getTicketAutomationLogPullConfig,
    resolveAiAnalysisProviderAgent,
    resolveDefaultAiPromptTemplateCodesFromDetail,
    loadDetailVersionOptions,
    loadProjectOptions,
    loadAgentOptions,
    formatStatOption,
    formatProblemFlag,
    formatIssueType,
    formatResolution,
    formatProblemPattern,
  } = useOptions();
  const currentTicketStatus = ref('');
  const { ticketStatusOptions, getStatusTagType, loadWorkflowConfig } =
    useWorkflow(currentTicketStatus);

  const detailMainTab = ref('overview');
  const descriptionExpanded = ref(true);
  const translationExpanded = ref(false);
  const detailMoreInfoExpanded = ref(false);
  const descriptionTranslateLoading = ref(false);
  const issueCreateBindOpen = ref(false);
  const issueActionLoading = ref(false);
  const issueCreateBindForm = ref({});
  const detail = ref({});
  const aiAnalysisSubmitting = ref(false);
  const aiAnalysisRetryLoading = ref(false);
  const aiAnalysisRefreshLoading = ref(false);
  const aiAnalysisOpen = ref(false);
  const aiTaskHistoryOpen = ref(false);
  const aiTaskDetailOpen = ref(false);
  const selectedAiTask = ref(null);
  // aiRepoMapping* 已提取到 hooks/useAiRepoMapping.js
  const {
    aiRepoMappingOpen,
    aiRepoMappingSubmitting,
    aiRepoMappingList,
    aiRepoMappingTotal,
    aiRepoMappingForm,
    aiRepoMappingRules,
    resetAiRepoMappingForm,
    openAiRepoMappingDialog,
    submitAiRepoMapping,
  } = useAiRepoMapping(detail, proxy);
  const projectVendorMapOpen = ref(false);
  const projectVendorMapLoading = ref(false);
  const projectVendorMapSubmitting = ref(false);
  const aiTaskLoading = ref(false);
  const aiTaskList = ref([]);
  const aiTaskTotal = ref(0);
  // detailVersionOptions 已通过 useOptions() 提供
  const aiAnalysisTaskForm = ref({
    versionKey: '',
    logPullRecordId: undefined,
    agentCode: '',
    aiProviderCode: '',
    forceRefresh: false,
    logAnalysisMode: 'hybrid',
    logTimeMode: 'none',
    logWindowMissingStrategy: 'agent_extract',
    logBeginTime: '',
    logEndTime: '',
    logPointTime: '',
    rangeBeforeMinutes: 5,
    rangeAfterMinutes: 10,
    extraInstruction: '',
    promptTemplateCodes: [],
  });

  /**
   * 根据 Provider 绑定关系回填 AI 分析 Agent。
   * useOptions 只负责解析选项，页面层负责写入当前分析表单。
   */
  function applyAiAnalysisProviderAgent(providerCode) {
    const providerAgentCode = resolveAiAnalysisProviderAgent(providerCode);
    if (providerAgentCode) {
      aiAnalysisTaskForm.value.agentCode = providerAgentCode;
    }
  }

  /**
   * 记录发起 AI 分析弹窗中用户手动选择的 Agent。
   */
  function handleAiAnalysisAgentChange(agentCode) {
    saveTicketAiPreferencePatch({ agentCode });
  }

  /**
   * 处理 AI 分析 Provider 变更，保持与备份分支一致的 Agent 自动带入行为。
   */
  function handleAiAnalysisProviderChange(providerCode) {
    applyAiAnalysisProviderAgent(providerCode);
    saveTicketAiPreferencePatch({
      aiProviderCode: providerCode,
      agentCode: aiAnalysisTaskForm.value.agentCode,
    });
  }

  /**
   * 记录发起 AI 分析弹窗中用户手动选择的追加提示词。
   */
  function handleAiAnalysisPromptTemplateChange(promptTemplateCodes) {
    saveTicketAiPreferencePatch({ promptTemplateCodes });
  }

  /**
   * 从当前工单详情解析默认追加提示词编码。
   */
  function resolveDefaultAiPromptTemplateCodes() {
    return resolveDefaultAiPromptTemplateCodesFromDetail(detail.value);
  }
  const projectVendorMapForm = ref({
    projectId: undefined,
    projectName: '',
    venderNo: '',
  });
  const aiTaskQuery = ref({
    pageNum: 1,
    pageSize: 10,
    status: undefined,
  });

  const aiTerminalStatuses = ['success', 'failed', 'canceled'];

  const data = reactive({
    aiAnalysisRules: {
      versionKey: [],
    },
    projectVendorMapRules: {
      venderNo: [{ required: true, message: '商户编号不能为空', trigger: 'blur' }],
    },
  });

  const { aiAnalysisRules, projectVendorMapRules } = toRefs(data);

  const detailTitle = computed(() => `工单详情：${detail.value.title || ''}`);
  const detailOriginalDescription = computed(() => {
    const originalText = String(
      detail.value.originalDescription ||
        detail.value.extraData?.originDescription ||
        detail.value.extraData?.origin_description ||
        ''
    ).trim();
    if (originalText) {
      return originalText;
    }
    const description = String(detail.value.description || '').trim();
    return description.includes('【AI翻译】')
      ? description.split('【AI翻译】')[0].trim()
      : description;
  });
  const detailAiTranslation = computed(() =>
    String(
      detail.value.aiTranslation ||
        detail.value.extraData?.aiTranslation ||
        detail.value.extraData?.ai_translation ||
        ''
    ).trim()
  );

  /**
   * 解析详情页默认版本号。
   * 优先使用工单自身版本号，其次使用当前项目版本选项中的第一个版本。
   * @returns {string} 默认版本号。
   */
  function resolveDefaultVersionKey() {
    return (
      detail.value.versionKey ||
      detail.value.extraData?.versionKey ||
      detailVersionOptions.value[0]?.value ||
      ''
    );
  }

  const latestSnapshotSummary = computed(
    () =>
      detail.value.latestSnapshot?.summary ||
      detail.value.snapshots?.[0]?.summary ||
      detail.value.rootCause ||
      detail.value.description ||
      ''
  );
  // normalizeWorkflowStatusOptions / getStatusTagType / loadWorkflowConfig 已提取到 hooks/useWorkflow.js

  function formatIssueRelationType(value) {
    const relationType = String(value || '').trim();
    const labelMap = {
      primary: '主问题',
      similar: '相似确认',
      manual: '手工归因',
      duplicate: '重复问题',
      related: '相关问题',
    };
    return labelMap[relationType] || relationType || '-';
  }
  const aiTaskDetailPayload = computed(() => selectedAiTask.value || {});
  const aiPromptLayers = computed(() => detail.value.aiPromptLayers || {});
  const aiPromptHintTitle = computed(() => {
    const projectName =
      aiPromptLayers.value?.project?.projectName || detail.value.projectName || '';
    const moduleName = aiPromptLayers.value?.module?.moduleName || detail.value.moduleName || '';
    const parts = ['AI 分析会自动叠加默认提示词'];
    if (projectName) {
      parts.push(`项目：${projectName}`);
    }
    if (moduleName) {
      parts.push(`模块：${moduleName}`);
    }
    return parts.join('，');
  });
  const aiPromptHintDesc = computed(() => {
    const hasDefaultPrompt = Boolean(aiPromptLayers.value?.hasDefaultPrompt);
    if (!hasDefaultPrompt) {
      return '当前工单未读取到项目/模块默认提示词，仍可填写额外说明来补充本次分析重点。';
    }
    return '项目和模块的默认提示词会自动参与本次分析，额外说明仅用于补充临时背景，不会覆盖系统约束和输出结构。';
  });

  // ticketStatusOptions / statusTransitionOptions 已提取到 hooks/useWorkflow.js

  // 将查询栏中的单值或多选数组统一转成数组，便于后续拼接查询参数。

  // 将多选数组拼成后端约定的逗号分隔查询参数。

  // 构造工单列表查询参数，避免全局 GET 序列化把数组转成 field[0] 形式。

  function syncDetailBundle(payload) {
    detail.value = payload || {};
  }

  /**
   * 解析外部工单详情链接，优先使用同步来源和原始字段。
   * @param {object} ticketRow 工单行或详情数据
   * @returns {string} 可打开的外部工单链接
   */
  function resolveTicketDetailUrl(ticketRow) {
    const row = ticketRow || {};
    const syncSummary = row.syncSummary || row.sync_summary || {};
    const extraData = row.extraData || row.extra_data || {};
    const externalSync = extraData.externalSync || extraData.external_sync || {};
    const source = externalSync.source || {};
    const value = String(
      row.ticketUrl ||
        row.ticket_url ||
        row.url ||
        syncSummary.ticketUrl ||
        syncSummary.ticket_url ||
        syncSummary.sourceRecordUrl ||
        syncSummary.source_record_url ||
        source.ticketUrl ||
        source.ticket_url ||
        source.recordUrl ||
        source.record_url ||
        ''
    ).trim();
    return value || '';
  }

  function refreshDetail() {
    if (!currentTicketId.value) {
      return Promise.resolve();
    }
    return getTicket(currentTicketId.value).then((response) => {
      syncDetailBundle(response.data || {});
      loadDetailVersionOptions(detail.value.projectId);
    });
  }

  /**
   * 子组件完成数据变更后，刷新详情基础信息并通知列表页。
   * @returns {Promise<void>} 刷新与通知完成 Promise。
   */
  function refreshDetailAndNotify() {
    return Promise.all([refreshDetail(), emitChanged()]).then(() => undefined);
  }

  function buildIssueCreateBindForm() {
    return {
      title: detail.value.issueTitle || detail.value.title || '',
      summary:
        detail.value.rootCause || latestSnapshotSummary.value || detail.value.description || '',
      status: 'open',
      severity: detail.value.severity || detail.value.internalPriority || '',
      projectId: detail.value.projectId || undefined,
      projectName: detail.value.projectName || detail.value.merchantName || '',
      moduleId: detail.value.moduleId || undefined,
      moduleName: detail.value.moduleName || '',
      rootCauseType: detail.value.rootCauseType || '',
      problemPatternCode: detail.value.problemPatternCode || '',
      problemPatternName: detail.value.problemPatternName || '',
      ownerId: detail.value.internalOwnerId || detail.value.currentAssigneeId || undefined,
      ownerName: detail.value.internalOwnerName || detail.value.currentAssigneeName || '',
      relationType: 'manual',
      confirmed: true,
    };
  }

  function openIssueCreateBindDialog() {
    if (!detail.value.ticketId) {
      proxy.$modal.msgWarning('请先打开工单详情');
      return;
    }
    issueCreateBindForm.value = buildIssueCreateBindForm();
    issueCreateBindOpen.value = true;
  }

  function submitIssueCreateBind() {
    const titleText = String(issueCreateBindForm.value.title || '').trim();
    if (!titleText) {
      proxy.$modal.msgWarning('问题标题不能为空');
      return;
    }
    issueActionLoading.value = true;
    createAndBindTicketIssue(detail.value.ticketId, {
      ...issueCreateBindForm.value,
      title: titleText,
    })
      .then(() => {
        proxy.$modal.msgSuccess('问题实例已创建并绑定');
        issueCreateBindOpen.value = false;
        return Promise.all([refreshDetail(), emitChanged()]);
      })
      .finally(() => {
        issueActionLoading.value = false;
      });
  }

  function handleUnbindIssue() {
    if (!detail.value.ticketId || !detail.value.issueId) {
      return;
    }
    proxy.$modal
      .confirm(
        `是否确认解除当前工单与问题实例 ${detail.value.issueNo || detail.value.issueId} 的归因？`
      )
      .then(() => {
        issueActionLoading.value = true;
        return unbindTicketIssue(detail.value.ticketId);
      })
      .then(() => {
        proxy.$modal.msgSuccess('归因已解除');
        return Promise.all([refreshDetail(), emitChanged()]);
      })
      .finally(() => {
        issueActionLoading.value = false;
      });
  }

  // createDefaultAiRepoMappingForm / resetAiRepoMappingForm 已提取到 hooks/useAiRepoMapping.js

  function createDefaultProjectVendorMapForm(projectId, projectName) {
    return {
      projectId,
      projectName: projectName || '',
      venderNo: '',
    };
  }

  function resetProjectVendorMapForm() {
    projectVendorMapForm.value = createDefaultProjectVendorMapForm(
      detail.value.projectId,
      detail.value.projectName || detail.value.merchantName || ''
    );
    if (proxy.$refs.projectVendorMapRef) {
      proxy.resetForm('projectVendorMapRef');
    }
  }

  function openProjectVendorMapDialog() {
    if (!detail.value.projectId) {
      proxy.$modal.msgWarning('当前工单缺少项目，无法维护商家映射');
      return;
    }
    projectVendorMapLoading.value = true;
    getTicketLogPullProjectVendorMap(detail.value.projectId)
      .then((response) => {
        const row = response.data || {};
        projectVendorMapForm.value = {
          projectId: row.projectId || detail.value.projectId,
          projectName:
            row.projectName || detail.value.projectName || detail.value.merchantName || '',
          venderNo: row.venderNo || '',
        };
      })
      .catch(() => {
        resetProjectVendorMapForm();
      })
      .finally(() => {
        projectVendorMapLoading.value = false;
        projectVendorMapOpen.value = true;
      });
  }

  function submitProjectVendorMap() {
    proxy.$refs.projectVendorMapRef.validate((valid) => {
      if (!valid) return;
      projectVendorMapSubmitting.value = true;
      const payload = {
        projectId: projectVendorMapForm.value.projectId,
        projectName: projectVendorMapForm.value.projectName,
        venderNo: projectVendorMapForm.value.venderNo,
      };
      saveTicketLogPullProjectVendorMap(payload)
        .then(() => {
          proxy.$modal.msgSuccess('商家映射保存成功');
          projectVendorMapOpen.value = false;
          loadProjectVendorMapOptions();
        })
        .finally(() => {
          projectVendorMapSubmitting.value = false;
        });
    });
  }

  // loadAiRepoMappings 已提取到 hooks/useAiRepoMapping.js

  function loadAiAnalysisTasks(silent = false) {
    if (!currentTicketId.value) {
      return Promise.resolve([]);
    }
    if (!silent) {
      aiTaskLoading.value = true;
    }
    return listTicketAiAnalysisTasks(currentTicketId.value, aiTaskQuery.value)
      .then((response) => {
        aiTaskList.value = response.rows || [];
        aiTaskTotal.value = response.total || 0;
        return aiTaskList.value;
      })
      .finally(() => {
        if (!silent) {
          aiTaskLoading.value = false;
        }
      });
  }

  function refreshAiAnalysisData(refreshTicketList = false) {
    if (!currentTicketId.value) {
      return Promise.resolve();
    }
    aiAnalysisRefreshLoading.value = true;
    const tasks = [refreshDetail(), loadAiAnalysisTasks(true)];
    if (refreshTicketList) {
      tasks.push(emitChanged());
    }
    return Promise.all(tasks).finally(() => {
      aiAnalysisRefreshLoading.value = false;
    });
  }

  function canRetryAiTask(row) {
    return (
      Boolean(row?.taskId) &&
      ['failed', 'canceled'].includes(String(row.status || '').toLowerCase())
    );
  }

  /**
   * 等待指定毫秒数，供 AI 任务短轮询使用。
   * @param {number} ms 等待毫秒数
   * @returns {Promise<void>} 等待完成 Promise
   */
  function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  /**
   * 从接口异常对象中提取可读错误信息，避免页面显示空对象。
   * @param {unknown} error 接口异常、字符串或响应对象
   * @param {string} fallback 无法提取时的兜底文案
   * @returns {string} 可直接提示给用户的错误文案
   */
  function extractReadableError(error, fallback = '操作失败') {
    if (!error) return fallback;
    if (typeof error === 'string') return error;
    if (error instanceof Error && error.message) return error.message;
    if (typeof error === 'object') {
      const candidates = [
        error.message,
        error.msg,
        error.errorMessage,
        error.response?.data?.msg,
        error.response?.data?.message,
        error.response?.data?.detail,
        error.data?.message,
        error.data?.msg,
      ];
      for (const candidate of candidates) {
        const text = extractReadableError(candidate, '');
        if (text) return text;
      }
      try {
        const text = JSON.stringify(error);
        return text && text !== '{}' ? text : fallback;
      } catch (_error) {
        return fallback;
      }
    }
    return String(error);
  }

  /**
   * 从 AI 分析提交接口响应中提取本次提交的任务对象。
   * @param {object} response 提交接口响应
   * @returns {object | null} AI 分析任务对象，未找到时返回 null
   */
  /**
   * 判断是否应该 resume：当前选择的 Provider 和上一次相同且上一次分析成功。
   * @returns {boolean} 是否启用 resume
   */
  function shouldResumeAiAnalysis() {
    const latest = detail.value?.latestAiAnalysis || {};
    const latestContext = latest.analysisContext || {};
    const currentProvider = aiAnalysisTaskForm.value.aiProviderCode;
    const lastProvider = latestContext.selectedAiProviderCode;
    if (!currentProvider || !lastProvider) {
      return false;
    }
    if (currentProvider !== lastProvider) {
      return false;
    }
    return latest.status === 'success' || latest.status === 'SUCCESS';
  }

  function extractSubmittedAiTask(response) {
    const payload = response?.data || response || {};
    const result = payload.result || payload.data?.result || {};
    return result?.taskId ? result : null;
  }

  /**
   * 短轮询指定 AI 分析任务，捕获后台快速失败或成功的终态。
   * @param {number | string} taskId AI 分析任务ID
   * @param {object} options 轮询配置，包含 maxAttempts 和 intervalMs
   * @returns {Promise<object | null>} 命中终态的任务对象，超时返回 null
   */
  async function waitForAiTaskTerminal(taskId, options = {}) {
    const maxAttempts = Number(options.maxAttempts || 6);
    const intervalMs = Number(options.intervalMs || 1500);
    for (let index = 0; index < maxAttempts; index += 1) {
      if (index > 0) {
        await sleep(intervalMs);
      }
      const tasks = await loadAiAnalysisTasks(true);
      const currentTask = (tasks || []).find((item) => String(item.taskId) === String(taskId));
      const status = String(currentTask?.status || '').toLowerCase();
      if (currentTask && aiTerminalStatuses.includes(status)) {
        return currentTask;
      }
    }
    return null;
  }

  /**
   * 提示 AI 分析任务提交结果，并在后台快速失败时展示真实失败原因。
   * @param {object} response 提交或重试接口响应
   * @param {string} successMessage 提交成功提示文案
   * @returns {Promise<void>} 提示完成 Promise
   */
  async function notifyAiTaskSubmitResult(response, successMessage) {
    const submittedTask = extractSubmittedAiTask(response);
    proxy.$modal.msgSuccess(successMessage);
    if (!submittedTask?.taskId) {
      return;
    }
    const terminalTask = await waitForAiTaskTerminal(submittedTask.taskId);
    const status = String(terminalTask?.status || '').toLowerCase();
    if (status === 'failed' || status === 'canceled') {
      const message =
        terminalTask.errorMessage ||
        terminalTask.statusDesc ||
        'AI分析任务执行失败，请查看任务历史';
      proxy.$modal.msgError(message);
      selectedAiTask.value = terminalTask;
    }
  }

  /**
   * 后台短轮询 AI 分析任务终态，不阻塞提交弹窗关闭。
   * @param {object} response 提交或重试接口响应
   * @returns {void}
   */
  function watchAiTaskSubmitResult(response) {
    const submittedTask = extractSubmittedAiTask(response);
    if (!submittedTask?.taskId) {
      return;
    }
    waitForAiTaskTerminal(submittedTask.taskId)
      .then((terminalTask) => {
        const status = String(terminalTask?.status || '').toLowerCase();
        if (status === 'failed' || status === 'canceled') {
          const message =
            terminalTask.errorMessage ||
            terminalTask.statusDesc ||
            'AI分析任务执行失败，请查看任务历史';
          proxy.$modal.msgError(message);
          selectedAiTask.value = terminalTask;
        }
        if (terminalTask) {
          refreshAiAnalysisData(true);
        }
      })
      .catch(() => {
        loadAiAnalysisTasks(true);
      });
  }

  function resetAiAnalysisDialog() {
    const logPullConfig = getTicketAutomationLogPullConfig(detail.value);
    const aiDefaults = buildTicketAiPreferenceDefaults(
      detail.value,
      resolveDefaultAiPromptTemplateCodes()
    );
    aiAnalysisTaskForm.value.versionKey = resolveDefaultVersionKey();
    aiAnalysisTaskForm.value.logPullRecordId = detail.value.latestLogPull?.id || undefined;
    aiAnalysisTaskForm.value.agentCode = aiDefaults.agentCode;
    aiAnalysisTaskForm.value.aiProviderCode = aiDefaults.aiProviderCode;
    if (!aiDefaults.hasManualAgentCode) {
      applyAiAnalysisProviderAgent(aiAnalysisTaskForm.value.aiProviderCode);
    }
    aiAnalysisTaskForm.value.forceRefresh = false;
    aiAnalysisTaskForm.value.logAnalysisMode =
      logPullConfig.logAnalysisMode || logPullConfig.log_analysis_mode || 'hybrid';
    aiAnalysisTaskForm.value.logTimeMode = 'none';
    aiAnalysisTaskForm.value.logWindowMissingStrategy =
      detail.value.latestAiAnalysis?.analysisContext?.logWindowMissingStrategy || 'agent_extract';
    aiAnalysisTaskForm.value.logBeginTime = '';
    aiAnalysisTaskForm.value.logEndTime = '';
    aiAnalysisTaskForm.value.logPointTime = '';
    aiAnalysisTaskForm.value.rangeBeforeMinutes = 5;
    aiAnalysisTaskForm.value.rangeAfterMinutes = 10;
    aiAnalysisTaskForm.value.extraInstruction =
      logPullConfig.extraInstruction || logPullConfig.extra_instruction || '';
    aiAnalysisTaskForm.value.promptTemplateCodes = aiDefaults.promptTemplateCodes;
  }

  function openAiAnalysisDialog() {
    if (!detail.value.projectId) {
      proxy.$modal.msgWarning('当前工单缺少项目，无法发起AI分析');
      return;
    }
    resetAiAnalysisDialog();
    aiAnalysisOpen.value = true;
  }

  function openAiTaskHistory() {
    aiTaskHistoryOpen.value = true;
    loadAiAnalysisTasks();
  }

  function openAiTaskDetail(row) {
    if (!row) {
      return;
    }
    selectedAiTask.value = row;
    aiTaskDetailOpen.value = true;
  }

  function submitAiAnalysis() {
    proxy.$refs.aiAnalysisRef.validate((valid) => {
      if (!valid) return;
      if (
        aiAnalysisTaskForm.value.logTimeMode === 'range' &&
        (!aiAnalysisTaskForm.value.logBeginTime || !aiAnalysisTaskForm.value.logEndTime)
      ) {
        proxy.$modal.msgWarning('请填写日志开始和结束时间');
        return;
      }
      if (
        aiAnalysisTaskForm.value.logTimeMode === 'point' &&
        !aiAnalysisTaskForm.value.logPointTime
      ) {
        proxy.$modal.msgWarning('请选择问题发生时间点');
        return;
      }
      if (
        aiAnalysisTaskForm.value.logTimeMode === 'point' &&
        Number(aiAnalysisTaskForm.value.rangeBeforeMinutes || 0) === 0 &&
        Number(aiAnalysisTaskForm.value.rangeAfterMinutes || 0) === 0
      ) {
        proxy.$modal.msgWarning('时间点前后分钟至少需要一侧大于 0');
        return;
      }
      aiAnalysisSubmitting.value = true;
      const payload = {
        versionKey: aiAnalysisTaskForm.value.versionKey || undefined,
        logPullRecordId: aiAnalysisTaskForm.value.logPullRecordId || undefined,
        agentCode: aiAnalysisTaskForm.value.agentCode || undefined,
        aiProviderCode: aiAnalysisTaskForm.value.aiProviderCode || undefined,
        forceRefresh: aiAnalysisTaskForm.value.forceRefresh,
        logAnalysisMode: aiAnalysisTaskForm.value.logAnalysisMode || 'hybrid',
        extraInstruction: aiAnalysisTaskForm.value.extraInstruction || undefined,
        promptTemplateCodes: aiAnalysisTaskForm.value.promptTemplateCodes?.length
          ? aiAnalysisTaskForm.value.promptTemplateCodes
          : undefined,
        resume: shouldResumeAiAnalysis(),
      };
      if (aiAnalysisTaskForm.value.logTimeMode !== 'none') {
        payload.logWindowMissingStrategy =
          aiAnalysisTaskForm.value.logWindowMissingStrategy || 'agent_extract';
      }
      if (aiAnalysisTaskForm.value.logTimeMode === 'range') {
        payload.logBeginTime = aiAnalysisTaskForm.value.logBeginTime;
        payload.logEndTime = aiAnalysisTaskForm.value.logEndTime;
      }
      if (aiAnalysisTaskForm.value.logTimeMode === 'point') {
        payload.logPointTime = aiAnalysisTaskForm.value.logPointTime;
        payload.rangeBeforeMinutes = aiAnalysisTaskForm.value.rangeBeforeMinutes;
        payload.rangeAfterMinutes = aiAnalysisTaskForm.value.rangeAfterMinutes;
      }
      addTicketAiAnalysis(currentTicketId.value, payload)
        .then((response) => {
          proxy.$modal.msgSuccess('AI分析任务已提交');
          aiAnalysisOpen.value = false;
          refreshAiAnalysisData(true);
          watchAiTaskSubmitResult(response);
        })
        .catch((error) => {
          proxy.$modal.msgError(extractReadableError(error, 'AI分析任务提交失败'));
        })
        .finally(() => {
          aiAnalysisSubmitting.value = false;
        });
    });
  }

  function retryAiAnalysisTask(row) {
    if (!row?.taskId) {
      return;
    }
    proxy.$modal
      .confirm(`是否确认重试 AI 分析任务 #${row.taskId}？`)
      .then(() => {
        aiAnalysisRetryLoading.value = true;
        return retryTicketAiAnalysis(currentTicketId.value, row.taskId);
      })
      .then(async (response) => {
        await notifyAiTaskSubmitResult(response, 'AI分析任务已重新提交');
        return Promise.all([loadAiAnalysisTasks(true), refreshDetail(), emitChanged()]);
      })
      .catch((error) => {
        if (error !== 'cancel' && error !== 'close') {
          proxy.$modal.msgError(extractReadableError(error, 'AI分析任务重试失败'));
        }
      })
      .finally(() => {
        aiAnalysisRetryLoading.value = false;
      });
  }

  function openDetail(row) {
    const ticketId = Number(row?.ticketId || row?.ticket_id || row);
    if (!Number.isFinite(ticketId) || ticketId <= 0) {
      proxy.$modal.msgWarning('工单ID无效，无法打开详情');
      return Promise.resolve();
    }
    currentTicketId.value = ticketId;
    detailOpen.value = true;
    detailMainTab.value = 'overview';
    descriptionExpanded.value = true;
    translationExpanded.value = false;
    detailMoreInfoExpanded.value = false;
    aiTaskHistoryOpen.value = false;
    aiTaskDetailOpen.value = false;
    aiTaskList.value = [];
    aiTaskTotal.value = 0;
    selectedAiTask.value = null;
    aiRepoMappingList.value = [];
    aiRepoMappingTotal.value = 0;
    return getTicket(ticketId).then((response) => {
      syncDetailBundle(response.data || {});
      return loadDetailVersionOptions(detail.value.projectId)
        .catch(() => {
          detailVersionOptions.value = [];
        })
        .then(() => {
          aiAnalysisTaskForm.value.mappingId =
            detail.value.latestAiAnalysis?.mappingId || aiAnalysisTaskForm.value.mappingId;
        });
    });
  }

  function handleTranslateDescription() {
    if (!detail.value.ticketId || descriptionTranslateLoading.value) {
      return;
    }
    if (!detailOriginalDescription.value) {
      proxy.$modal.msgWarning('当前工单描述为空，无法翻译');
      return;
    }
    descriptionTranslateLoading.value = true;
    translateTicketDescription(detail.value.ticketId)
      .then((response) => {
        syncDetailBundle(response.data || detail.value);
        proxy.$modal.msgSuccess(response.msg || '翻译成功');
        emitChanged();
      })
      .finally(() => {
        descriptionTranslateLoading.value = false;
      });
  }

  function resetDetailDialog() {
    detailMainTab.value = 'overview';
    descriptionExpanded.value = true;
    translationExpanded.value = false;
    detailMoreInfoExpanded.value = false;
    detail.value = {};
    detailVersionOptions.value = [];
    aiTaskHistoryOpen.value = false;
    aiTaskDetailOpen.value = false;
    selectedAiTask.value = null;
    aiAnalysisOpen.value = false;
    aiRepoMappingOpen.value = false;
    projectVendorMapOpen.value = false;
  }

  function formatJson(value) {
    return JSON.stringify(value, null, 2);
  }

  function getAiStatusTagType(value) {
    const status = String(value || '');
    if (status === 'success') return 'success';
    if (status === 'failed') return 'danger';
    if (status === 'running') return 'warning';
    if (status === 'created') return 'info';
    return 'info';
  }

  function getAiStatusLabel(value) {
    const status = String(value || '');
    if (status === 'success') return '成功';
    if (status === 'failed') return '失败';
    if (status === 'running') return '执行中';
    if (status === 'created') return '待执行';
    return status || '-';
  }

  function formatSeconds(seconds) {
    if (!seconds) return '-';
    const hour = Math.floor(seconds / 3600);
    const minute = Math.floor((seconds % 3600) / 60);
    const second = seconds % 60;
    return `${hour}小时${minute}分${second}秒`;
  }

  /**
   * 关闭详情弹窗后清理组件内部状态，并通知父组件执行独立路由收尾。
   * @returns {void}
   */
  function handleDetailClosed() {
    resetDetailDialog();
    emit('closed');
  }

  watch(
    () => [props.open, props.ticketId],
    ([openValue, ticketId]) => {
      const resolvedTicketId = Number(ticketId);
      if (!openValue || !Number.isFinite(resolvedTicketId) || resolvedTicketId <= 0) {
        return;
      }
      if (resolvedTicketId === currentTicketId.value && detail.value.ticketId) {
        return;
      }
      openDetail({ ticketId: resolvedTicketId });
    },
    { immediate: true }
  );

  loadProjectOptions();
  loadProjectVendorMapOptions();
  loadAgentOptions();
  loadProviderOptions();
  loadAnalysisPromptOptions();
  loadWorkflowConfig();
</script>
<template>
  <el-dialog
    v-model="detailOpen"
    fullscreen
    class="ticket-detail-dialog"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    @closed="handleDetailClosed"
  >
    <template #header>
      <div class="ticket-detail-dialog__header">
        <span class="ticket-detail-dialog__title">{{ detailTitle }}</span>
        <el-button link type="primary" @click="detailMoreInfoExpanded = !detailMoreInfoExpanded">
          {{ detailMoreInfoExpanded ? '收起更多信息' : '展开更多信息' }}
        </el-button>
      </div>
    </template>
    <template v-if="detail.ticketId">
      <div class="ticket-detail-scroll">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="编号">{{ detail.ticketNo }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusTagType(detail.status)">
              {{ getOptionLabel(ticketStatusOptions, detail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="当前处理人">{{
            detail.currentAssigneeName || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="所属项目">{{
            detail.projectName || detail.merchantName || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="所属模块">{{
            detail.moduleName || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="外部链接">
            <el-link
              v-if="resolveTicketDetailUrl(detail)"
              :href="resolveTicketDetailUrl(detail)"
              target="_blank"
              type="primary"
            >
              打开详情
            </el-link>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="工单类型">{{
            formatIssueType(detail)
          }}</el-descriptions-item>
          <el-descriptions-item label="根因分类">{{
            formatStatOption(rootCauseTypeOptions, detail.rootCauseType)
          }}</el-descriptions-item>
          <el-descriptions-item label="内部优先级">{{
            detail.internalPriority || '-'
          }}</el-descriptions-item>
          <template v-if="detailMoreInfoExpanded">
            <el-descriptions-item label="1线人员">{{
              detail.firstLineAssigneeName || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="内部负责人">{{
              detail.internalOwnerName || '-'
            }}</el-descriptions-item>

            <el-descriptions-item label="问题性质">{{
              formatProblemFlag(detail.isProblem)
            }}</el-descriptions-item>
            <el-descriptions-item label="解决方式">{{
              formatStatOption(solutionTypeOptions, detail.solutionType)
            }}</el-descriptions-item>
            <el-descriptions-item label="关闭结果">{{
              formatResolution(detail)
            }}</el-descriptions-item>
            <el-descriptions-item label="细分问题">{{
              formatProblemPattern(detail)
            }}</el-descriptions-item>
            <el-descriptions-item label="细分确认">
              <el-tag v-if="detail.problemPatternVerified === true" type="success">已确认</el-tag>
              <el-tag v-else-if="detail.problemPatternVerified === false" type="warning"
                >待确认</el-tag
              >
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="所属问题">
              <template v-if="detail.issueId">
                <div class="issue-summary-inline">
                  <el-tag type="primary">{{ detail.issueNo || detail.issueId }}</el-tag>
                  <span>{{ detail.issueTitle || '-' }}</span>
                </div>
              </template>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="归因确认">
              <el-tag v-if="detail.issueId && detail.issueConfirmed" type="success">已确认</el-tag>
              <el-tag v-else-if="detail.issueId" type="warning">待确认</el-tag>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="归因类型">{{
              formatIssueRelationType(detail.issueRelationType)
            }}</el-descriptions-item>
            <el-descriptions-item label="版本号">{{
              detail.versionKey || detail.extraData?.versionKey || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="日志拉取状态">
              <el-tag
                v-if="detail.latestLogPull?.status"
                :type="getLogPullStatusTagType(detail.latestLogPull.status)"
              >
                {{
                  detail.latestLogPull.statusDesc ||
                  getOptionLabel(logPullStatusOptions, detail.latestLogPull.status)
                }}
              </el-tag>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="来源">{{
              getOptionLabel(sourceOptions, detail.source)
            }}</el-descriptions-item>
            <el-descriptions-item label="对方优先级">{{
              detail.customerPriority || '-'
            }}</el-descriptions-item>

            <el-descriptions-item label="总耗时">{{
              formatSeconds(detail.totalProcessSeconds)
            }}</el-descriptions-item>
            <el-descriptions-item label="根因" :span="3">{{
              detail.rootCause || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="解决方案" :span="3">{{
              detail.solution || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="问题实例操作" :span="3">
              <el-button
                v-if="!detail.issueId"
                link
                type="primary"
                @click="openIssueCreateBindDialog"
                v-hasPermi="['ticket:issue:add']"
              >
                新建问题实例并绑定
              </el-button>
              <el-button
                v-if="detail.issueId"
                link
                type="danger"
                @click="handleUnbindIssue"
                v-hasPermi="['ticket:issue:remove']"
              >
                解除归因
              </el-button>
            </el-descriptions-item>
          </template>
        </el-descriptions>
        <div class="ticket-detail-description">
          <div class="ticket-detail-description__label">
            <span>描述</span>
            <div class="ticket-detail-description__actions">
              <el-button
                link
                type="primary"
                :loading="descriptionTranslateLoading"
                @click="handleTranslateDescription"
                v-hasPermi="['ticket:ticket:edit']"
              >
                翻译
              </el-button>
              <el-button link type="primary" @click="descriptionExpanded = !descriptionExpanded">
                {{ descriptionExpanded ? '收起' : '展开' }}
              </el-button>
            </div>
          </div>
          <div
            :class="[
              'ticket-detail-description__content',
              { 'ticket-detail-description__content--collapsed': !descriptionExpanded },
            ]"
          >
            {{ detailOriginalDescription || '-' }}
          </div>
        </div>
        <div v-if="detailAiTranslation" class="ticket-detail-description ticket-detail-translation">
          <div class="ticket-detail-description__label">
            <span>翻译</span>
            <el-button link type="primary" @click="translationExpanded = !translationExpanded">
              {{ translationExpanded ? '收起' : '展开' }}
            </el-button>
          </div>
          <div
            :class="[
              'ticket-detail-description__content',
              { 'ticket-detail-description__content--collapsed': !translationExpanded },
            ]"
          >
            {{ detailAiTranslation }}
          </div>
        </div>

        <el-tabs v-model="detailMainTab" class="detail-main-tabs">
          <el-tab-pane label="概览" name="overview" lazy>
            <TicketDetailOverviewTab
              :ticket-id="currentTicketId"
              :active="detailMainTab === 'overview'"
              :detail="detail"
              @run-ai="openAiAnalysisDialog"
              @refresh-ai="refreshAiAnalysisData"
              @open-ai-history="openAiTaskHistory"
              @open-ai-repo-mapping="openAiRepoMappingDialog"
              @open-project-vendor-map="openProjectVendorMapDialog"
              @changed="refreshDetailAndNotify"
            />
          </el-tab-pane>

          <el-tab-pane label="日志拉取" name="logPull" lazy>
            <TicketDetailLogPullTab
              :ticket-id="currentTicketId"
              :active="detailMainTab === 'logPull'"
              :detail="detail"
              @changed="refreshDetailAndNotify"
            />
          </el-tab-pane>

          <el-tab-pane label="协同/AI" name="collab" lazy>
            <TicketDetailCollabTab
              :ticket-id="currentTicketId"
              :active="detailMainTab === 'collab'"
              :detail="detail"
              @changed="refreshDetailAndNotify"
              @run-ai="openAiAnalysisDialog"
              @open-ai-history="openAiTaskHistory"
            />
          </el-tab-pane>

          <el-tab-pane label="评论" name="comments" lazy>
            <TicketDetailCommentsTab
              :ticket-id="currentTicketId"
              :active="detailMainTab === 'comments'"
              @changed="refreshDetailAndNotify"
            />
          </el-tab-pane>

          <el-tab-pane label="历史" name="history" lazy>
            <TicketDetailHistoryTab
              :ticket-id="currentTicketId"
              :active="detailMainTab === 'history'"
              @changed="refreshDetailAndNotify"
            />
          </el-tab-pane>
        </el-tabs>
      </div>
    </template>
  </el-dialog>

  <el-dialog
    v-model="aiAnalysisOpen"
    title="发起AI分析"
    width="620px"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    @closed="resetAiAnalysisDialog"
  >
    <el-form
      ref="aiAnalysisRef"
      :model="aiAnalysisTaskForm"
      :rules="aiAnalysisRules"
      label-width="110px"
    >
      <el-form-item label="版本号" prop="versionKey">
        <el-select
          v-model="aiAnalysisTaskForm.versionKey"
          placeholder="请选择或输入版本号，系统将按工单所属项目 + 版本号自动匹配仓库映射"
          filterable
          clearable
          allow-create
          default-first-option
          style="width: 100%"
        >
          <el-option
            v-for="item in detailVersionOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="Agent">
        <el-select
          v-model="aiAnalysisTaskForm.agentCode"
          placeholder="可选，优先使用指定Agent"
          filterable
          clearable
          style="width: 100%"
          @change="handleAiAnalysisAgentChange"
        >
          <el-option
            v-for="item in agentOptions"
            :key="item.agentCode"
            :label="`${item.agentName || item.agentCode} [${item.agentCode}]`"
            :value="item.agentCode"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="Provider">
        <el-select
          v-model="aiAnalysisTaskForm.aiProviderCode"
          placeholder="可选，优先使用指定Provider"
          filterable
          clearable
          style="width: 100%"
          @change="handleAiAnalysisProviderChange"
        >
          <el-option
            v-for="item in providerOptions"
            :key="item.providerCode"
            :label="`${item.providerName || item.providerCode} [${item.providerCode}] ${item.modelName ? `- ${item.modelName}` : ''}`"
            :value="item.providerCode"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="强制刷新">
        <el-switch v-model="aiAnalysisTaskForm.forceRefresh" />
      </el-form-item>
      <el-form-item label="日志模式">
        <el-select
          v-model="aiAnalysisTaskForm.logAnalysisMode"
          placeholder="请选择日志分析模式"
          style="width: 100%"
        >
          <el-option label="生成摘要" value="digest" />
          <el-option label="完整目录" value="full_directory" />
          <el-option label="摘要 + 完整目录" value="hybrid" />
        </el-select>
      </el-form-item>
      <el-form-item label="日志时间">
        <el-radio-group v-model="aiAnalysisTaskForm.logTimeMode">
          <el-radio-button label="none">不指定</el-radio-button>
          <el-radio-button label="range">开始/结束</el-radio-button>
          <el-radio-button label="point">时间点前后</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <template v-if="aiAnalysisTaskForm.logTimeMode === 'range'">
        <el-form-item label="开始时间">
          <el-date-picker
            v-model="aiAnalysisTaskForm.logBeginTime"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择日志开始时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-date-picker
            v-model="aiAnalysisTaskForm.logEndTime"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择日志结束时间"
            style="width: 100%"
          />
        </el-form-item>
      </template>
      <template v-if="aiAnalysisTaskForm.logTimeMode === 'point'">
        <el-form-item label="问题时间点">
          <el-date-picker
            v-model="aiAnalysisTaskForm.logPointTime"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择问题发生时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="前后分钟">
          <div class="inline-inputs">
            <el-input-number v-model="aiAnalysisTaskForm.rangeBeforeMinutes" :min="0" :step="1" />
            <span class="inline-separator">前</span>
            <el-input-number v-model="aiAnalysisTaskForm.rangeAfterMinutes" :min="0" :step="1" />
            <span class="inline-separator">后</span>
          </div>
        </el-form-item>
      </template>
      <el-form-item v-if="aiAnalysisTaskForm.logTimeMode !== 'none'" label="缺失策略">
        <el-select
          v-model="aiAnalysisTaskForm.logWindowMissingStrategy"
          placeholder="数据库没有截取正文时怎么处理"
          style="width: 100%"
        >
          <el-option label="Agent 本地截取" value="agent_extract" />
          <el-option label="服务端实时截取" value="server_extract" />
        </el-select>
      </el-form-item>
      <el-form-item label="额外说明">
        <el-input
          v-model="aiAnalysisTaskForm.extraInstruction"
          type="textarea"
          :rows="4"
          maxlength="2000"
          show-word-limit
          placeholder="可填写本次分析的额外重点，例如优先排查的链路、已知异常现象、需要忽略的噪声等"
        />
      </el-form-item>
      <el-form-item label="追加提示词">
        <el-select
          v-model="aiAnalysisTaskForm.promptTemplateCodes"
          placeholder="可选，选择后会追加到当前分析提示词中"
          multiple
          filterable
          clearable
          style="width: 100%"
          @change="handleAiAnalysisPromptTemplateChange"
        >
          <el-option
            v-for="item in analysisPromptOptions"
            :key="item.templateCode"
            :label="`${item.templateName || item.templateCode} [${item.templateCode}]`"
            :value="item.templateCode"
          />
        </el-select>
      </el-form-item>
      <el-alert :title="aiPromptHintTitle" :description="aiPromptHintDesc" type="info" show-icon />
    </el-form>
    <template #footer>
      <el-button @click="aiAnalysisOpen = false">取消</el-button>
      <el-button
        type="primary"
        :loading="aiAnalysisSubmitting"
        @click="submitAiAnalysis"
        v-hasPermi="['ticket:ai:analysis:run']"
      >
        提交分析
      </el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="aiTaskHistoryOpen"
    title="AI任务历史"
    width="1100px"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
  >
    <div class="panel-header mb16">
      <div class="panel-inline">
        <span>任务列表</span>
        <el-tag v-if="aiTaskTotal">{{ aiTaskTotal }} 条</el-tag>
      </div>
      <el-button link type="primary" @click="loadAiAnalysisTasks" :loading="aiTaskLoading"
        >刷新</el-button
      >
    </div>
    <el-table v-loading="aiTaskLoading" :data="aiTaskList" row-key="taskId">
      <el-table-column label="提交时间" prop="createTime" width="170">
        <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110" align="center">
        <template #default="scope">
          <el-tag :type="getAiStatusTagType(scope.row.status)">{{
            getAiStatusLabel(scope.row.status)
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="版本" prop="versionKey" width="120" show-overflow-tooltip />
      <el-table-column label="提交人" prop="submittedByName" width="120" show-overflow-tooltip />
      <el-table-column label="完成时间" prop="finishedAt" width="170">
        <template #default="scope">{{ parseTime(scope.row.finishedAt) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" align="center" fixed="right">
        <template #default="scope">
          <el-button link type="primary" @click="openAiTaskDetail(scope.row)">查看原文</el-button>
          <el-button
            v-if="canRetryAiTask(scope.row)"
            link
            type="warning"
            :loading="aiAnalysisRetryLoading"
            @click="retryAiAnalysisTask(scope.row)"
            v-hasPermi="['ticket:ai:analysis:run']"
          >
            重试
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <pagination
      v-show="aiTaskTotal > 0"
      :total="aiTaskTotal"
      v-model:page="aiTaskQuery.pageNum"
      v-model:limit="aiTaskQuery.pageSize"
      @pagination="loadAiAnalysisTasks"
    />
    <template #footer>
      <el-button @click="aiTaskHistoryOpen = false">关闭</el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="aiTaskDetailOpen"
    title="AI任务原文"
    width="980px"
    top="4vh"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
  >
    <el-descriptions :column="2" border class="mb16">
      <el-descriptions-item label="任务ID">{{
        aiTaskDetailPayload.taskId || '-'
      }}</el-descriptions-item>
      <el-descriptions-item label="状态">
        <el-tag
          v-if="aiTaskDetailPayload.status"
          :type="getAiStatusTagType(aiTaskDetailPayload.status)"
        >
          {{ getAiStatusLabel(aiTaskDetailPayload.status) }}
        </el-tag>
        <span v-else>-</span>
      </el-descriptions-item>
      <el-descriptions-item label="版本">{{
        aiTaskDetailPayload.versionKey || '-'
      }}</el-descriptions-item>
      <el-descriptions-item label="Agent">{{
        aiTaskDetailPayload.agentCode || '-'
      }}</el-descriptions-item>
      <el-descriptions-item label="提交时间">{{
        parseTime(aiTaskDetailPayload.createTime) || '-'
      }}</el-descriptions-item>
      <el-descriptions-item label="完成时间">{{
        parseTime(aiTaskDetailPayload.finishedAt || aiTaskDetailPayload.updateTime) || '-'
      }}</el-descriptions-item>
      <el-descriptions-item label="仓库地址" :span="2">{{
        aiTaskDetailPayload.repoUrl || '-'
      }}</el-descriptions-item>
      <el-descriptions-item label="分支名称" :span="2">{{
        aiTaskDetailPayload.branchName || '-'
      }}</el-descriptions-item>
    </el-descriptions>
    <el-alert
      v-if="aiTaskDetailPayload.errorMessage"
      type="error"
      show-icon
      :title="aiTaskDetailPayload.errorMessage"
      class="mb16"
    />
    <el-tabs class="task-detail-tabs">
      <el-tab-pane label="提示词">
        <pre class="json-block task-detail-block">{{ aiTaskDetailPayload.promptText || '-' }}</pre>
      </el-tab-pane>
      <el-tab-pane label="原始输出">
        <pre class="json-block task-detail-block">{{ aiTaskDetailPayload.rawOutput || '-' }}</pre>
      </el-tab-pane>
      <el-tab-pane label="分析结果">
        <pre class="json-block task-detail-block">{{
          aiTaskDetailPayload.analysisResult ? formatJson(aiTaskDetailPayload.analysisResult) : '-'
        }}</pre>
      </el-tab-pane>
      <el-tab-pane label="上下文">
        <pre class="json-block task-detail-block">{{
          aiTaskDetailPayload.analysisContext
            ? formatJson(aiTaskDetailPayload.analysisContext)
            : '-'
        }}</pre>
      </el-tab-pane>
    </el-tabs>
    <template #footer>
      <el-button @click="aiTaskDetailOpen = false">关闭</el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="aiRepoMappingOpen"
    title="仓库映射"
    width="760px"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    @closed="resetAiRepoMappingForm"
  >
    <el-form
      ref="aiRepoMappingRef"
      :model="aiRepoMappingForm"
      :rules="aiRepoMappingRules"
      label-width="110px"
    >
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="项目" prop="projectId">
            <el-select
              v-model="aiRepoMappingForm.projectId"
              placeholder="请选择项目"
              filterable
              style="width: 100%"
            >
              <el-option
                v-for="item in projectOptions"
                :key="item.projectId"
                :label="item.projectName"
                :value="item.projectId"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="版本标识" prop="versionKey">
            <el-input v-model="aiRepoMappingForm.versionKey" placeholder="例如 release/2.1.3" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="仓库地址" prop="repoUrl">
            <el-input
              v-model="aiRepoMappingForm.repoUrl"
              placeholder="git@gitlab.xxx/project.git"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="分支名称" prop="branchName">
            <el-input v-model="aiRepoMappingForm.branchName" placeholder="release/2.1.3" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="本地仓库" prop="localRepoPath">
            <el-input
              v-model="aiRepoMappingForm.localRepoPath"
              placeholder="留空则使用 Agent 本地配置"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="工作区根目录">
            <el-input
              v-model="aiRepoMappingForm.workspaceRoot"
              placeholder="留空则使用 Agent 本地配置"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="Worker命令">
            <el-input
              v-model="aiRepoMappingForm.workerCommand"
              placeholder="留空则使用系统默认 codex exec"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="默认映射">
            <el-switch v-model="aiRepoMappingForm.isDefault" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="启用状态">
            <el-switch v-model="aiRepoMappingForm.enabled" />
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="备注">
            <el-input v-model="aiRepoMappingForm.remark" type="textarea" :rows="3" />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>
    <template #footer>
      <el-button @click="aiRepoMappingOpen = false">取消</el-button>
      <el-button type="primary" :loading="aiRepoMappingSubmitting" @click="submitAiRepoMapping">
        保存
      </el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="projectVendorMapOpen"
    title="商家映射"
    width="520px"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    @closed="resetProjectVendorMapForm"
  >
    <div v-loading="projectVendorMapLoading">
      <el-form
        ref="projectVendorMapRef"
        :model="projectVendorMapForm"
        :rules="projectVendorMapRules"
        label-width="110px"
      >
        <el-form-item label="项目">
          <el-select
            v-model="projectVendorMapForm.projectId"
            placeholder="项目"
            filterable
            style="width: 100%"
            disabled
          >
            <el-option
              v-for="item in projectOptions"
              :key="item.projectId"
              :label="item.projectName"
              :value="item.projectId"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="项目名称">
          <el-input v-model="projectVendorMapForm.projectName" disabled />
        </el-form-item>
        <el-form-item label="商户编号" prop="venderNo">
          <el-input
            v-model="projectVendorMapForm.venderNo"
            placeholder="请输入 vender_no"
            maxlength="30"
          />
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="projectVendorMapOpen = false">取消</el-button>
      <el-button
        type="primary"
        :loading="projectVendorMapSubmitting"
        @click="submitProjectVendorMap"
        >保存</el-button
      >
    </template>
  </el-dialog>

  <el-dialog
    v-model="issueCreateBindOpen"
    title="新建问题实例并绑定"
    width="720px"
    append-to-body
    destroy-on-close
  >
    <el-form :model="issueCreateBindForm" label-width="110px">
      <el-form-item label="问题标题" required>
        <el-input v-model="issueCreateBindForm.title" maxlength="500" show-word-limit />
      </el-form-item>
      <el-form-item label="问题摘要">
        <el-input v-model="issueCreateBindForm.summary" type="textarea" :rows="4" />
      </el-form-item>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="状态">
            <el-select v-model="issueCreateBindForm.status" style="width: 100%">
              <el-option label="待处理" value="open" />
              <el-option label="处理中" value="processing" />
              <el-option label="已解决" value="resolved" />
              <el-option label="已关闭" value="closed" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="严重等级">
            <el-select v-model="issueCreateBindForm.severity" clearable style="width: 100%">
              <el-option
                v-for="item in severityOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="项目">{{ issueCreateBindForm.projectName || '-' }}</el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="模块">{{ issueCreateBindForm.moduleName || '-' }}</el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="根因分类">
            <el-select v-model="issueCreateBindForm.rootCauseType" clearable style="width: 100%">
              <el-option
                v-for="item in rootCauseTypeOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="负责人">{{ issueCreateBindForm.ownerName || '-' }}</el-form-item>
        </el-col>
      </el-row>
    </el-form>
    <template #footer>
      <el-button @click="issueCreateBindOpen = false">取消</el-button>
      <el-button type="primary" :loading="issueActionLoading" @click="submitIssueCreateBind">
        确认创建并绑定
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped lang="scss">
  :deep(.ticket-detail-dialog .el-dialog) {
    display: flex;
    flex-direction: column;
    height: 100vh;
    margin: 0;
  }

  :deep(.ticket-detail-dialog .el-dialog__header) {
    flex: 0 0 auto;
  }

  .ticket-detail-dialog__header {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }

  .ticket-detail-dialog__title {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 700;
  }

  :deep(.ticket-detail-dialog .el-dialog__body) {
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
    padding-top: 8px;
    padding-bottom: 12px;
  }

  .ticket-detail-scroll {
    height: 100%;
    overflow: auto;
    padding-right: 4px;
  }

  .ticket-detail-description {
    display: grid;
    grid-template-columns: 112px minmax(0, 1fr);
    border: 1px solid var(--el-border-color-lighter);
    border-top: 0;
    font-size: 14px;
    line-height: 1.5;
  }

  .ticket-detail-description__label {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    justify-content: space-between;
    padding: 8px 11px;
    color: var(--el-text-color-regular);
    background: var(--el-fill-color-light);
    border-right: 1px solid var(--el-border-color-lighter);
    font-weight: 700;
    white-space: nowrap;
  }

  .ticket-detail-description__actions {
    display: flex;
    flex-direction: column;
    gap: 2px;
    align-items: flex-end;
    line-height: 1.2;
  }

  .ticket-detail-description__actions :deep(.el-button + .el-button) {
    margin-left: 0;
  }

  .ticket-detail-description__content {
    min-width: 0;
    padding: 8px 11px;
    color: var(--el-text-color-primary);
    white-space: pre-wrap;
    word-break: break-word;
  }

  .ticket-detail-description__content--collapsed {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  :deep(.detail-main-tabs) {
    height: auto;
  }

  .detail-main-tabs :deep(.el-tabs__header) {
    margin-bottom: 16px;
  }

  .mt16 {
    margin-top: 16px;
  }

  .mb16 {
    margin-bottom: 16px;
  }

  .mb12 {
    margin-bottom: 12px;
  }

  .mb8 {
    margin-bottom: 8px;
  }

  .ml12 {
    margin-left: 12px;
  }

  .mt12 {
    margin-top: 12px;
  }

  .mr8 {
    margin-right: 8px;
  }

  .import-result {
    margin-top: 16px;
  }

  .version-statistics-toolbar {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 12px;
  }

  .result-title {
    margin-bottom: 8px;
    color: #606266;
    font-weight: 600;
  }

  .json-block {
    padding: 10px;
    margin: 10px 0 0;
    overflow: auto;
    background: #f6f8fa;
    border-radius: 4px;
  }

  .issue-summary-inline {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .issue-summary-inline span:last-child {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .panel-header {
    display: flex;
    justify-content: start;
    gap: 12px;
  }

  .log-view-controls {
    flex-wrap: wrap;
    align-items: center;
  }

  .ticket-page :deep(.ticket-log-viewer-dialog .el-dialog__body) {
    height: calc(100vh - 56px);
    overflow: hidden;
  }

  .log-viewer-content {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }

  .log-keyword-input {
    width: min(460px, 100%);
  }

  .log-highlight-input {
    width: min(360px, 100%);
  }

  .log-context-lines-input {
    width: 120px;
  }

  .log-highlight-summary-tag {
    max-width: min(280px, 32vw);
    min-width: 0;
  }

  .log-highlight-summary {
    display: inline-block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    vertical-align: bottom;
    white-space: nowrap;
  }

  .log-view-time-picker {
    width: 220px;
  }

  .log-file-scope-select {
    width: min(360px, 100%);
  }

  .panel-inline {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: nowrap;
  }

  .inline-inputs {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
  }

  .inline-inputs :deep(.el-input-number) {
    flex: 1;
    min-width: 0;
  }

  .inline-separator {
    color: #606266;
    white-space: nowrap;
  }

  .log-view-panel {
    display: flex;
    flex: 0 0 auto;
    flex-direction: column;
    min-height: 0;
    padding: 10px;
    border: 1px solid #dcdfe6;
    border-radius: 6px;
    background: #ffffff;
  }

  .log-view-panel-header {
    align-items: center;
    flex-wrap: wrap;
    justify-content: space-between;
  }

  .log-view-panel-header > span {
    min-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .log-view-panel-fullscreen {
    position: fixed;
    inset: 16px;
    z-index: 3000;
    display: flex;
    flex-direction: column;
    padding: 14px;
    overflow: hidden;
    box-shadow: 0 8px 24px rgb(0 0 0 / 18%);
  }

  .log-view-panel-fullscreen :deep(.el-table) {
    flex: 1;
  }

  .log-view-panel-fullscreen .log-content-block {
    flex: 1;
    max-height: none;
  }

  .log-view-panel-minimized {
    flex: 0 0 auto;
    padding-bottom: 6px;
  }

  .log-view-panel-fill {
    flex: 1 1 auto;
    min-height: 0;
  }

  .log-view-panel-fill :deep(.el-table) {
    flex: 1 1 auto;
    min-height: 0;
  }

  .log-view-panel-fill .log-content-block {
    flex: 1 1 auto;
    max-height: none;
  }

  .history-entry-tabs :deep(.el-tabs__header) {
    margin-bottom: 16px;
  }

  .task-detail-tabs :deep(.el-tabs__header) {
    margin-bottom: 12px;
  }

  .task-detail-block {
    max-height: 46vh;
  }

  .time-range-inline {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }

  .log-filter-input {
    max-width: 360px;
  }

  .log-content-block {
    max-height: 52vh;
    padding: 12px;
    margin: 0;
    overflow: auto;
    white-space: pre;
    word-break: normal;
    background: #0f172a;
    color: #e2e8f0;
    border-radius: 6px;
    font-size: 12px;
    line-height: 1.55;
  }

  .log-content-wrap {
    white-space: pre-wrap;
    word-break: break-word;
  }

  .log-context-line {
    display: block;
  }

  .log-context-line-no {
    color: #94a3b8;
    user-select: none;
  }

  .log-context-line-content {
    white-space: inherit;
  }

  :global(::highlight(ticket-log-context-highlight)) {
    color: #111827;
    background: #fde047;
  }

  .log-context-highlight {
    padding: 0 1px;
    color: #111827;
    background: #fde047;
    border-radius: 2px;
  }

  .log-context-highlight-1 {
    background: #bfdbfe;
  }

  .log-context-highlight-2 {
    background: #bbf7d0;
  }

  .log-context-highlight-3 {
    background: #fecaca;
  }

  .log-context-highlight-4 {
    background: #ddd6fe;
  }

  .log-context-highlight-5 {
    background: #fed7aa;
  }

  .log-content-dialog {
    max-height: 60vh;
  }

  .log-pull-record-table :deep(.el-scrollbar__bar.is-horizontal) {
    height: 12px;
  }

  .log-pull-record-table :deep(.el-scrollbar__bar.is-horizontal .el-scrollbar__thumb) {
    min-width: 48px;
  }
</style>
