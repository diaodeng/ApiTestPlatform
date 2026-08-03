<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    fullscreen
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    :close-on-press-escape="!hasFullscreenPanel"
    class="ticket-log-viewer-dialog"
    @closed="handleClosed"
  >
    <div v-loading="searching" class="log-viewer-content">
      <!-- 搜索工具栏 -->
      <div class="panel-header mb16 log-view-controls">
        <el-input
          v-model="form.keywords"
          class="log-keyword-input"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 2 }"
          clearable
          placeholder="输入搜索关键字，多个用英文逗号或换行分隔"
        />
        <el-radio-group v-model="form.searchMode" size="small">
          <el-radio-button value="any">任一</el-radio-button>
          <el-radio-button value="all">全部</el-radio-button>
        </el-radio-group>
        <el-button type="primary" :loading="searching" @click="searchKeyword">搜索</el-button>
        <el-select
          v-model="form.file"
          class="log-file-scope-select"
          clearable
          filterable
          placeholder="全局搜索"
        >
          <el-option v-for="file in fileOptions" :key="file" :label="file" :value="file" />
        </el-select>
        <el-button v-if="form.file" link type="primary" @click="clearFileScope">清除文件范围</el-button>
        <el-text>结果上限</el-text>
        <el-input-number
          v-model="form.limit"
          :min="1"
          :max="5000"
          :step="100"
          controls-position="right"
        />
        <slot name="toolbar-actions" />
        <el-button type="warning" :loading="searching" @click="loadErrors">异常提取</el-button>
      </div>

      <!-- 异常摘要 -->
      <el-alert
        v-if="errorSummary"
        type="warning"
        show-icon
        :closable="false"
        class="mb16"
        :title="`异常命中 ${errorSummary.total || 0} 条`"
      />

      <!-- 搜索结果面板 -->
      <div
        v-if="hits.length"
        :class="[
          'log-view-panel',
          'mb16',
          {
            'log-view-panel-fullscreen': resultViewMode === 'fullscreen',
            'log-view-panel-minimized': resultViewMode === 'minimized',
            'log-view-panel-fill':
              resultViewMode !== 'minimized' &&
              (!context || contextViewMode === 'minimized'),
          },
        ]"
      >
        <div class="panel-header mb8 log-view-panel-header">
          <span>搜索结果：{{ hits.length }} 条（当前上限 {{ form.limit }} 条）</span>
          <div class="panel-inline">
            <el-button
              link
              type="primary"
              :icon="resultViewMode === 'minimized' ? 'Plus' : 'Minus'"
              @click="toggleResultMode('minimized')"
            >
              {{ resultViewMode === 'minimized' ? '展开' : '最小化' }}
            </el-button>
            <el-button
              link
              type="primary"
              :icon="resultViewMode === 'fullscreen' ? 'FullScreen' : 'Rank'"
              @click="toggleResultMode('fullscreen')"
            >
              {{ resultViewMode === 'fullscreen' ? '还原' : '放大全屏' }}
            </el-button>
          </div>
        </div>
        <el-table-v2
          v-show="resultViewMode !== 'minimized'"
          :columns="resultTableColumns"
          :data="hits"
          row-key="hitKey"
          :width="resultTableWidth"
          :height="resultTableHeight"
          :header-height="44"
          :estimated-row-height="42"
          :row-height="42"
          :row-event-handlers="resultTableRowEventHandlers"
          row-class="log-hit-row"
        />
      </div>

      <!-- 上下文面板 -->
      <div
        v-if="context"
        :class="[
          'log-context-panel',
          'log-view-panel',
          'mb16',
          {
            'log-view-panel-fullscreen': contextViewMode === 'fullscreen',
            'log-view-panel-minimized': contextViewMode === 'minimized',
            'log-view-panel-fill':
              contextViewMode !== 'minimized' && resultViewMode === 'minimized',
          },
        ]"
      >
        <div class="panel-header mb8 log-view-panel-header">
          <span>{{ context.file }}:{{ context.line }}（{{ context.start }}-{{ context.end }}/{{ context.totalLines }}）</span>
          <div class="panel-inline">
            <el-text style="flex: none">上下文</el-text>
            <el-input-number
              v-model="form.contextLines"
              class="log-context-lines-input"
              :min="0"
              :max="500"
              controls-position="right"
            />
            <el-input
              v-model="highlightText"
              class="log-highlight-input"
              type="textarea"
              :rows="1"
              clearable
              placeholder="输入高亮文本，多个用英文逗号或换行分隔"
              @input="updateHighlightKeywords(highlightText)"
            />
            <el-switch
              v-model="wrapEnabled"
              inline-prompt
              active-text="换行"
              inactive-text="不换行"
            />
            <el-button
              icon="Delete"
              v-if="highlightSummary"
              link
              type="primary"
              @click="clearHighlight"
              title="清除高亮"
            />
            <el-button
              link
              type="primary"
              icon="ArrowLeftBold"
              title="上一段"
              :disabled="!context.hasPrev || searching"
              @click="pageContext(-1)"
            />
            <el-button
              link
              type="primary"
              icon="ArrowRightBold"
              title="下一段"
              :disabled="!context.hasNext || searching"
              @click="pageContext(1)"
            />
            <el-button
              link
              type="primary"
              :icon="contextViewMode === 'minimized' ? 'Plus' : 'Minus'"
              @click="toggleContextMode('minimized')"
            />
            <el-button
              link
              type="primary"
              :icon="contextViewMode === 'fullscreen' ? 'FullScreen' : 'Rank'"
              @click="toggleContextMode('fullscreen')"
            />
          </div>
        </div>
        <pre
          ref="contextBlockRef"
          v-show="contextViewMode !== 'minimized'"
          :class="['log-content-block', 'log-context-block', { 'log-content-wrap': wrapEnabled }]"
          @mouseup="handleContextSelection"
          @keyup="handleContextSelection"
        ><span
            v-for="item in contextDisplayLines"
            :key="`${item.file}:${item.line}`"
            class="log-context-line"
          ><span class="log-context-line-no">{{ item.paddedLine }}</span
          ><span class="log-context-line-content"
            ><template v-for="(part, partIndex) in item.parts" :key="partIndex"
              ><mark
                v-if="part.highlight"
                :class="['log-context-highlight', part.highlightClass]"
                >{{ part.text }}</mark
              ><span v-else>{{ part.text }}</span></template
            ></span
          ></span
        ></pre>
      </div>

      <!-- 日志准备全屏遮罩：覆盖弹窗 body，可点击关闭按钮或 ESC 取消 -->
      <div v-if="preparing" class="log-viewer-overlay">
        <div class="log-viewer-overlay-content">
          <el-icon class="log-viewer-overlay-spinner" :size="48"><Loading /></el-icon>
          <span class="log-viewer-overlay-title">正在准备日志文件...</span>
          <el-progress :percentage="prepareProgress" :stroke-width="8" class="log-viewer-overlay-progress" />
          <span class="log-viewer-overlay-hint">请稍候，可点击右上角关闭或按 ESC 取消</span>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
