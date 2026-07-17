/**
 * 工单日志拉取和日志查看器 composable。
 *
 * 该 hook 从工单管理页拆出日志拉取表单、记录刷新、下载和日志查看器能力；
 * 业务行为保持与备份分支 master_params_ticket_new 中 index.vue 的实现一致。
 */
import { computed, ref } from 'vue'
import { saveAs } from 'file-saver'
import { blobValidate } from '@/utils/ruoyi'
import {
  addTicketLogPull,
  delTicketLogPull,
  downloadTicketLogPull,
  listTicketLogPulls,
  retryTicketLogPull,
  redownloadTicketLogPull,
  prepareTicketLogs,
  searchTicketLogs,
  getTicketLogContext,
  getTicketLogErrors
} from '@/api/ticket/ticket'
import {
  buildOptionalLogPullTimeRangePayload,
  createDefaultLogPullNotifyConfig,
  formatLogPullParameter,
  getOptionalLogPullTimeRangeError,
  normalizeLogPullNotifyConfig,
  resolveLogPullArchiveLink,
  resolveLogPullOriginalLink
} from '@/views/ticket/logPull.shared'

export function useLogViewer(proxy, currentTicketId, options = {}) {
  const {
    detail,
    detailOpen,
    getList,
    refreshDetail,
    applyProjectVendorMapping,
    getVendorStoreOptions
  } = options

  const logPullLoading = ref(false)
  const logPullSubmitting = ref(false)
  const logPullActionLoading = ref(false)
  const logPullSubmitOpen = ref(false)
  const logPullContentOpen = ref(false)
  const logPullList = ref([])
  const logPullTotal = ref(0)
  const logPullWrapEnabled = ref(false)
  const logPullAutoRefreshing = ref(false)
  let logPullRefreshTimer = null
  const selectedLogPullRecord = ref(null)
  const activeLogPullStatuses = ['pending', 'processing', 'polling']
  const logPullQuery = ref({ pageNum: 1, pageSize: 20 })

  function createDefaultLogPullForm() {
    return {
      vendorId: undefined,
      storeId: undefined,
      posNo: undefined,
      commandDataType: 1,
      modifyTime: undefined,
      path: '',
      cutLogEnabled: false,
      timeRangeMode: 'between',
      fileMaxSize: 500,
      zipMaxSize: 500,
      logBeginTime: undefined,
      logEndTime: undefined,
      logPointTime: undefined,
      rangeBeforeMinutes: 30,
      rangeAfterMinutes: 30,
      storageMode: 'local',
      autoAiEnabled: false,
      aiAgentCode: '',
      aiProviderCode: '',
      notifyConfig: createDefaultLogPullNotifyConfig()
    }
  }

  const logPullForm = ref(createDefaultLogPullForm())
  const logViewerTicketMeta = ref({ ticketId: undefined, ticketNo: '', title: '' })
  const logViewerSearching = ref(false)
  const logViewerHits = ref([])
  const logViewerContext = ref(null)
  const logViewerErrorSummary = ref(null)
  const logViewerResultViewMode = ref('normal')
  const logViewerContextViewMode = ref('normal')
  const logViewerHighlightText = ref('')
  const logViewerHighlightKeywords = ref([])
  const logViewerHighlightSummary = computed(() => logViewerHighlightKeywords.value.join('、'))
  const logViewerSelectionHighlightKeyword = ref('')
  const logViewerSelectionHighlightOwned = ref(false)
  const logViewerForm = ref({
    ticketId: undefined,
    keyword: '',
    keywords: '',
    searchMode: 'any',
    file: '',
    contextLines: 20,
    limit: 500
  })

  function buildCleanLogPullConfig(source) {
    const config = { ...(source || {}) }
    config.notifyConfig = normalizeLogPullNotifyConfig(config.notifyConfig)
    if (Number(config.commandDataType) === 2) {
      delete config.modifyTime
    } else {
      delete config.path
    }
    if (!config.cutLogEnabled) {
      delete config.timeRangeMode
      delete config.logBeginTime
      delete config.logEndTime
      delete config.logPointTime
      delete config.rangeBeforeMinutes
      delete config.rangeAfterMinutes
    } else if (config.timeRangeMode === 'between') {
      delete config.logPointTime
      delete config.rangeBeforeMinutes
      delete config.rangeAfterMinutes
    } else if (config.timeRangeMode === 'point') {
      delete config.logBeginTime
      delete config.logEndTime
    }
    delete config.cutLogEnabled
    if (!config.autoAiEnabled) {
      config.aiAgentCode = ''
      config.aiProviderCode = ''
    }
    return config
  }

  function resetLogPullForm() {
    logPullForm.value = createDefaultLogPullForm()
    if (proxy.$refs.logPullRef) {
      proxy.resetForm('logPullRef')
    }
  }

  function resetStoreSelection(target, vendorId) {
    const storeId = String(target.storeId || '').trim()
    if (!storeId) {
      target.storeId = undefined
      return
    }
    const storeOptions = typeof getVendorStoreOptions === 'function' ? getVendorStoreOptions(vendorId) : []
    if (storeOptions.length && !storeOptions.some(item => String(item.storeId || '').trim() === storeId)) {
      target.storeId = storeId
    }
  }

  function handleLogPullVendorChange(vendorId) {
    resetStoreSelection(logPullForm.value, vendorId)
  }

  function pickFirstFilledValue(candidates = []) {
    for (const candidate of candidates) {
      if (candidate === null || candidate === undefined) continue
      if (typeof candidate === 'string' && !candidate.trim()) continue
      return candidate
    }
    return undefined
  }

  function resolveTicketLogPullHintsFromDetail(ticketDetail) {
    const detailPayload = ticketDetail || {}
    const extraData = detailPayload.extraData || detailPayload.extra_data || {}
    const externalSync = extraData.externalSync || extraData.external_sync || {}
    const source = externalSync.source || {}
    const logPullHints = extraData.logPullHints || extraData.log_pull_hints || {}
    const ticketAutomation = extraData.ticketAutomation || extraData.ticket_automation || {}
    const automationLogPullConfig = ticketAutomation.logPullConfig || ticketAutomation.log_pull_config || {}
    const latestLogPull = detailPayload.latestLogPull || detailPayload.latest_log_pull || {}
    const directLogPullConfig = detailPayload.logPullConfig || detailPayload.log_pull_config || {}
    return {
      vendorId: pickFirstFilledValue([
        source.vendorId, source.vendor_id, logPullHints.vendorId, logPullHints.vendor_id,
        latestLogPull.vendorId, latestLogPull.vendor_id, automationLogPullConfig.vendorId,
        automationLogPullConfig.vendor_id, directLogPullConfig.vendorId, directLogPullConfig.vendor_id
      ]),
      storeId: pickFirstFilledValue([
        source.storeId, source.store_id, logPullHints.storeId, logPullHints.store_id,
        latestLogPull.storeId, latestLogPull.store_id, automationLogPullConfig.storeId,
        automationLogPullConfig.store_id, directLogPullConfig.storeId, directLogPullConfig.store_id
      ]),
      posNo: pickFirstFilledValue([
        source.posNo, source.pos_no, source.posId, source.pos_id, source.scoNo, source.sco_no,
        logPullHints.posNo, logPullHints.pos_no, latestLogPull.posNo, latestLogPull.pos_no,
        automationLogPullConfig.posNo, automationLogPullConfig.pos_no,
        directLogPullConfig.posNo, directLogPullConfig.pos_no
      ]),
      modifyTime: pickFirstFilledValue([
        source.modifyTime, source.modify_time, source.logDate, source.log_date,
        logPullHints.modifyTime, logPullHints.modify_time, logPullHints.logDate, logPullHints.log_date,
        latestLogPull.modifyTime, latestLogPull.modify_time,
        automationLogPullConfig.modifyTime, automationLogPullConfig.modify_time,
        directLogPullConfig.modifyTime, directLogPullConfig.modify_time
      ])
    }
  }

  function applyTicketDetailLogPullPrefill(ticketDetail) {
    const hints = resolveTicketLogPullHintsFromDetail(ticketDetail)
    let vendorApplied = false
    const vendorId = Number(hints.vendorId)
    if (Number.isFinite(vendorId) && vendorId > 0) {
      logPullForm.value.vendorId = vendorId
      vendorApplied = true
    }
    const storeId = String(hints.storeId || '').trim()
    if (storeId) logPullForm.value.storeId = storeId
    const posNo = Number(hints.posNo)
    if (Number.isFinite(posNo) && posNo > 0) logPullForm.value.posNo = posNo
    const modifyTime = String(hints.modifyTime || '').trim()
    if (modifyTime) logPullForm.value.modifyTime = modifyTime.slice(0, 10)
    return { vendorApplied }
  }

  function openLogPullSubmitDialog() {
    resetLogPullForm()
    if (currentTicketId.value) {
      logPullForm.value.ticketId = currentTicketId.value
    }
    const prefillResult = applyTicketDetailLogPullPrefill(detail?.value)
    if (!prefillResult.vendorApplied && typeof applyProjectVendorMapping === 'function') {
      applyProjectVendorMapping(detail?.value?.projectId)
    }
    logPullSubmitOpen.value = true
  }

  function stopLogPullAutoRefresh() {
    if (logPullRefreshTimer) {
      window.clearTimeout(logPullRefreshTimer)
      logPullRefreshTimer = null
    }
    logPullAutoRefreshing.value = false
  }

  function scheduleLogPullAutoRefresh() {
    stopLogPullAutoRefresh()
    const hasRunningTask = detailOpen?.value && logPullList.value.some(item =>
      activeLogPullStatuses.includes(String(item.status || '').toLowerCase())
    )
    logPullAutoRefreshing.value = hasRunningTask
    if (!hasRunningTask) return
    logPullRefreshTimer = window.setTimeout(() => {
      Promise.all([
        loadLogPullList(true),
        typeof refreshDetail === 'function' ? refreshDetail() : Promise.resolve()
      ]).finally(() => scheduleLogPullAutoRefresh())
    }, 10000)
  }

  function loadLogPullList(silent = false) {
    if (!currentTicketId.value) return Promise.resolve()
    if (!silent) logPullLoading.value = true
    return listTicketLogPulls(currentTicketId.value, logPullQuery.value).then(response => {
      logPullList.value = response.rows || []
      logPullTotal.value = response.total || 0
      if (selectedLogPullRecord.value) {
        selectedLogPullRecord.value =
          logPullList.value.find(item => item.id === selectedLogPullRecord.value.id) || selectedLogPullRecord.value
      }
      scheduleLogPullAutoRefresh()
    }).finally(() => {
      if (!silent) logPullLoading.value = false
    })
  }

  function submitLogPull() {
    proxy.$refs.logPullRef.validate(valid => {
      if (!valid) return
      if (Number(logPullForm.value.commandDataType) === 2 && !String(logPullForm.value.path || '').trim()) {
        proxy.$modal.msgWarning('数据类型为数据库时，path 不能为空')
        return
      }
      if (Number(logPullForm.value.commandDataType) !== 2 && !logPullForm.value.modifyTime) {
        proxy.$modal.msgWarning('数据类型为日志时，modifyTime 不能为空')
        return
      }
      const timeRangeError = getOptionalLogPullTimeRangeError(logPullForm.value)
      if (timeRangeError) {
        proxy.$modal.msgWarning(timeRangeError)
        return
      }
      if (
        logPullForm.value.autoAiEnabled &&
        !String(logPullForm.value.aiAgentCode || '').trim() &&
        !String(logPullForm.value.aiProviderCode || '').trim()
      ) {
        proxy.$modal.msgWarning('启用自动AI分析时，请先选择Provider或Agent')
        return
      }
      const payload = {
        vendorId: logPullForm.value.vendorId,
        storeId: logPullForm.value.storeId,
        posNo: logPullForm.value.posNo,
        commandDataType: logPullForm.value.commandDataType,
        fileMaxSize: logPullForm.value.fileMaxSize,
        zipMaxSize: logPullForm.value.zipMaxSize,
        storageMode: logPullForm.value.storageMode,
        notifyConfig: normalizeLogPullNotifyConfig(logPullForm.value.notifyConfig)
      }
      if (Number(logPullForm.value.commandDataType) === 2) {
        payload.path = logPullForm.value.path
      } else {
        payload.modifyTime = logPullForm.value.modifyTime
      }
      Object.assign(payload, buildOptionalLogPullTimeRangePayload(logPullForm.value))
      payload.autoAiEnabled = Boolean(logPullForm.value.autoAiEnabled)
      payload.aiAgentCode = logPullForm.value.autoAiEnabled ? String(logPullForm.value.aiAgentCode || '').trim() : ''
      payload.aiProviderCode = logPullForm.value.autoAiEnabled
        ? String(logPullForm.value.aiProviderCode || '').trim()
        : ''
      logPullSubmitting.value = true
      addTicketLogPull(currentTicketId.value, payload).then(() => {
        proxy.$modal.msgSuccess('日志拉取任务已提交')
        logPullSubmitOpen.value = false
        resetLogPullForm()
        Promise.all([
          loadLogPullList(true),
          typeof refreshDetail === 'function' ? refreshDetail() : Promise.resolve(),
          typeof getList === 'function' ? getList() : Promise.resolve()
        ])
      }).finally(() => {
        logPullSubmitting.value = false
      })
    })
  }

  function runLogPullAction(actionPromise, successMessage) {
    logPullActionLoading.value = true
    return actionPromise
      .then(() => {
        proxy.$modal.msgSuccess(successMessage)
        return Promise.all([
          loadLogPullList(true),
          typeof refreshDetail === 'function' ? refreshDetail() : Promise.resolve(),
          typeof getList === 'function' ? getList() : Promise.resolve()
        ])
      })
      .finally(() => {
        logPullActionLoading.value = false
      })
  }

  function deleteLogPull(row) {
    if (!row?.id) return
    if (activeLogPullStatuses.includes(String(row.status || '').toLowerCase())) {
      proxy.$modal.msgWarning('当前日志拉取任务仍在执行中，不能删除')
      return
    }
    proxy.$modal.confirm(`是否确认删除日志拉取记录 #${row.id}？删除后会同步清理关联文件数据。`).then(() => {
      logPullActionLoading.value = true
      return delTicketLogPull(row.id)
    }).then(() => {
      proxy.$modal.msgSuccess('日志拉取记录已删除')
      if (selectedLogPullRecord.value?.id === row.id) {
        logPullContentOpen.value = false
        selectedLogPullRecord.value = null
      }
      return Promise.all([
        loadLogPullList(true),
        typeof refreshDetail === 'function' ? refreshDetail() : Promise.resolve(),
        typeof getList === 'function' ? getList() : Promise.resolve()
      ])
    }).catch(() => {}).finally(() => {
      logPullActionLoading.value = false
    })
  }

  function retryLogPull(row) {
    if (!row?.id) return
    if (activeLogPullStatuses.includes(String(row.status || '').toLowerCase())) {
      proxy.$modal.msgWarning('当前日志拉取任务仍在执行中，不能重新拉取')
      return
    }
    runLogPullAction(retryTicketLogPull(row.id), '已重新提交拉取任务')
  }

  function redownloadLogPull(row) {
    if (!row?.id) return
    if (!row.commandResultUrl && !row.storagePath) {
      proxy.$modal.msgWarning('当前记录缺少可用于重新下载的归档地址')
      return
    }
    runLogPullAction(redownloadTicketLogPull(row.id), '日志压缩包已重新下载')
  }

  function openBrowserDownload(url) {
    const targetUrl = String(url || '').trim()
    if (!targetUrl) return false
    window.open(targetUrl, '_blank', 'noopener')
    return true
  }

  function getLogPullOriginalDownloadUrl(row) {
    return resolveLogPullOriginalLink(row).url
  }

  function getLogPullArchiveDownloadUrl(row) {
    return resolveLogPullArchiveLink(row, 'service').url
  }

  function getLogPullArchiveDisplayText(row) {
    const link = resolveLogPullArchiveLink(row, 'service')
    return link.text || link.url
  }

  async function copyTextToClipboard(text) {
    const copyText = String(text || '').trim()
    if (!copyText) return false
    if (navigator.clipboard?.writeText && window.isSecureContext) {
      await navigator.clipboard.writeText(copyText)
      return true
    }
    const textarea = document.createElement('textarea')
    textarea.value = copyText
    textarea.setAttribute('readonly', 'readonly')
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.select()
    const copied = document.execCommand('copy')
    document.body.removeChild(textarea)
    return copied
  }

  async function copyLogPullOriginalDownloadUrl(row) {
    const targetUrl = getLogPullOriginalDownloadUrl(row)
    if (!targetUrl) {
      proxy.$modal.msgWarning('当前记录缺少原始压缩包地址')
      return
    }
    try {
      const copied = await copyTextToClipboard(targetUrl)
      if (!copied) {
        proxy.$modal.msgError('复制失败，请手动复制链接')
        return
      }
      proxy.$modal.msgSuccess('下载链接已复制')
    } catch (error) {
      console.error(error)
      proxy.$modal.msgError('复制失败，请手动复制链接')
    }
  }

  async function copyLogPullArchiveDownloadUrl(row) {
    const { url, needLogin } = resolveLogPullArchiveLink(row, 'service')
    if (!url) {
      proxy.$modal.msgWarning('当前记录缺少本服务归档地址')
      return
    }
    try {
      const copied = await copyTextToClipboard(url)
      if (!copied) {
        proxy.$modal.msgError('复制失败，请手动复制链接')
        return
      }
      proxy.$modal.msgSuccess(needLogin ? '下载链接已复制，访问时需要当前系统登录态' : '下载链接已复制')
    } catch (error) {
      console.error(error)
      proxy.$modal.msgError('复制失败，请手动复制链接')
    }
  }

  function resolveLogPullDownloadFileName(row, source = 'auto') {
    let remoteName = ''
    if (row?.commandResultUrl) {
      try {
        remoteName = new URL(String(row.commandResultUrl)).pathname.split('/').pop() || ''
      } catch (error) {
        remoteName = String(row.commandResultUrl).split('/').pop() || ''
      }
    }
    const candidates = [
      row?.downloadFileName,
      source !== 'original' && row?.storagePath ? String(row.storagePath).split(/[\\/]/).pop() : '',
      remoteName,
      `ticket_log_pull_${row?.id || Date.now()}.zip`
    ]
    for (const candidate of candidates) {
      const text = String(candidate || '').trim()
      if (text) return text
    }
    return `ticket_log_pull_${row?.id || Date.now()}.zip`
  }

  async function downloadLogPullFile(row, source, emptyMessage) {
    if (!row?.id) return
    try {
      logPullActionLoading.value = true
      const blob = await downloadTicketLogPull(row.id, source)
      if (!blobValidate(blob)) {
        try {
          const text = await blob.text()
          const payload = JSON.parse(text)
          proxy.$modal.msgError(payload.msg || emptyMessage || '下载失败')
        } catch (error) {
          proxy.$modal.msgError(emptyMessage || '下载失败')
        }
        return
      }
      saveAs(blob, resolveLogPullDownloadFileName(row, source))
    } catch (error) {
      console.error(error)
    } finally {
      logPullActionLoading.value = false
    }
  }

  function downloadLogPullArchive(row) {
    if (!row?.storagePath) {
      proxy.$modal.msgWarning('当前记录缺少本服务归档地址')
      return
    }
    if (/^https?:\/\//i.test(String(row.storagePath))) {
      openBrowserDownload(row.storagePath)
      return
    }
    downloadLogPullFile(row, 'service', '本服务归档文件不存在或不可下载')
  }

  function downloadLogPullOriginal(row) {
    if (!row?.commandResultUrl) {
      proxy.$modal.msgWarning('当前记录缺少原始压缩包地址')
      return
    }
    openBrowserDownload(row.commandResultUrl)
  }

  function syncLogViewerTicketMeta(payload = {}) {
    logViewerTicketMeta.value = {
      ticketId: payload.ticketId ?? currentTicketId.value,
      ticketNo: payload.ticketNo || '',
      title: payload.title || ''
    }
  }

  function buildLogViewerRecord(row, ticketMeta = {}) {
    const record = {
      ...(row || {}),
      ticketId: ticketMeta.ticketId || row?.ticketId,
      ticketNo: ticketMeta.ticketNo || row?.ticketNo || '',
      title: ticketMeta.title || row?.title || ''
    }
    syncLogViewerTicketMeta(record)
    return record
  }

  function resetLogViewerState(ticketId = currentTicketId.value) {
    selectedLogPullRecord.value = null
    logViewerHits.value = []
    logViewerContext.value = null
    logViewerErrorSummary.value = null
    logViewerForm.value.keyword = ''
    logViewerForm.value.keywords = ''
    logViewerForm.value.file = ''
    clearLogViewerHighlight()
    logViewerForm.value.ticketId = ticketId
  }

  function openTicketLogViewer(row) {
    const ticketId = row?.ticketId
    const recordId = row?.id
    if (!ticketId) return
    logViewerSearching.value = true
    prepareTicketLogs(ticketId, recordId).then(() => {
      currentTicketId.value = ticketId
      resetLogViewerState(ticketId)
      syncLogViewerTicketMeta({
        ticketId,
        ticketNo: row?.ticketNo || detail?.value?.ticketNo || '',
        title: row?.title || detail?.value?.title || ''
      })
      selectedLogPullRecord.value = row?.id
        ? buildLogViewerRecord(row, {
          ticketId,
          ticketNo: row?.ticketNo || detail?.value?.ticketNo || '',
          title: row?.title || detail?.value?.title || ''
        })
        : {
          id: undefined,
          ticketId,
          ticketNo: row?.ticketNo || detail?.value?.ticketNo || '',
          title: row?.title || detail?.value?.title || '',
          storagePath: row.latestLogPull?.storagePath || '',
          commandResultUrl: row.latestLogPull?.commandResultUrl || ''
        }
      logPullWrapEnabled.value = false
      logPullContentOpen.value = true
    }).finally(() => {
      logViewerSearching.value = false
    })
  }

  function openLogViewerFromPullRecord(row) {
    const ticketMeta = {
      ticketId: row?.ticketId || currentTicketId.value || detail?.value?.ticketId,
      ticketNo: row?.ticketNo || detail?.value?.ticketNo || '',
      title: row?.title || detail?.value?.title || ''
    }
    if (!ticketMeta.ticketId) {
      proxy.$modal.msgWarning('当前日志记录缺少工单ID，无法查看日志')
      return
    }
    selectedLogPullRecord.value = buildLogViewerRecord(row, ticketMeta)
    openTicketLogViewer(buildLogViewerRecord(row, ticketMeta))
  }

  function handleLogPullDialogClosed() {
    logViewerTicketMeta.value = { ticketId: undefined, ticketNo: '', title: '' }
    selectedLogPullRecord.value = null
    logPullWrapEnabled.value = false
    logViewerHits.value = []
    logViewerContext.value = null
    logViewerErrorSummary.value = null
    clearLogViewerHighlight()
  }

  function buildLogViewerPayload(keywordField = 'keyword') {
    const contextLines = Number(logViewerForm.value.contextLines || 0)
    const limit = Math.min(Math.max(Number(logViewerForm.value.limit || 500), 1), 5000)
    const recordId = selectedLogPullRecord.value?.id
    const payload = {
      ticketId: currentTicketId.value || selectedLogPullRecord.value?.ticketId || logViewerForm.value.ticketId,
      recordId,
      contextBefore: contextLines,
      contextAfter: contextLines,
      limit,
      withContext: false
    }
    const keywords = normalizeLogViewerKeywords(logViewerForm.value.keywords)
    payload.keywords = keywords
    payload.keyword = keywords[0] || String(logViewerForm.value[keywordField] || '').trim()
    payload.searchMode = String(logViewerForm.value.searchMode || 'any').trim().toLowerCase() === 'all' ? 'all' : 'any'
    const file = String(logViewerForm.value.file || '').trim()
    if (file) payload.file = file
    return payload
  }

  /** 设置日志关键字搜索的文件范围。 */
  function setLogViewerFileScope(file) {
    logViewerForm.value.file = String(file || '').trim()
  }

  /** 将搜索范围切到指定日志文件后立即用当前关键字重新搜索。 */
  function searchLogViewerInFile(file) {
    setLogViewerFileScope(file)
    searchLogViewerKeyword()
  }

  /** 清空日志搜索文件范围，后续搜索恢复全局目录。 */
  function clearLogViewerFileScope() {
    logViewerForm.value.file = ''
  }

  /** 归一化日志搜索或高亮关键字，支持数组、逗号、分号和换行分隔。 */
  function normalizeLogViewerKeywords(value) {
    const rawItems = Array.isArray(value)
      ? value
      : String(value || '').split(/[\n,，;；]+/)
    const keywords = []
    rawItems.forEach(item => {
      const keyword = String(item || '').trim()
      if (keyword && !keywords.includes(keyword)) {
        keywords.push(keyword.slice(0, 200))
      }
    })
    return keywords.slice(0, 10)
  }

  /** 同步多高亮关键字，并维护旧展示字段。 */
  function syncLogViewerHighlightKeywords(value, displayText) {
    const keywords = normalizeLogViewerKeywords(value)
    logViewerHighlightKeywords.value = keywords
    logViewerHighlightText.value = displayText === undefined ? keywords.join('\n') : displayText
  }

  /** 从高亮词列表中移除当前选区临时追加的高亮词。 */
  function removeLogViewerSelectionOwnedKeyword(keywords = logViewerHighlightKeywords.value) {
    const selectedKeyword = logViewerSelectionHighlightKeyword.value
    if (!selectedKeyword || !logViewerSelectionHighlightOwned.value) {
      return normalizeLogViewerKeywords(keywords)
    }
    return normalizeLogViewerKeywords(keywords).filter(keyword => keyword !== selectedKeyword)
  }

  /** 同步用户输入的多高亮关键字；存在选区时保留选区对应的临时高亮词。 */
  function updateLogViewerHighlightKeywords(value) {
    const keywords = normalizeLogViewerKeywords(value)
    const selectedKeyword = logViewerSelectionHighlightKeyword.value
    if (selectedKeyword && !keywords.includes(selectedKeyword)) {
      keywords.push(selectedKeyword)
      syncLogViewerHighlightKeywords(keywords)
      return
    }
    syncLogViewerHighlightKeywords(
      keywords,
      Array.isArray(value) ? keywords.join('\n') : String(value || '')
    )
  }

  /** 增加一个日志高亮关键字。 */
  function addLogViewerHighlightKeyword(text) {
    const keyword = normalizeLogViewerSelectedText(text)
    if (!keyword) return
    const keywords = removeLogViewerSelectionOwnedKeyword()
    if (!keywords.includes(keyword)) {
      keywords.push(keyword)
    }
    logViewerSelectionHighlightKeyword.value = ''
    logViewerSelectionHighlightOwned.value = false
    syncLogViewerHighlightKeywords(keywords)
  }

  /** 归一化用户在日志详细信息中选中的文本，避免跨行选择导致高亮范围过大。 */
  function normalizeLogViewerSelectedText(text) {
    const selected = String(text || '').replace(/\r/g, '').trim()
    if (!selected || selected.includes('\n')) return ''
    return selected.length > 200 ? selected.slice(0, 200) : selected
  }

  /** 捕获日志详细信息块的选中文本，并作为当前上下文临时高亮关键字。 */
  function captureLogViewerHighlight(text) {
    const selected = normalizeLogViewerSelectedText(
      text === undefined ? window.getSelection?.().toString() : text
    )
    if (!selected) return
    if (selected.length < 2) {
      proxy.$modal.msgWarning('请选择至少 2 个字符用于高亮')
      return
    }
    const keywords = removeLogViewerSelectionOwnedKeyword()
    const existed = keywords.includes(selected)
    if (!existed) {
      keywords.push(selected)
    }
    logViewerSelectionHighlightKeyword.value = selected
    logViewerSelectionHighlightOwned.value = !existed
    syncLogViewerHighlightKeywords(keywords)
  }

  /** 清除由当前浏览器选区临时追加的高亮词，保留用户手工维护的高亮词。 */
  function clearLogViewerSelectionHighlight() {
    if (!logViewerSelectionHighlightKeyword.value) return
    const keywords = removeLogViewerSelectionOwnedKeyword()
    logViewerSelectionHighlightKeyword.value = ''
    logViewerSelectionHighlightOwned.value = false
    syncLogViewerHighlightKeywords(keywords)
  }

  /** 清空当前上下文高亮关键字。 */
  function clearLogViewerHighlight() {
    logViewerHighlightText.value = ''
    logViewerHighlightKeywords.value = []
    logViewerSelectionHighlightKeyword.value = ''
    logViewerSelectionHighlightOwned.value = false
  }

  function setLogViewerPanelMode(panel, mode) {
    if (panel === 'result') {
      logViewerResultViewMode.value = mode
      return
    }
    logViewerContextViewMode.value = mode
  }

  function searchLogViewerKeyword() {
    const keywords = normalizeLogViewerKeywords(logViewerForm.value.keywords)
    if (!keywords.length) {
      proxy.$modal.msgWarning('请输入搜索关键字')
      return
    }
    logViewerForm.value.keywords = keywords.join('\n')
    logViewerForm.value.keyword = keywords[0]
    updateLogViewerHighlightKeywords(keywords)
    logViewerSearching.value = true
    searchTicketLogs(buildLogViewerPayload('keyword')).then(response => {
      setLogViewerHits(response?.data || [])
    }).finally(() => {
      logViewerSearching.value = false
    })
  }

  function loadLogViewerErrors() {
    const ticketId = currentTicketId.value || selectedLogPullRecord.value?.ticketId || logViewerForm.value.ticketId
    if (!ticketId) return
    const limit = Math.min(Math.max(Number(logViewerForm.value.limit || 500), 1), 5000)
    logViewerSearching.value = true
    getTicketLogErrors({ ticketId, recordId: selectedLogPullRecord.value?.id, limit }).then(response => {
      logViewerErrorSummary.value = response?.data || null
      setLogViewerHits(logViewerErrorSummary.value?.samples || [])
    }).finally(() => {
      logViewerSearching.value = false
    })
  }

  function setLogViewerHits(rows = []) {
    logViewerHits.value = rows.map((item, index) => ({
      ...item,
      hitKey: `${item.file || ''}:${item.line || 0}:${index}`
    }))
    logViewerContext.value = null
    if (logViewerHits.value.length === 1) {
      selectLogViewerHit(logViewerHits.value[0])
    }
  }

  function selectLogViewerHit(row) {
    if (!row) return
    loadLogViewerContext(row.file, row.line)
  }

  function pageLogViewerContext(direction) {
    const context = logViewerContext.value
    if (!context) return
    if (direction > 0) {
      loadLogViewerContext(context.nextFile, context.nextLine)
      return
    }
    loadLogViewerContext(context.prevFile, context.prevLine)
  }

  function loadLogViewerContext(file, line) {
    const ticketId = currentTicketId.value ||
      selectedLogPullRecord.value?.ticketId ||
      logViewerTicketMeta.value?.ticketId ||
      logViewerForm.value.ticketId
    if (!ticketId || !file || !line) return
    const contextLines = Number(logViewerForm.value.contextLines || 0)
    logViewerSearching.value = true
    getTicketLogContext({
      ticketId,
      record_id: selectedLogPullRecord.value?.id,
      file,
      line,
      before: contextLines,
      after: contextLines
    }).then(response => {
      logViewerContext.value = response?.data || null
    }).finally(() => {
      logViewerSearching.value = false
    })
  }

  return {
    logPullLoading,
    logPullSubmitting,
    logPullActionLoading,
    logPullSubmitOpen,
    logPullContentOpen,
    logPullList,
    logPullTotal,
    logPullForm,
    logPullQuery,
    logPullWrapEnabled,
    logPullAutoRefreshing,
    selectedLogPullRecord,
    activeLogPullStatuses,
    logViewerTicketMeta,
    logViewerSearching,
    logViewerHits,
    logViewerContext,
    logViewerErrorSummary,
    logViewerResultViewMode,
    logViewerContextViewMode,
    logViewerHighlightText,
    logViewerHighlightKeywords,
    logViewerHighlightSummary,
    logViewerSelectionHighlightKeyword,
    logViewerForm,
    createDefaultLogPullForm,
    buildCleanLogPullConfig,
    resetLogPullForm,
    resetStoreSelection,
    handleLogPullVendorChange,
    pickFirstFilledValue,
    resolveTicketLogPullHintsFromDetail,
    applyTicketDetailLogPullPrefill,
    openLogPullSubmitDialog,
    stopLogPullAutoRefresh,
    scheduleLogPullAutoRefresh,
    loadLogPullList,
    submitLogPull,
    runLogPullAction,
    deleteLogPull,
    retryLogPull,
    redownloadLogPull,
    openBrowserDownload,
    getLogPullOriginalDownloadUrl,
    getLogPullArchiveDownloadUrl,
    getLogPullArchiveDisplayText,
    formatLogPullParameter,
    copyTextToClipboard,
    copyLogPullOriginalDownloadUrl,
    copyLogPullArchiveDownloadUrl,
    resolveLogPullDownloadFileName,
    downloadLogPullFile,
    downloadLogPullArchive,
    downloadLogPullOriginal,
    syncLogViewerTicketMeta,
    buildLogViewerRecord,
    openTicketLogViewer,
    openLogViewerFromPullRecord,
    handleLogPullDialogClosed,
    resetLogViewerState,
    buildLogViewerPayload,
    setLogViewerFileScope,
    searchLogViewerInFile,
    clearLogViewerFileScope,
    normalizeLogViewerSelectedText,
    normalizeLogViewerKeywords,
    captureLogViewerHighlight,
    clearLogViewerSelectionHighlight,
    updateLogViewerHighlightKeywords,
    addLogViewerHighlightKeyword,
    clearLogViewerHighlight,
    setLogViewerPanelMode,
    searchLogViewerKeyword,
    loadLogViewerErrors,
    setLogViewerHits,
    selectLogViewerHit,
    pageLogViewerContext,
    loadLogViewerContext
  }
}
