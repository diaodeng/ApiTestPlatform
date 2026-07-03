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

const USER_CONFIG_KEY = 'ticket_column_visible_keys'

export function useTicketList(proxy, standaloneDetailMode) {
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
    currentAssigneeUserIds: [], firstLineAssigneeUserIds: [],
    internalOwnerUserIds: [], sortField: '', sortOrder: ''
  })

  const queryCurrentAssigneeOption = ref([])
  const queryFirstLineAssigneeOption = ref([])
  const queryInternalOwnerOption = ref([])

  // === 列配置 ===
  const columnConfigOpen = ref(false)
  const ticketColumnOptions = [
    { key: 'ticketNo', label: '工单编号', required: true },
    { key: 'title', label: '标题', required: true },
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
    if (Array.isArray(value)) return [...new Set(value.filter(k => typeof k === 'string' && k.trim()))]
    if (typeof value === 'string') return [...new Set(value.split(',').map(k => k.trim()).filter(Boolean))]
    return [...defaultTicketColumnKeys]
  }

  function loadTicketColumnConfig() {
    return getCurrentUserConfig(USER_CONFIG_KEY).then(response => {
      const raw = response?.data?.configValue ?? response?.data?.config_value
      visibleTicketColumnKeys.value = normalizeTicketColumnKeys(raw)
    }).catch(() => { visibleTicketColumnKeys.value = [...defaultTicketColumnKeys] })
  }

  function saveTicketColumnConfig() {
    const keys = [...new Set([...requiredTicketColumnKeys, ...visibleTicketColumnKeys.value])]
    return saveCurrentUserConfig({ configKey: USER_CONFIG_KEY, configValue: keys.join(',') })
  }

  function resetTicketColumnConfig() { visibleTicketColumnKeys.value = [...defaultTicketColumnKeys] }
  function isTicketColumnVisible(key) { return visibleTicketColumnKeys.value.includes(key) }

  // === 查询方法 ===
  function normalizeQueryList(value) {
    if (!Array.isArray(value)) return []
    return [...new Set(value.filter(Boolean))]
  }

  function joinQueryList(value) { return normalizeQueryList(value).join(',') }

  function buildTicketListQueryParams() {
    const params = { ...queryParams.value }
    if (submitTimeRange.value?.length === 2) {
      params.submitTimeBegin = submitTimeRange.value[0]
      params.submitTimeEnd = submitTimeRange.value[1]
    }
    return params
  }

  function getList() {
    if (standaloneDetailMode?.value) return Promise.resolve()
    loading.value = true
    return listTicket(buildTicketListQueryParams()).then(response => {
      ticketList.value = response.rows || []
      total.value = response.total || 0
    }).finally(() => { loading.value = false })
  }

  function toElementSortOrder(sortOrder) {
    if (sortOrder === 'ascending') return 'asc'
    if (sortOrder === 'descending') return 'desc'
    return ''
  }

  function normalizeTicketSortOrder(sortOrder) {
    if (sortOrder === 'asc') return 'ascending'
    if (sortOrder === 'desc') return 'descending'
    return ''
  }

  function handleTicketSortChange({ prop, order }) {
    queryParams.value.sortField = prop || ''
    queryParams.value.sortOrder = toElementSortOrder(order)
    getList()
  }

  // === 外部链接 ===
  function resolveTicketDetailUrl(ticketRow) {
    const extraData = ticketRow?.extraData || ticketRow?.extra_data || {}
    const source = extraData?.source || extraData?.external_source || ''
    return extraData?.ticketUrl || extraData?.ticket_url || extraData?.recordUrl || extraData?.record_url || ''
  }

  function openTicketLink(ticketRow) {
    const url = resolveTicketDetailUrl(ticketRow)
    if (!url) { proxy.$modal.msgWarning('该工单缺少外部链接'); return }
    window.open(url, '_blank')
  }

  function buildSystemTicketDetailUrl(ticketRow) {
    const id = ticketRow?.ticketId ?? ticketRow?.id
    return id ? `/ticket/detail/${id}` : ''
  }

  function openSystemTicketDetail(ticketRow) {
    const url = buildSystemTicketDetailUrl(ticketRow)
    if (url) window.open(url, '_blank')
  }

  // === 搜索 ===
  function handleQuery() { queryParams.value.pageNum = 1; getList() }
  function handleSearch() { handleQuery() }
  function resetQuery() {
    queryParams.value = {
      pageNum: 1, pageSize: 20, keyword: '', ticketNo: '',
      statuses: [], processStatuses: [], projectIds: [], moduleIds: [],
      moduleCodes: [], issueTypeIds: [], rootCauseTypes: [], solutionTypes: [],
      resolutionCodes: [], problemPatternCodes: [], isProblems: [],
      internalPriorities: [], sources: [], reporterNames: [],
      currentAssigneeUserIds: [], firstLineAssigneeUserIds: [],
      internalOwnerUserIds: [], sortField: '', sortOrder: ''
    }
    submitTimeRange.value = []
    naturalKeyword.value = ''
    queryCurrentAssigneeOption.value = []
    queryFirstLineAssigneeOption.value = []
    queryInternalOwnerOption.value = []
    handleQuery()
  }

  function handleNaturalSearch() {
    const keyword = naturalKeyword.value?.trim()
    if (!keyword) { proxy.$modal.msgWarning('请输入自然语言描述'); return }
    loading.value = true
    return searchTicketNaturalLanguage({ keyword, limit: 20 }).then(response => {
      ticketList.value = response.data || []
      total.value = ticketList.value.length
    }).finally(() => { loading.value = false })
  }

  // === 人员筛选 ===
  function handleQueryCurrentAssigneeChange(user) { queryParams.value.currentAssigneeUserIds = user ? [user.userId] : [] }
  function handleQueryFirstLineAssigneeChange(user) { queryParams.value.firstLineAssigneeUserIds = user ? [user.userId] : [] }
  function handleQueryInternalOwnerChange(user) { queryParams.value.internalOwnerUserIds = user ? [user.userId] : [] }

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