/**
 * 云端搜索日志查看器弹窗 — 共享组件。
 *
 * 供工单详情页和日志拉取管理页复用，提供关键字搜索、上下文查看、异常提取、高亮等功能。
 * 时间截取逻辑与此组件无关，仅用于拉取任务创建时的配置。
 */
import { computed, h, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useWindowSize } from '@vueuse/core'
import {
  prepareTicketLogs,
  listTicketLogFiles,
  searchTicketLogs,
  getTicketLogContext,
  getTicketLogErrors,
} from '@/api/ticket/ticket'
import { useLogPrepareProgress } from '@/views/ticket/hooks/useLogPrepareProgress'

const props = defineProps({
  /** 控制弹窗可见性 */
  modelValue: { type: Boolean, default: false },
  /** 日志拉取记录对象，需包含 id, ticketId, ticketNo, title */
  record: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue'])

const { prepareWithDownloadProgress, getDownloadProgress } = useLogPrepareProgress()

// ── 弹窗可见性 ──
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

// ── 对话框标题 ──
const dialogTitle = computed(() => {
  const ticketNo = String(props.record?.ticketNo || '').trim()
  const title = String(props.record?.title || props.record?.ticketTitle || '').trim()
  if (ticketNo && title) return `日志查看 - ${ticketNo} - ${title}`
  if (ticketNo) return `日志查看 - ${ticketNo}`
  if (title) return `日志查看 - ${title}`
  return '日志查看'
})

// ── 准备状态 ──
const preparing = ref(false)
const prepareProgress = ref(0)
const prepareTimer = ref(null)

// ── 搜索状态 ──
const searching = ref(false)
const hits = ref([])
const context = ref(null)
const errorSummary = ref(null)
const resultViewMode = ref('normal')
const contextViewMode = ref('normal')
const wrapEnabled = ref(false)
const availableFiles = ref([])
const hasFullscreenPanel = computed(
  () => resultViewMode.value === 'fullscreen' || contextViewMode.value === 'fullscreen'
)

const { width: windowWidth, height: windowHeight } = useWindowSize()

// ── 搜索表单 ──
const form = ref({
  keywords: '',
  searchMode: 'any',
  file: '',
  contextLines: 20,
  limit: 500,
})

// ── 高亮状态 ──
const highlightKeywords = ref([])
const highlightText = ref('')
const highlightSummary = computed(() => highlightKeywords.value.join('、'))
const selectionHighlightKeyword = ref('')
const selectionHighlightOwned = ref(false)
const contextBlockRef = ref(null)

const highlightName = 'ticket-log-context-highlight'
const nativeHighlightSupported = computed(() =>
  Boolean(
    window.CSS?.highlights &&
    typeof window.Highlight === 'function' &&
    typeof window.Range === 'function'
  )
)

// ── 文件选项 ──
const fileOptions = computed(() => availableFiles.value)

// ── 上下文展示行 ──
const contextDisplayLines = computed(() => {
  const lines = context.value?.lines || []
  return lines.map((item) => ({
    file: item.file || context.value?.file || '',
    line: item.line,
    paddedLine: `${String(item.line).padStart(6, ' ')}  `,
    content: item.content || '',
    parts: nativeHighlightSupported.value
      ? [{ text: item.content || '', highlight: false }]
      : splitHighlightParts(item.content || ''),
  }))
})

/**
 * 搜索结果区改为虚拟表格，避免大结果集在普通表格下卡顿。
 * 宽高继续沿用原先布局逻辑，只是改成虚拟表格可直接使用的数值。
 */
const resultTableWidth = computed(() => Math.max((windowWidth.value || 0) - 64, 720))

const resultTableHeight = computed(() =>
  resultViewMode.value === 'fullscreen'
    ? Math.max((windowHeight.value || 0) - 170, 240)
    : !context.value || contextViewMode.value === 'minimized'
      ? Math.max((windowHeight.value || 0) - 250, 240)
      : 320
)

function renderHitTextCell(className, value) {
  const text = String(value ?? '')
  return h('span', { class: className, title: text }, text)
}

const resultTableColumns = [
  {
    key: 'file',
    dataKey: 'file',
    title: '文件',
    width: 220,
    minWidth: 160,
    flexGrow: 1,
    cellRenderer: ({ rowData }) => renderHitTextCell('log-hit-cell log-hit-cell-file', rowData.file),
  },
  {
    key: 'line',
    dataKey: 'line',
    title: '行号',
    width: 90,
    align: 'center',
    cellRenderer: ({ rowData }) => renderHitTextCell('log-hit-cell log-hit-cell-line', rowData.line),
  },
  {
    key: 'content',
    dataKey: 'content',
    title: '内容',
    width: 360,
    minWidth: 260,
    flexGrow: 2,
    cellRenderer: ({ rowData }) =>
      renderHitTextCell(
        'log-hit-cell log-hit-cell-content',
        `${String(rowData.content ?? '')}${rowData.contentTruncated ? '...' : ''}`
      ),
  },
  {
    key: 'actions',
    title: '操作',
    width: 130,
    fixed: 'right',
    align: 'center',
    cellRenderer: ({ rowData }) =>
      h(
        'button',
        {
          type: 'button',
          class: 'log-hit-action-btn',
          title: '在此文件搜索',
          onClick: (event) => {
            event.stopPropagation()
            searchInFile(rowData.file)
          },
        },
        '在此文件搜索'
      ),
  },
]

const resultTableRowEventHandlers = {
  onClick: ({ rowData }) => {
    selectHit(rowData)
  },
}

// ── 打开弹窗时准备日志 ──
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    const ticketId = props.record?.ticketId || 0
    const recordId = props.record?.id
    if (!recordId) return
    preparing.value = true
    prepareProgress.value = 0
    startPrepareProgressPolling(ticketId, recordId)
    prepareWithDownloadProgress(ticketId, recordId, () => prepareTicketLogs(ticketId, recordId))
      .then(() => {
        if (!visible.value || props.record?.id !== recordId) return
        // 日志准备完成，重置查看器状态
        resetViewerState()
        return loadFileOptions(ticketId, recordId)
      })
      .finally(() => {
        stopPrepareProgressPolling()
        preparing.value = false
        prepareProgress.value = 0
      })
  }
)

