// 工单 API 统一入口（向后兼容）
// 原 ticket.js 已拆分为 6 个文件，按功能域组织
export {
  // crud
  listTicket,
  downloadTicketImportTemplate,
  importTicketExcel,
  searchTicketNaturalLanguage,
  addTicket,
  updateTicket,
  delTicket,
  getTicket,
} from './crud';

export {
  // operations
  assignTicket,
  changeTicketStatus,
  translateTicketDescription,
  addTicketComment,
  getTicketComments,
  getTicketMessages,
  addTicketMessage,
  addTicketSnapshot,
  extractTicketKnowledge,
  addTicketEvent,
  getTicketTimeline,
  saveTicketRca,
} from './operations';

export {
  // sync
  getTicketSyncAutomationConfig,
  saveTicketSyncAutomationConfig,
  previewTicketSyncBitablePullFields,
  listTicketSyncNotifyPushOptions,
  previewTicketSyncPersonReminder,
  runTicketSyncPersonReminder,
  runTicketSyncSummaryReport,
  sendTicketSyncGroupPushByTicket,
  batchReclassifyTicketSync,
  getTicketSyncAutoCategoryStats,
} from './sync';

export {
  // logPull
  getTicketLogPullStorageConfig,
  saveTicketLogPullStorageConfig,
  getTicketLogPullVendorStoreOptions,
  downloadTicketLogPullStoreConfigTemplate,
  listTicketLogPullStoreConfigs,
  importTicketLogPullStoreConfigs,
  listTicketLogPullProjectVendorMaps,
  listTicketLogPullProjectVendorMapOptions,
  getTicketLogPullProjectVendorMap,
  saveTicketLogPullProjectVendorMap,
  addTicketLogPull,
  createTicketLogPullRecord,
  downloadTicketLogPull,
  retryTicketLogPull,
  delTicketLogPull,
  redownloadTicketLogPull,
  getTicketLogPullContent,
  prepareTicketLogs,
  listTicketLogFiles,
  searchTicketLogs,
  getTicketLogContext,
  getTicketLogErrors,
  listTicketLogPulls,
  listTicketLogPullRecords,
} from './logPull';

export {
  // ai
  listTicketAiRepoMappings,
  addTicketAiRepoMapping,
  updateTicketAiRepoMapping,
  delTicketAiRepoMapping,
  listTicketAiAnalysisTasks,
  addTicketAiAnalysis,
  retryTicketAiAnalysis,
} from './ai';

export {
  // config
  getTicketSimilarityConfig,
  saveTicketSimilarityConfig,
  rebuildTicketSimilarity,
  getTicketStatClassificationOptions,
  getTicketWorkflow,
  saveWorkflowStatus,
  delWorkflowStatus,
  saveWorkflowTransition,
  delWorkflowTransition,
  listTicketUserOptions,
  listTicketProjectOptions,
  listTicketModuleOptions,
  getTicketStatistics,
  getTicketStatisticsTrend,
  listKnowledge,
  getKnowledge,
  addKnowledge,
  updateKnowledge,
  delKnowledge,
} from './config';
