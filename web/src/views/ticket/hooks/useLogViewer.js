/**
 * 工单日志查看器 + 日志拉取 composable。
 *
 * 从 index.vue 提取（37 个函数，~624 行）：
 * - 日志拉取记录 CRUD（提交/重试/删除/下载/刷新）
 * - 日志查看器（搜索/上下文/异常提取/面板切换）
 * - 下载工具（复制链接/浏览器下载/blob 保存）
 */
import { ref } from 'vue'
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
import { createDefaultLogPullNotifyConfig } from '@/views/ticket/logPull.shared'

export function useLogViewer(proxy, currentTicketId) {
  // === 日志拉取状态 ===
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

  const logPullQuery = { pageNum: 1, pageSize: 20 }

  function createDefaultLogPullForm() {
    return {
      logDataType: 'app_log',
      storageMode: 'ftp',
      vendorId: undefined,
      storeId: undefined,
      posNo: '',
      commandType: 'pull',
      timeRangeMode: 'between',
      beginTime: '',
      endTime: '',
      pointTime: '',
      rangeBeforeMinutes: 5,
      rangeAfterMinutes: 10,
      autoRefresh: false,
      autoRefreshCount: 0,
      ticketId: undefined,
      notifyConfig: createDefaultLogPullNotifyConfig()
    }
  }

  const logPullForm = ref(createDefaultLogPullForm())

  // === 日志查看器状态 ===
  const logViewerTicketMeta = ref({ ticketId: undefined, ticketNo: '', title: '' })
  const logViewerSearching = ref(false)
  const logViewerHits = ref([])
  const logViewerContext = ref(null)
  const logViewerErrorSummary = ref(null)
  const logViewerResultViewMode = ref('normal')
  const logViewerContextViewMode = ref('normal')
  const logViewerForm = ref({ ticketId: undefined, keyword: '', contextLines: 20, limit: 500 })

  // === 日志拉取 CRUD ===
  function buildCleanLogPullConfig(rawConfig) {
    const config = typeof rawConfig === 'object' && rawConfig !== null ? { ...rawConfig } : {}
    const clean = {}
    const allowedKeys = ['logDataType', 'storageMode', 'vendorId', 'storeId', 'posNo',
      'commandType', 'timeRangeMode', 'beginTime', 'endTime', 'pointTime',
      'rangeBeforeMinutes', 'rangeAfterMinutes', 'notifyConfig', 'ticketId',
      'autoRefresh', 'autoRefreshCount']
    for (const key of allowedKeys) {
      if (key in config) clean[key] = config[key]
    }
    return clean
  }

  function resetLogPullForm() {
    logPullForm.value = createDefaultLogPullForm()
  }

  function openLogPullSubmitDialog() {
    resetLogPullForm()
    logPullSubmitOpen.value = true
  }

  function stopLogPullAutoRefresh() {
    logPullAutoRefreshing.value = false
    if (logPullRefreshTimer) {
      clearInterval(logPullRefreshTimer)
      logPullRefreshTimer = null
    }
  }

  function scheduleLogPullAutoRefresh() {
    stopLogPullAutoRefresh()
    logPullAutoRefreshing.value = true
    logPullRefreshTimer = setInterval(() => {
      if (!logPullAutoRefreshing.value) { stopLogPullAutoRefresh(); return }
      loadLogPullList()
    }, 8000)
  }

  function loadLogPullList() {
    logPullLoading.value = true
    return listTicketLogPulls({ ...logPullQuery, ticketId: currentTicketId.value })
      .then(response => {
        logPullList.value = response.rows || []
        logPullTotal.value = response.total || 0
        const hasActive = logPullList.value.some(item =>
          activeLogPullStatuses.includes(String(item.status || '').toLowerCase())
        )
        if (hasActive && !logPullAutoRefreshing.value) scheduleLogPullAutoRefresh()
        else if (!hasActive && logPullAutoRefreshing.value) stopLogPullAutoRefresh()
      }).finally(() => { logPullLoading.value = false })
  }

  async function submitLogPull() {
    logPullSubmitting.value = true
    try {
      await addTicketLogPull({ ...logPullForm.value, ticketId: currentTicketId.value })
      proxy.$modal.msgSuccess('日志拉取任务已提交')
      logPullSubmitOpen.value = false
      loadLogPullList()
    } catch (e) { console.error(e) }
    finally { logPullSubmitting.value = false }
  }

  async function runLogPullAction(action, row, msg) {
    logPullActionLoading.value = true
    try {
      await action(row.id)
      proxy.$modal.msgSuccess(msg)
      loadLogPullList()
    } catch (e) { console.error(e) }
    finally { logPullActionLoading.value = false }
  }

  function deleteLogPull(row) { runLogPullAction(delTicketLogPull, row, '删除成功') }
  function retryLogPull(row) { runLogPullAction(retryTicketLogPull, row, '重新拉取已提交') }
  function redownloadLogPull(row) { runLogPullAction(redownloadTicketLogPull, row, '重新下载已提交') }

  // === 下载工具 ===
  function openBrowserDownload(url) {
    if (!url) { proxy.$modal.msgWarning('缺少下载地址'); return }
    window.open(url, '_blank')
  }

  function getLogPullOriginalDownloadUrl(row) { return String(row?.commandResultUrl || '').trim() }

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
    if (!targetUrl) { proxy.$modal.msgWarning('当前记录缺少原始压缩包地址'); return }
    try {
      const copied = await copyTextToClipboard(targetUrl)
      if (!copied) { proxy.$modal.msgError('复制失败，请手动复制链接'); return }
      proxy.$modal.msgSuccess('下载链接已复制')
    } catch (error) { console.error(error); proxy.$modal.msgError('复制失败，请手动复制链接') }
  }

  function resolveLogPullDownloadFileName(row, source = 'auto') {
    let remoteName = ''
    if (row?.commandResultUrl) {
      try { remoteName = new URL(String(row.commandResultUrl)).pathname.split('/').pop() || '' }
      catch (error) { remoteName = String(row.commandResultUrl).split('/').pop() || '' }
    }
    const candidates = [
      row?.downloadFileName,
      source !== 'original' && row?.storagePath ? String(row.storagePath).split(/[\\/]/).pop() : '',
      remoteName,
      `ticket_log_pull_${row?.id || Date.now()}.zip`
    ]
    for (const candidate of candidates) { const text = String(candidate || '').trim(); if (text) return text }
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
        } catch (error) { proxy.$modal.msgError(emptyMessage || '下载失败') }
        return
      }
      saveAs(blob, resolveLogPullDownloadFileName(row, source))
    } catch (error) { console.error(error) }
    finally { logPullActionLoading.value = false }
  }

  function downloadLogPullArchive(row) { downloadLogPullFile(row, 'archive', '归档文件不存在') }
  function downloadLogPullOriginal(row) { downloadLogPullFile(row, 'original', '原始压缩包不存在') }

  // === 日志查看器 ===
  function syncLogViewerTicketMeta(payload = {}) {
    logViewerTicketMeta.value = {
      ticketId: payload.ticketId ?? currentTicketId.value,
      ticketNo: payload.ticketNo || '',
      title: payload.title || ''
    }
  }

  function buildLogViewerRecord(row, ticketMeta = {}) {
    selectedLogPullRecord.value = row
    syncLogViewerTicketMeta(ticketMeta)
  }

  function openTicketLogViewer(row) {
    buildLogViewerRecord(row)
    logPullContentOpen.value = true
    logViewerForm.value.ticketId = row?.ticketId
    logViewerForm.value.keyword = ''
    logViewerHits.value = []
    logViewerContext.value = null
    logViewerErrorSummary.value = null
  }

  function openLogViewerFromPullRecord(row) { openTicketLogViewer(row) }

  function handleLogPullDialogClosed() {
    stopLogPullAutoRefresh()
    logPullContentOpen.value = false
    selectedLogPullRecord.value = null
    logViewerHits.value = []
    logViewerContext.value = null
    logViewerErrorSummary.value = null
  }

  function resetLogViewerState(ticketId) {
    stopLogPullAutoRefresh()
    selectedLogPullRecord.value = null
    logViewerHits.value = []
    logViewerContext.value = null
    logViewerErrorSummary.value = null
    logViewerForm.value.keyword = ''
  }

  function buildLogViewerPayload(keywordField = 'keyword') {
    return {
      recordId: selectedLogPullRecord.value?.id,
      ticketId: logViewerForm.value.ticketId || currentTicketId.value,
      keyword: logViewerForm.value[keywordField] || '',
      contextLines: logViewerForm.value.contextLines,
      limit: logViewerForm.value.limit
    }
  }

  function setLogViewerPanelMode(panel, mode) {
    if (panel === 'result') logViewerResultViewMode.value = mode
    if (panel === 'context') logViewerContextViewMode.value = mode
  }

  async function searchLogViewerKeyword() {
    logViewerSearching.value = true
    try {
      const payload = buildLogViewerPayload()
      const data = await searchTicketLogs(payload)
      setLogViewerHits(data?.hits || [])
    } catch (error) { console.error(error) }
    finally { logViewerSearching.value = false }
  }

  async function loadLogViewerErrors() {
    logViewerSearching.value = true
    try {
      const payload = buildLogViewerPayload()
      const data = await getTicketLogErrors(payload)
      logViewerErrorSummary.value = data?.errorSummary || null
    } catch (error) { console.error(error) }
    finally { logViewerSearching.value = false }
  }

  function setLogViewerHits(rows = []) { logViewerHits.value = rows }

  function selectLogViewerHit(row) {
    if (!row) return
    loadLogViewerContext(row.file, row.line)
  }

  async function pageLogViewerContext(direction) {
    if (!logViewerContext.value) return
    const offset = direction > 0 ? logViewerContext.value.end : Math.max(0, logViewerContext.value.start - logViewerContext.value.contextLines * 2)
    await loadLogViewerContext(logViewerContext.value.file, Math.max(1, offset))
  }

  async function loadLogViewerContext(file, line) {
    logViewerSearching.value = true
    try {
      const data = await getTicketLogContext({
        recordId: selectedLogPullRecord.value?.id,
        ticketId: logViewerForm.value.ticketId || currentTicketId.value,
        file, line, contextLines: logViewerForm.value.contextLines
      })
      logViewerContext.value = data?.context || null
    } catch (error) { console.error(error) }
    finally { logViewerSearching.value = false }
  }

  return {
    // 日志拉取状态
    logPullLoading, logPullSubmitting, logPullActionLoading,
    logPullSubmitOpen, logPullContentOpen,
    logPullList, logPullTotal, logPullForm, logPullQuery,
    logPullWrapEnabled, logPullAutoRefreshing,
    selectedLogPullRecord, activeLogPullStatuses,
    // 日志查看器状态
    logViewerTicketMeta, logViewerSearching, logViewerHits,
    logViewerContext, logViewerErrorSummary,
    logViewerResultViewMode, logViewerContextViewMode, logViewerForm,
    // 表单工厂
    createDefaultLogPullForm,
    // 日志拉取 CRUD
    buildCleanLogPullConfig, resetLogPullForm, openLogPullSubmitDialog,
    stopLogPullAutoRefresh, scheduleLogPullAutoRefresh, loadLogPullList,
    submitLogPull, deleteLogPull, retryLogPull, redownloadLogPull,
    // 下载工具
    openBrowserDownload, getLogPullOriginalDownloadUrl,
    copyTextToClipboard, copyLogPullOriginalDownloadUrl,
    resolveLogPullDownloadFileName, downloadLogPullFile,
    downloadLogPullArchive, downloadLogPullOriginal,
    // 日志查看器
    syncLogViewerTicketMeta, buildLogViewerRecord,
    openTicketLogViewer, openLogViewerFromPullRecord,
    handleLogPullDialogClosed, resetLogViewerState,
    buildLogViewerPayload, setLogViewerPanelMode,
    searchLogViewerKeyword, loadLogViewerErrors,
    setLogViewerHits, selectLogViewerHit,
    pageLogViewerContext, loadLogViewerContext
  }
}