function resetViewerState() {
  hits.value = []
  context.value = null
  errorSummary.value = null
  availableFiles.value = []
  form.value.keywords = ''
  form.value.file = ''
  clearHighlight()
  resultViewMode.value = 'normal'
  contextViewMode.value = 'normal'
  wrapEnabled.value = false
}

/**
 * 加载当前日志拉取记录的全部可搜索文件，并保留后端返回顺序。
 * @param {number|string} ticketId 工单ID
 * @param {number|string} recordId 日志拉取记录ID
 * @returns {Promise<void>} 文件列表加载完成后的 Promise
 */
function loadFileOptions(ticketId, recordId) {
  return listTicketLogFiles(ticketId, recordId)
    .then((response) => {
      if (!visible.value || props.record?.id !== recordId) return
      const files = []
      const seen = new Set()
      const responseFiles = response?.data || []
      responseFiles.forEach((item) => {
        const file = String(item?.file || item || '').trim()
        if (file && !seen.has(file)) {
          seen.add(file)
          files.push(file)
        }
      })
      availableFiles.value = files
    })
    .catch(() => {
      if (visible.value && props.record?.id === recordId) {
        availableFiles.value = []
      }
    })
}

/**
 * 启动日志准备下载进度轮询，从 useLogPrepareProgress 获取后端下载进度并更新弹窗进度条。
 * @param {number|string} ticketId 工单ID
 * @param {number|string} recordId 日志拉取记录ID
 */
