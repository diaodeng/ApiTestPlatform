/**
 * 工单列表查询 composable。
 *
 * 从 index.vue 提取（23 个函数）：
 * - 列表查询、分页、排序、筛选
 * - 列配置（显隐、持久化）
 * - 外部链接跳转
 * - 自然语言搜索
 */
import { ref } from 'vue'
import { listTicket, searchTicketNaturalLanguage } from '@/api/ticket/ticket'
import { getCurrentUserConfig, saveCurrentUserConfig } from '@/api/system/userConfig'

export function useTicketList(proxy, standaloneDetailMode, router) {
  // === 列表状态 ===
  const loading = ref(false)
  const showSearch = ref(true)
  const ticketList = ref([])
  const total = ref(0)
  const naturalKeyword = ref('')
  const submitTimeRange = ref([])

  // === 查询参数 ===
  const queryParams = ref({
    pageNum: 1, pageSize: 20, keyword: '', ticketNo: '',
    statuses: [], processStatuses: [], projectIds: [], moduleIds: [],
    moduleCodes: [], issueTypeIds: [], rootCauseTypes: [], solutionTypes: [],
    resolutionCodes: [], problemPatternCodes: [], isProblems: [],
    internalPriorities: [], sources: [], reporterNames: [],
    currentAssigneeIds: [], firstLineAssigneeIds: [],
    internalOwnerIds: [], sortField: 'submitTime', sortOrder: 'desc'
  })

  const queryCurrentAssigneeOption = ref([])
  const queryFirstLineAssigneeOption = ref([])
  const queryInternalOwnerOption = ref([])

  // === 列配置 ===
  const columnConfigOpen = ref(false)
  const ticketColumnOptions = [
    { key: 'index', label: '序号' },
    { key: 'ticketNo', label: '工单编号', required: true },
    { key: 'title', label: '标题', required: true },
    { key: 'similarityScore', label: '相似度' },
    { key: 'status', label: '状态' },
    { key: 'processStatus', label: '处理状态' },
    { key: 'project', label: '项目' },
    { key: 'moduleName', label: '模块' },
    { key: 'issueType', label: '工单类型' },
    { key: 'isProblem', label: '问题性质' },
    { key: 'rootCauseType', label: '根因分类' },
    { key: 'solutionType', label: '解决方式' },
    { key: 'resolution', label: '关闭结果' },
    { key: 'problemPattern', label: '细分问题' },
    { key: 'customerPriority', label: '对方优先级' },
    { key: 'internalPriority', label: '内部优先级' },
    { key: 'source', label: '来源' },
    { key: 'firstLineAssigneeName', label: '1线人员' },
    { key: 'internalOwnerName', label: '内部负责人' },
    { key: 'currentAssigneeName', label: '当前处理人' },
    { key: 'submitTime', label: '工单提交时间' },
    { key: 'createTime', label: '创建时间' }
  ]
  const defaultTicketColumnKeys = ticketColumnOptions.map(item => item.key)
  const requiredTicketColumnKeys = ticketColumnOptions.filter(item => item.required).map(item => item.key)
  const visibleTicketColumnKeys = ref([...defaultTicketColumnKeys])

  // === 列配置方法 ===
  function normalizeTicketColumnKeys(value) {
    const rawKeys = Array.isArray(value?.visibleColumns) ? value.visibleColumns : value
    const validKeys = new Set(ticketColumnOptions.map(item => item.key))
    const normalized = (Array.isArray(rawKeys) ? rawKeys : defaultTicketColumnKeys)
      .map(item => String(item || '').trim())
      .filter(item => validKeys.has(item))
    requiredTicketColumnKeys.forEach(key => {
      if (!normalized.includes(key)) {
        normalized.push(key)
      }
    })
    return normalized.length ? normalized : [...defaultTicketColumnKeys]
  }

  function loadTicketColumnConfig() {
    return getCurrentUserConfig('ticket', 'ticket_list_columns').then(response => {
      visibleTicketColumnKeys.value = normalizeTicketColumnKeys(response.data?.configValue)
    }).catch(() => { visibleTicketColumnKeys.value = [...defaultTicketColumnKeys] })
  }

  function saveTicketColumnConfig() {
    visibleTicketColumnKeys.value = normalizeTicketColumnKeys(visibleTicketColumnKeys.value)
    return saveCurrentUserConfig({
      configType: 'ticket',
      configKey: 'ticket_list_columns',
      configValue: {
        visibleColumns: visibleTicketColumnKeys.value
      },
      remark: '工单列表显示列配置'
    }).then(() => {
      columnConfigOpen.value = false
      proxy.$modal.msgSuccess('保存成功')
    })
  }

  function resetTicketColumnConfig() { visibleTicketColumnKeys.value = [...defaultTicketColumnKeys] }
  function isTicketColumnVisible(key) { return visibleTicketColumnKeys.value.includes(key) }

  // === 查询方法 ===
  function normalizeQueryList(value) {
    if (Array.isArray(value)) {
      return value.filter(item => item !== undefined && item !== null && item !== '')
    }
    if (value === undefined || value === null || value === '') {
      return []
    }
    return [value]
  }

  function joinQueryList(value) {
    const items = normalizeQueryList(value)
    return items.length ? items.join(',') : undefined
  }

  function buildTicketListQueryParams() {
    const params = {
      ...queryParams.value,
      statuses: joinQueryList(queryParams.value.statuses),
      processStatuses: joinQueryList(queryParams.value.processStatuses),
      projectIds: joinQueryList(queryParams.value.projectIds),
      moduleIds: joinQueryList(queryParams.value.moduleIds),
      moduleCodes: joinQueryList(queryParams.value.moduleCodes),
      issueTypeIds: joinQueryList(queryParams.value.issueTypeIds),
      isProblems: joinQueryList(queryParams.value.isProblems),
      rootCauseTypes: joinQueryList(queryParams.value.rootCauseTypes),
      solutionTypes: joinQueryList(queryParams.value.solutionTypes),
      resolutionCodes: joinQueryList(queryParams.value.resolutionCodes),
      problemPatternCodes: joinQueryList(queryParams.value.problemPatternCodes),
      internalPriorities: joinQueryList(queryParams.value.internalPriorities),
      currentAssigneeIds: joinQueryList(queryParams.value.currentAssigneeIds),
      firstLineAssigneeIds: joinQueryList(queryParams.value.firstLineAssigneeIds),
      internalOwnerIds: joinQueryList(queryParams.value.internalOwnerIds)
    }
    return Object.fromEntries(
      Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')
    )
  }

  function getList() {
    if (standaloneDetailMode?.value) return Promise.resolve()
    const rangeValues = Array.isArray(submitTimeRange.value) ? submitTimeRange.value : []
    const [submitBeginTime, submitEndTime] = rangeValues
    queryParams.value.submitBeginTime = submitBeginTime || undefined
    queryParams.value.submitEndTime = submitEndTime || undefined
    loading.value = true
    return listTicket(buildTicketListQueryParams()).then(response => {
      ticketList.value = response.rows || []
      total.value = response.total || 0
    }).finally(() => { loading.value = false })
  }

  function toElementSortOrder(sortOrder) {
    const value = String(sortOrder || '').trim().toLowerCase()
    if (value === 'asc' || value === 'ascending') {
      return 'ascending'
    }
    return 'descending'
  }

  function normalizeTicketSortOrder(sortOrder) {
    const value = String(sortOrder || '').trim().toLowerCase()
    if (value === 'ascending' || value === 'asc') {
      return 'asc'
    }
    if (value === 'descending' || value === 'desc') {
      return 'desc'
    }
    return 'desc'
  }

  function handleTicketSortChange({ prop, order }) {
    queryParams.value.sortField = order ? (prop || 'submitTime') : 'submitTime'
    queryParams.value.sortOrder = order ? normalizeTicketSortOrder(order) : 'desc'
    queryParams.value.pageNum = 1
    getList()
  }

  // === 外部链接 ===
  function resolveTicketDetailUrl(ticketRow) {
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

  function openTicketLink(ticketRow) {
    const url = resolveTicketDetailUrl(ticketRow)
    if (!url) { proxy.$modal.msgWarning('当前工单未配置详情链接'); return }
    window.open(url, '_blank', 'noopener')
  }

  function buildSystemTicketDetailUrl(ticketRow) {
    const ticketId = Number(ticketRow?.ticketId || ticketRow?.ticket_id)
    if (!Number.isFinite(ticketId) || ticketId <= 0) {
      return ''
    }
    if (router?.resolve) {
      const resolved = router.resolve({
        name: 'TicketDetail',
        params: { ticketId }
      })
      return resolved.href
    }
    return `/ticket/detail/${ticketId}`
  }

  function openSystemTicketDetail(ticketRow) {
    const url = buildSystemTicketDetailUrl(ticketRow)
    if (url) window.open(url, '_blank')
  }

  // === 搜索 ===
  function handleQuery() { queryParams.value.pageNum = 1; getList() }
  function handleSearch() {
    if (naturalKeyword.value) {
      handleNaturalSearch()
      return
    }
    handleQuery()
  }
  function resetQuery() {
    proxy.resetForm('queryRef')
    submitTimeRange.value = []
    naturalKeyword.value = ''
    queryParams.value.submitBeginTime = undefined
    queryParams.value.submitEndTime = undefined
    queryCurrentAssigneeOption.value = []
    queryFirstLineAssigneeOption.value = []
    queryInternalOwnerOption.value = []
    handleQuery()
  }

  function handleNaturalSearch() {
    if (!naturalKeyword.value) { handleQuery(); return }
    loading.value = true
    const rangeValues = Array.isArray(submitTimeRange.value) ? submitTimeRange.value : []
    const [submitBeginTime, submitEndTime] = rangeValues
    queryParams.value.submitBeginTime = submitBeginTime || undefined
    queryParams.value.submitEndTime = submitEndTime || undefined
    const params = {
      ...buildTicketListQueryParams(),
      keyword: naturalKeyword.value,
      limit: queryParams.value.pageSize
    }
    // 自然语言搜索按相似度排序，不传排序字段
    delete params.sortField
    delete params.sortOrder
    return searchTicketNaturalLanguage(params).then(response => {
      ticketList.value = response.rows || response.data || []
      total.value = response.total || ticketList.value.length
    }).finally(() => { loading.value = false })
  }

  // === 人员筛选 ===
  function handleQueryCurrentAssigneeChange(user) { queryCurrentAssigneeOption.value = Array.isArray(user) ? user : (user ? [user] : []) }
  function handleQueryFirstLineAssigneeChange(user) { queryFirstLineAssigneeOption.value = Array.isArray(user) ? user : (user ? [user] : []) }
  function handleQueryInternalOwnerChange(user) { queryInternalOwnerOption.value = Array.isArray(user) ? user : (user ? [user] : []) }

  return {
    // state
    loading, showSearch, ticketList, total, naturalKeyword, submitTimeRange,
    queryParams, queryCurrentAssigneeOption, queryFirstLineAssigneeOption, queryInternalOwnerOption,
    // column config
    columnConfigOpen, ticketColumnOptions, defaultTicketColumnKeys,
    requiredTicketColumnKeys, visibleTicketColumnKeys,
    normalizeTicketColumnKeys, loadTicketColumnConfig, saveTicketColumnConfig,
    resetTicketColumnConfig, isTicketColumnVisible,
    // query
    normalizeQueryList, joinQueryList, buildTicketListQueryParams, getList,
    toElementSortOrder, normalizeTicketSortOrder, handleTicketSortChange,
    // external links
    resolveTicketDetailUrl, openTicketLink, buildSystemTicketDetailUrl, openSystemTicketDetail,
    // search
    handleQuery, handleSearch, resetQuery, handleNaturalSearch,
    // person filters
    handleQueryCurrentAssigneeChange, handleQueryFirstLineAssigneeChange, handleQueryInternalOwnerChange
  }
}
