/**
 * 工单选项加载 composable。
 *
 * 从 index.vue 提取所有选项加载和格式化函数（~30 个函数）。
 * 包括：项目/模块/版本/商家/Provider/Agent/Prompt/Push 选项加载，
 * 以及工单类型/状态/根因/解决方式等格式化辅助函数。
 */
import { ref } from 'vue';
import { listAiProviderOptions } from '@/api/system/aiprovider';
import { listAiPromptTemplateOptions } from '@/api/system/aiprompt';
import { all as listAllAgents } from '@/api/hrm/agent';
import { allPushConfig as listAllPushConfig } from '@/api/hrm/push';
import {
  getTicketLogPullVendorStoreOptions,
  listTicketLogPullProjectVendorMapOptions,
  getTicketStatClassificationOptions,
  listTicketAiRepoMappings,
  listTicketProjectOptions,
  listTicketModuleOptions,
} from '@/api/ticket/ticket';
// 分类选项从 API 动态加载（loadStatClassificationOptions），不使用静态枚举

export function useOptions() {
  // === 选项数据 refs ===
  const projectOptions = ref([]);
  const projectVendorMapOptions = ref([]);
  const formModuleOptions = ref([]);
  const formVersionOptions = ref([]);
  const queryModuleOptions = ref([]);
  const queryModuleCodeOptions = ref([]);
  const issueTypeOptions = ref([]);
  const rootCauseTypeOptions = ref([]);
  const solutionTypeOptions = ref([]);
  const resolutionOptions = ref([]);
  const problemPatternOptions = ref([]);
  const agentOptions = ref([]);
  const providerOptions = ref([]);
  const analysisPromptOptions = ref([]);
  const vendorOptions = ref([]);
  const parameterExamples = ref([]);
  const pushOptions = ref([]);
  const detailVersionOptions = ref([]);

  // === 商家/门店选项 ===
  function normalizeVendorOptions(rows = []) {
    return rows
      .map((item) => ({
        venderNo: String(item.venderNo || '').trim(),
        vendorName: String(item.vendorName || '').trim(),
        label: buildVendorOptionLabel(item),
      }))
      .filter((item) => item.venderNo && item.vendorName);
  }

  function buildVendorOptionLabel(vendor) {
    const venderNo = String(vendor.venderNo || '').trim();
    const name = String(vendor.vendorName || '').trim();
    return [venderNo, name].filter(Boolean).join(' - ');
  }

  function buildStoreOptionLabel(store) {
    const name = String(store.storeName || store.storeId || '').trim();
    const orgNo = String(store.storeCode || store.storeId || '').trim();
    const sapOrgNo = String(store.sapOrgNo || '').trim();
    return [name, orgNo ? `[${orgNo}]` : '', sapOrgNo ? `(${sapOrgNo})` : '']
      .filter(Boolean)
      .join(' ');
  }

  function loadVendorOptions() {
    return getTicketLogPullVendorStoreOptions().then((response) => {
      vendorOptions.value = normalizeVendorOptions(response.data?.vendors || []);
      console.log(vendorOptions.value);
      parameterExamples.value = Array.isArray(response.data?.parameterExamples)
        ? response.data.parameterExamples
        : [];
    });
  }

  function loadProjectVendorMapOptions() {
    return listTicketLogPullProjectVendorMapOptions().then((response) => {
      projectVendorMapOptions.value = Array.isArray(response.data) ? response.data : [];
    });
  }

  function getProjectVendorNo(projectId) {
    const resolvedProjectId = Number(projectId);
    if (!resolvedProjectId) return '';
    const mapping = projectVendorMapOptions.value.find(
      (item) => Number(item.projectId) === resolvedProjectId
    );
    return String(mapping?.venderNo || '').trim();
  }

  // === Provider / Agent / Prompt 选项 ===
  function loadProviderOptions() {
    return listAiProviderOptions().then((response) => {
      providerOptions.value = response.data || [];
    });
  }

  function loadAnalysisPromptOptions() {
    return listAiPromptTemplateOptions({
      template_category: 'analysis,common',
      enabled_only: true,
    }).then((response) => {
      analysisPromptOptions.value = response.data || [];
    });
  }

  function getTicketAutomationLogPullConfig(ticketData = {}) {
    const extraData = ticketData.extraData || ticketData.extra_data || {};
    const automation = extraData.ticketAutomation || extraData.ticket_automation || {};
    return automation.logPullConfig || automation.log_pull_config || {};
  }

  function findAiProviderOption(providerCode) {
    const resolvedCode = String(providerCode || '').trim();
    if (!resolvedCode) return undefined;
    return providerOptions.value.find(
      (item) => String(item.providerCode || '').trim() === resolvedCode
    );
  }

  function resolveAiAnalysisProviderAgent(providerCode) {
    const provider = findAiProviderOption(providerCode);
    const providerAgentCode = String(provider?.agentCode || '').trim();
    return providerAgentCode || null;
  }

  function resolveDefaultAiPromptTemplateCodesFromDetail(detail) {
    const contextCodes = detail?.latestAiAnalysis?.analysisContext?.selectedPromptTemplateCodes;
    if (Array.isArray(contextCodes) && contextCodes.length) return contextCodes;
    const config = getTicketAutomationLogPullConfig(detail || {});
    const rawCodes =
      config.promptTemplateCodes ||
      config.prompt_template_codes ||
      config.aiPromptTemplateCodes ||
      config.ai_prompt_template_codes;
    if (Array.isArray(rawCodes))
      return rawCodes.map((item) => String(item || '').trim()).filter(Boolean);
    if (typeof rawCodes === 'string')
      return rawCodes
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);
    return [];
  }

  // === 版本选项 ===
  function loadDetailVersionOptions(projectId) {
    if (!projectId) {
      detailVersionOptions.value = [];
      return Promise.resolve();
    }
    return listTicketAiRepoMappings({
      pageNum: 1,
      pageSize: 200,
      projectId,
      enabled: true,
    }).then((response) => {
      const rows = response.rows || [];
      const optionMap = new Map();
      rows.forEach((item) => {
        const value = String(item.versionKey || '').trim();
        if (!value || optionMap.has(value)) {
          return;
        }
        const branchName = String(item.branchName || '').trim();
        const repoUrl = String(item.repoUrl || '').trim();
        const labelParts = [value];
        if (branchName) {
          labelParts.push(`- ${branchName}`);
        }
        if (repoUrl) {
          labelParts.push(`(${repoUrl})`);
        }
        optionMap.set(value, {
          value,
          label: labelParts.join(' '),
        });
      });
      detailVersionOptions.value = Array.from(optionMap.values());
    });
  }

  // === Push 选项 ===
  function loadPushOptions() {
    return listAllPushConfig({ pageNum: 1, pageSize: 500 }).then((response) => {
      const rows = response.data || [];
      pushOptions.value = Array.isArray(rows) ? rows : [];
    });
  }

  // === 项目/模块选项 ===
  function loadProjectOptions() {
    return listTicketProjectOptions().then((response) => {
      projectOptions.value = response.data || [];
    });
  }

  function loadAgentOptions() {
    return listAllAgents().then((response) => {
      agentOptions.value = Array.isArray(response.data) ? response.data : [];
    });
  }

  function normalizeQueryList(value) {
    if (Array.isArray(value)) {
      return value.filter((item) => item !== undefined && item !== null && item !== '');
    }
    if (value === undefined || value === null || value === '') {
      return [];
    }
    return [value];
  }

  function buildModuleCodeOptions(moduleOptions = []) {
    const codeMap = new Map();
    (Array.isArray(moduleOptions) ? moduleOptions : []).forEach((item) => {
      const code = String(item?.moduleCode || '').trim();
      if (!code || codeMap.has(code)) {
        return;
      }
      codeMap.set(code, {
        value: code,
        label: code,
      });
    });
    return Array.from(codeMap.values());
  }

  function loadQueryModuleOptions(projectIds) {
    const selectedProjectIds = normalizeQueryList(projectIds).map((item) => String(item));
    return listTicketModuleOptions({}).then((response) => {
      const allModules = response.data || [];
      queryModuleOptions.value = selectedProjectIds.length
        ? allModules.filter((item) => selectedProjectIds.includes(String(item.projectId)))
        : allModules;
      queryModuleCodeOptions.value = buildModuleCodeOptions(queryModuleOptions.value);
    });
  }

  function loadFormModuleOptions(projectId) {
    if (!projectId) {
      formModuleOptions.value = [];
      return Promise.resolve();
    }
    return listTicketModuleOptions(projectId ? { projectId } : {}).then((response) => {
      formModuleOptions.value = response.data || [];
    });
  }

  function loadFormVersionOptions(projectId) {
    if (!projectId) {
      formVersionOptions.value = [];
      return Promise.resolve();
    }
    return listTicketAiRepoMappings({
      pageNum: 1,
      pageSize: 200,
      projectId,
      enabled: true,
    }).then((response) => {
      const rows = response.rows || [];
      const optionMap = new Map();
      rows.forEach((item) => {
        const value = String(item.versionKey || '').trim();
        if (!value || optionMap.has(value)) {
          return;
        }
        const branchName = String(item.branchName || '').trim();
        const repoUrl = String(item.repoUrl || '').trim();
        const labelParts = [value];
        if (branchName) {
          labelParts.push(`- ${branchName}`);
        }
        if (repoUrl) {
          labelParts.push(`(${repoUrl})`);
        }
        optionMap.set(value, {
          value,
          label: labelParts.join(' '),
        });
      });
      formVersionOptions.value = Array.from(optionMap.values());
    });
  }

  // === 格式化辅助函数 ===
  function getStatOptionLabel(options, value) {
    const text = String(value || '').trim();
    if (!text) return '-';
    const option = (options || []).find((item) => item.value === text);
    return option?.label || text;
  }

  function formatStatOption(options, value) {
    return getStatOptionLabel(options.value || options, value);
  }

  function formatProblemFlag(value) {
    if (value === true) return '真实问题';
    if (value === false) return '非问题';
    return '-';
  }

  function formatIssueType(row, localIssueTypeOptions) {
    const issueTypeName = row?.issueTypeName || row?.issue_type_name || '';
    if (issueTypeName) return issueTypeName;
    const issueTypeId = row?.issueTypeId || row?.issue_type_id || '';
    if (!issueTypeId) return '-';
    const option = (localIssueTypeOptions || issueTypeOptions.value).find(
      (item) => item.value === String(issueTypeId).trim()
    );
    return option?.label || '-';
  }

  function formatResolution(row) {
    const resolutionName = row?.resolutionName || row?.resolution_name || '';
    if (resolutionName) return resolutionName;
    const resolutionCode = row?.resolutionCode || row?.resolution_code || '';
    return resolutionCode ? getStatOptionLabel(resolutionOptions.value, resolutionCode) : '-';
  }

  function formatProblemPattern(row) {
    const patternName = row?.problemPatternName || row?.problem_pattern_name || '';
    if (patternName) return patternName;
    const patternCode = row?.problemPatternCode || row?.problem_pattern_code || '';
    return patternCode ? getStatOptionLabel(problemPatternOptions.value, patternCode) : '-';
  }

  // === 统计分类选项 ===
  function normalizeStatOptions(items = []) {
    return (Array.isArray(items) ? items : [])
      .map((item) => ({
        value: String(item.value || item.code || '').trim(),
        label: String(item.label || item.name || item.value || item.code || '').trim(),
      }))
      .filter((item) => item.value);
  }

  function loadStatClassificationOptions() {
    return getTicketStatClassificationOptions()
      .then((response) => {
        const config = response.data || {};
        issueTypeOptions.value = normalizeStatOptions(config.issueTypes);
        rootCauseTypeOptions.value = normalizeStatOptions(config.rootCauseTypes);
        solutionTypeOptions.value = normalizeStatOptions(config.solutionTypes);
        resolutionOptions.value = normalizeStatOptions(config.resolutions);
        problemPatternOptions.value = normalizeStatOptions(config.problemPatterns);
      })
      .catch(() => {
        issueTypeOptions.value = [];
        rootCauseTypeOptions.value = [];
        solutionTypeOptions.value = [];
        resolutionOptions.value = [];
        problemPatternOptions.value = [];
      });
  }

  return {
    // refs
    projectOptions,
    projectVendorMapOptions,
    formModuleOptions,
    formVersionOptions,
    queryModuleOptions,
    queryModuleCodeOptions,
    issueTypeOptions,
    rootCauseTypeOptions,
    solutionTypeOptions,
    resolutionOptions,
    problemPatternOptions,
    agentOptions,
    providerOptions,
    analysisPromptOptions,
    vendorOptions,
    parameterExamples,
    pushOptions,
    detailVersionOptions,
    // vendor/store functions
    normalizeVendorOptions,
    buildVendorOptionLabel,
    buildStoreOptionLabel,
    loadVendorOptions,
    loadProjectVendorMapOptions,
    getProjectVendorNo,
    // provider/agent/prompt functions
    loadProviderOptions,
    loadAnalysisPromptOptions,
    getTicketAutomationLogPullConfig,
    findAiProviderOption,
    resolveAiAnalysisProviderAgent,
    resolveDefaultAiPromptTemplateCodesFromDetail,
    // version functions
    loadDetailVersionOptions,
    // push functions
    loadPushOptions,
    // project/module functions
    loadProjectOptions,
    loadAgentOptions,
    normalizeQueryList,
    buildModuleCodeOptions,
    loadQueryModuleOptions,
    loadFormModuleOptions,
    loadFormVersionOptions,
    // format helpers
    getStatOptionLabel,
    formatStatOption,
    formatProblemFlag,
    formatIssueType,
    formatResolution,
    formatProblemPattern,
    // stat classification
    normalizeStatOptions,
    loadStatClassificationOptions,
  };
}