function startPrepareProgressPolling(ticketId, recordId) {
  stopPrepareProgressPolling()
  const poll = () => {
    const progress = getDownloadProgress(ticketId, recordId)
    if (progress) {
      prepareProgress.value = progress.percentage
    }
    prepareTimer.value = window.setTimeout(poll, 400)
  }
  poll()
}

/** 停止日志准备进度轮询。 */
function stopPrepareProgressPolling() {
  if (prepareTimer.value) {
    window.clearTimeout(prepareTimer.value)
    prepareTimer.value = null
  }
}

function handleClosed() {
  stopPrepareProgressPolling()
  preparing.value = false
  prepareProgress.value = 0
  resetViewerState()
}

// ── 关键字归一化 ──
function normalizeKeywords(value) {
  const rawItems = Array.isArray(value) ? value : String(value || '').split(/[\n,，;；]+/)
  const keywords = []
  rawItems.forEach((item) => {
    const keyword = String(item || '').trim()
    if (keyword && !keywords.includes(keyword)) {
      keywords.push(keyword.slice(0, 200))
    }
  })
  return keywords.slice(0, 10)
}

// ── 搜索 ──
function searchKeyword() {
  const keywords = normalizeKeywords(form.value.keywords)
  if (!keywords.length) {
    return
  }
  form.value.keywords = keywords.join('\n')
  updateHighlightKeywords(keywords)
  searching.value = true
  const contextLines = Number(form.value.contextLines || 0)
  const limit = Math.min(Math.max(Number(form.value.limit || 500), 1), 5000)
  const payload = {
    ticketId: props.record?.ticketId || 0,
    recordId: props.record?.id,
    keywords,
    searchMode: String(form.value.searchMode || 'any').trim().toLowerCase() === 'all' ? 'all' : 'any',
    contextBefore: contextLines,
    contextAfter: contextLines,
    limit,
    withContext: false,
  }
  const file = String(form.value.file || '').trim()
  if (file) payload.file = file
  searchTicketLogs(payload)
    .then((response) => {
      setHits(response?.data || [])
    })
    .finally(() => {
      searching.value = false
    })
}

function setHits(rows = []) {
  hits.value = rows.map((item, index) => ({
    ...item,
    hitKey: `${item.file || ''}:${item.line || 0}:${index}`,
  }))
  context.value = null
  if (hits.value.length === 1) {
    selectHit(hits.value[0])
  }
}

function selectHit(row) {
  if (!row) return
  loadContext(row.file, row.line)
}

function loadContext(file, line) {
  const ticketId = props.record?.ticketId || 0
  if (!file || !line) return
  const contextLines = Number(form.value.contextLines || 0)
  searching.value = true
  getTicketLogContext({
    ticketId,
    record_id: props.record?.id,
    file,
    line,
    before: contextLines,
    after: contextLines,
  })
    .then((response) => {
      context.value = response?.data || null
    })
    .finally(() => {
      searching.value = false
    })
}

function pageContext(direction) {
  if (!context.value) return
  if (direction > 0) {
    loadContext(context.value.nextFile, context.value.nextLine)
  } else {
    loadContext(context.value.prevFile, context.value.prevLine)
  }
}

// ── 异常提取 ──
function loadErrors() {
  const ticketId = props.record?.ticketId || 0
  const limit = Math.min(Math.max(Number(form.value.limit || 500), 1), 5000)
  searching.value = true
  getTicketLogErrors({ ticketId, recordId: props.record?.id, limit })
    .then((response) => {
      errorSummary.value = response?.data || null
      setHits(errorSummary.value?.samples || [])
    })
    .finally(() => {
      searching.value = false
    })
}

// ── 文件范围 ──
function searchInFile(file) {
  form.value.file = String(file || '').trim()
  searchKeyword()
}
function clearFileScope() {
  form.value.file = ''
}

// ── 高亮 ──
function syncHighlightKeywords(value) {
  const keywords = normalizeKeywords(value)
  highlightKeywords.value = keywords
  highlightText.value = keywords.join('\n')
}

function updateHighlightKeywords(value) {
  const keywords = normalizeKeywords(value)
  const selectedKw = selectionHighlightKeyword.value
  if (selectedKw && !keywords.includes(selectedKw)) {
    keywords.push(selectedKw)
    syncHighlightKeywords(keywords)
    return
  }
  syncHighlightKeywords(Array.isArray(value) ? keywords.join('\n') : String(value || ''))
}

function clearHighlight() {
  highlightText.value = ''
  highlightKeywords.value = []
  selectionHighlightKeyword.value = ''
  selectionHighlightOwned.value = false
}

function removeSelectionOwnedKeyword() {
  const selectedKw = selectionHighlightKeyword.value
  if (!selectedKw || !selectionHighlightOwned.value) {
    return normalizeKeywords(highlightKeywords.value)
  }
  return normalizeKeywords(highlightKeywords.value).filter((kw) => kw !== selectedKw)
}

function captureHighlight(text) {
  const selected = normalizeSelectedText(text)
  if (!selected) return
  const keywords = removeSelectionOwnedKeyword()
  const existed = keywords.includes(selected)
  if (!existed) keywords.push(selected)
  selectionHighlightKeyword.value = selected
  selectionHighlightOwned.value = !existed
  syncHighlightKeywords(keywords)
}

function clearSelectionHighlight() {
  if (!selectionHighlightKeyword.value) return
  const keywords = removeSelectionOwnedKeyword()
  selectionHighlightKeyword.value = ''
  selectionHighlightOwned.value = false
  syncHighlightKeywords(keywords)
}

function normalizeSelectedText(text) {
  const selected = String(text || '').replace(/\r/g, '').trim()
  if (!selected || selected.includes('\n')) return ''
  return selected.length > 200 ? selected.slice(0, 200) : selected
}

// ── 原生 CSS Highlight API 高亮 ──
function clearNativeHighlights() {
  if (!nativeHighlightSupported.value) return
  window.CSS.highlights.delete(highlightName)
}

function buildHighlightRanges(textNode, keywords) {
  const text = textNode.textContent || ''
  const ranges = []
  let cursor = 0
  while (cursor < text.length) {
    let nextMatch = null
    keywords.forEach((keyword) => {
      const index = text.indexOf(keyword, cursor)
      if (index < 0) return
      if (
        !nextMatch ||
        index < nextMatch.index ||
        (index === nextMatch.index && keyword.length > nextMatch.keyword.length)
      ) {
        nextMatch = { index, keyword }
      }
    })
    if (!nextMatch) break
    const range = new window.Range()
    range.setStart(textNode, nextMatch.index)
    range.setEnd(textNode, nextMatch.index + nextMatch.keyword.length)
    ranges.push(range)
    cursor = nextMatch.index + nextMatch.keyword.length
  }
  return ranges
}

function refreshNativeHighlights() {
  if (!nativeHighlightSupported.value) return
  const block = contextBlockRef.value
  const keywords = Array.from(new Set(highlightKeywords.value || []))
    .map((item) => String(item || '').trim())
    .filter(Boolean)
    .sort((left, right) => right.length - left.length)
  if (!block || !keywords.length || contextViewMode.value === 'minimized') {
    clearNativeHighlights()
    return
  }
  const ranges = []
  block.querySelectorAll('.log-context-line-content').forEach((contentNode) => {
    const walker = document.createTreeWalker(contentNode, window.NodeFilter.SHOW_TEXT)
    let textNode = walker.nextNode()
    while (textNode) {
      ranges.push(...buildHighlightRanges(textNode, keywords))
      textNode = walker.nextNode()
    }
  })
  if (!ranges.length) {
    clearNativeHighlights()
    return
  }
  window.CSS.highlights.set(highlightName, new window.Highlight(...ranges))
}

// ── 回退 DOM mark 高亮 ──
function splitHighlightParts(content) {
  const text = String(content || '')
  const keywords = Array.from(new Set(highlightKeywords.value || []))
    .map((item) => String(item || '').trim())
    .filter(Boolean)
    .sort((left, right) => right.length - left.length)
  if (!keywords.length) return [{ text, highlight: false }]
  const parts = []
  let cursor = 0
  while (cursor < text.length) {
    let nextMatch = null
    keywords.forEach((keyword, keywordIndex) => {
      const index = text.indexOf(keyword, cursor)
      if (index < 0) return
      if (
        !nextMatch ||
        index < nextMatch.index ||
        (index === nextMatch.index && keyword.length > nextMatch.keyword.length)
      ) {
        nextMatch = { index, keyword, keywordIndex }
      }
    })
    if (!nextMatch) {
      parts.push({ text: text.slice(cursor), highlight: false })
      break
    }
    if (nextMatch.index > cursor) {
      parts.push({ text: text.slice(cursor, nextMatch.index), highlight: false })
    }
    parts.push({
      text: text.slice(nextMatch.index, nextMatch.index + nextMatch.keyword.length),
      highlight: true,
      highlightClass: `log-context-highlight-${nextMatch.keywordIndex % 6}`,
    })
    cursor = nextMatch.index + nextMatch.keyword.length
  }
  return parts.length ? parts : [{ text, highlight: false }]
}

// ── 选区高亮 ──
function getContextSelectionText() {
  const block = contextBlockRef.value
  const selection = window.getSelection?.()
  if (!block || !selection || selection.rangeCount === 0 || selection.isCollapsed) return ''
  if (!block.contains(selection.anchorNode) || !block.contains(selection.focusNode)) return ''
  return selection.toString()
}

function handleContextSelection() {
  const selectedText = getContextSelectionText()
  if (!selectedText) return
  captureHighlight(selectedText)
}

function handleDocumentSelectionChange() {
  const block = contextBlockRef.value
  const selection = window.getSelection?.()
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
    clearSelectionHighlight()
    return
  }
  if (block && block.contains(selection.anchorNode) && block.contains(selection.focusNode)) return
  clearSelectionHighlight()
}

// ── 面板模式切换 ──
function toggleResultMode(mode) {
  resultViewMode.value = resultViewMode.value === mode ? 'normal' : mode
}
function toggleContextMode(mode) {
  contextViewMode.value = contextViewMode.value === mode ? 'normal' : mode
}

/**
 * 优先处理日志子区域全屏状态，避免 Esc 直接关闭日志查看弹窗。
 * @param {KeyboardEvent} event 键盘事件
 */
function handleEscapeKey(event) {
  if (!visible.value || event.key !== 'Escape' || !hasFullscreenPanel.value) return
  event.preventDefault()
  event.stopImmediatePropagation()
  if (resultViewMode.value === 'fullscreen') {
    resultViewMode.value = 'normal'
  }
  if (contextViewMode.value === 'fullscreen') {
    contextViewMode.value = 'normal'
  }
}

// ── 高亮刷新 ──
watch(
  [context, highlightKeywords, contextViewMode],
  () => {
    nextTick(() => refreshNativeHighlights())
  },
  { deep: true }
)

onMounted(() => {
  document.addEventListener('selectionchange', handleDocumentSelectionChange)
  document.addEventListener('keydown', handleEscapeKey, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('selectionchange', handleDocumentSelectionChange)
  document.removeEventListener('keydown', handleEscapeKey, true)
  clearNativeHighlights()
  stopPrepareProgressPolling()
})
</script>

<style scoped>
.panel-header {
  display: flex;
  justify-content: start;
  gap: 12px;
}

.panel-inline {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
}

.mb16 { margin-bottom: 16px; }
.mb8 { margin-bottom: 8px; }

.log-view-controls {
  flex-wrap: wrap;
  align-items: center;
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

.log-file-scope-select {
  width: min(360px, 100%);
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

.log-hit-row {
  cursor: pointer;
}

.log-hit-cell {
  display: block;
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-hit-cell-line {
  text-align: center;
}

.log-hit-action-btn {
  padding: 0;
  border: 0;
  background: transparent;
  color: #409eff;
  cursor: pointer;
  font: inherit;
}

.log-hit-action-btn:hover {
  text-decoration: underline;
}

.log-view-panel-fullscreen .log-content-block { flex: 1; max-height: none; }

.log-view-panel-minimized {
  flex: 0 0 auto;
  padding-bottom: 6px;
}

.log-view-panel-fill {
  flex: 1 1 auto;
  min-height: 0;
}

.log-view-panel-fill .log-content-block {
  flex: 1 1 auto;
  max-height: none;
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
  min-height: 18px;
}

.log-context-line-no {
  display: inline-block;
  user-select: none;
  color: #64748b;
}

.log-context-line-content {
  white-space: inherit;
}

.log-context-highlight {
  padding: 0 1px;
  color: #111827;
  border-radius: 2px;
}

.log-context-highlight-0 { background: #fde68a; }
.log-context-highlight-1 { background: #bfdbfe; }
.log-context-highlight-2 { background: #bbf7d0; }
.log-context-highlight-3 { background: #fecaca; }
.log-context-highlight-4 { background: #ddd6fe; }
.log-context-highlight-5 { background: #fed7aa; }

.log-highlight-input :deep(.el-textarea__inner) {
  height: 32px;
  min-height: 32px !important;
  max-height: 32px;
  overflow: auto;
  resize: none;
  white-space: pre;
}

.log-viewer-overlay {
  position: absolute;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(2px);
}

.log-viewer-overlay-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 48px 64px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12);
}

.log-viewer-overlay-spinner {
  color: #409eff;
  animation: log-viewer-spin 1s linear infinite;
}

@keyframes log-viewer-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.log-viewer-overlay-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.log-viewer-overlay-progress {
  width: 360px;
}

.log-viewer-overlay-hint {
  font-size: 13px;
  color: #909399;
}

.log-viewer-preparing {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 0;
}

.preparing-text {
  color: #606266;
  font-size: 14px;
}
</style>

<style>
/* 全局样式：CSS Highlight API 伪元素 */
::highlight(ticket-log-context-highlight) {
  color: #111827;
  background: #fde047;
}

/* LogViewerDialog 弹窗全屏高度适配 */
.ticket-log-viewer-dialog .el-dialog__body {
  position: relative;
  height: calc(100vh - 56px);
  overflow: hidden;
}
</style>
