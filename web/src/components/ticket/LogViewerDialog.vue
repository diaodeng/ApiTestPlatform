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
        <el-checkbox v-model="form.ignoreCase">忽略大小写</el-checkbox>
        <el-checkbox v-model="form.wordRegexp">整词搜索</el-checkbox>
        <el-button type="primary" :loading="searching" @click="searchKeyword">搜索</el-button>
        <el-select
          v-model="form.files"
          class="log-file-scope-select"
          multiple
          collapse-tags
          collapse-tags-tooltip
          clearable
          filterable
          placeholder="全局搜索（可多选）"
        >
          <el-option v-for="file in fileOptions" :key="file" :label="file" :value="file" />
        </el-select>
        <el-button v-if="form.files.length" link type="primary" @click="clearFileScope">清除文件范围</el-button>
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
        <el-button type="success" :loading="memoryLoading" @click="toggleMemoryPanel">内存分析</el-button>
      </div>

      <!-- 内存分析面板：展示日志中 Process cpu/mem/threads 监控曲线 -->
      <div v-if="memoryPanelVisible" class="log-view-panel mb16">
        <div class="panel-header mb8 log-view-panel-header">
          <span>内存分析（Process 资源监控）</span>
          <div class="panel-inline">
            <el-button link type="primary" :loading="memoryLoading" @click="loadMemoryMetrics">刷新</el-button>
            <el-button link type="primary" @click="memoryPanelVisible = false">关闭</el-button>
          </div>
        </div>
        <div>
          <!-- 解析中：实时展示扫描进度、当前文件、已提取点数、耗时与预计剩余时间 -->
          <div v-if="memoryLoading" class="log-memory-progress">
            <el-progress
              :percentage="memoryProgressPercent"
              :stroke-width="14"
              striped
              striped-flow
            />
            <div class="log-memory-progress-text">
              <span v-if="memoryProgress.fileCount">
                正在解析日志 {{ memoryProgress.fileIndex }}/{{ memoryProgress.fileCount }}：{{ memoryProgress.file }}
              </span>
              <span v-else>正在准备内存分析任务…</span>
              <span>已提取 {{ memoryProgress.points }} 条监控数据</span>
              <span>已耗时 {{ memoryElapsedText }}</span>
              <span v-if="memoryEtaText" class="log-memory-eta">{{ memoryEtaText }}</span>
            </div>
          </div>
          <template v-else>
            <el-alert
              v-if="memoryError"
              type="error"
              show-icon
              :closable="false"
              :title="memoryError"
            />
            <LogMemoryChartPanel
              v-else
              :metrics="memoryMetrics"
              :empty-text="memoryMetrics?.message || '当前日志中未找到 Process 资源监控数据'"
            />
          </template>
        </div>
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
            <el-input-number
              v-model="contextJumpLine"
              class="log-context-jump-input"
              :min="1"
              :max="context.totalLines || 1"
              controls-position="right"
              @keyup.enter="jumpToContextLine"
            />
            <el-button
              icon="Position"
              link
              type="primary"
              title="跳转指定行"
              :disabled="searching"
              @click="jumpToContextLine"
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
        <div
          ref="contextBlockRef"
          v-show="contextViewMode !== 'minimized'"
          :class="['log-content-block', 'log-context-block', { 'log-content-wrap': wrapEnabled }]"
          @mouseup="handleContextSelection"
          @keyup="handleContextSelection"
        >
          <template v-for="item in contextDisplayLines" :key="`${item.file}:${item.line}`">
            <span class="log-context-line"><span class="log-context-line-no">{{ item.paddedLine }}</span><span v-if="item.contentTruncated && !isLineExpanded(item)" class="log-context-line-content"><template v-for="(part, partIndex) in item.parts" :key="partIndex"><mark v-if="part.highlight" :class="['log-context-highlight', part.highlightClass]">{{ part.text }}</mark><span v-else>{{ part.text }}</span></template> <button class="log-line-expand-btn" @click="expandLine(item)">展开完整内容（{{ formatFileSize(item.contentLength) }}）</button></span><span v-else-if="item.contentTruncated && isLineExpanded(item)" class="log-context-line-content log-context-line-content-ph">[已展开，见下方]</span><span v-else class="log-context-line-content"><template v-for="(part, partIndex) in item.parts" :key="partIndex"><mark v-if="part.highlight" :class="['log-context-highlight', part.highlightClass]">{{ part.text }}</mark><span v-else>{{ part.text }}</span></template></span></span>
            <div v-if="item.contentTruncated && isLineExpanded(item)" :class="['log-line-expanded-block', { 'log-line-expanded-block-fullwidth': getExpandedMode(item) === 'fullwidth', 'log-line-expanded-block-fullscreen': getExpandedMode(item) === 'fullscreen' }]">
              <div class="log-line-expanded-header">
                <span class="log-line-expanded-title">完整内容 · {{ item.file }}:{{ item.line }}</span>
                <div class="log-line-expanded-actions">
                  <button class="log-line-action-btn" @click="copyLineContent(item)" :title="isCopySuccess(item) ? '已复制' : '复制内容'">
                    {{ isCopySuccess(item) ? '✓ 已复制' : '复制' }}
                  </button>
                  <button v-if="getExpandedMode(item) !== 'fullwidth'" class="log-line-action-btn" @click="toggleExpandedMode(item, 'fullwidth')" title="全宽阅读">全宽</button>
                  <button v-else class="log-line-action-btn log-line-action-btn-active" @click="toggleExpandedMode(item, 'normal')" title="还原宽度">还原</button>
                  <button v-if="getExpandedMode(item) !== 'fullscreen'" class="log-line-action-btn" @click="toggleExpandedMode(item, 'fullscreen')" title="全屏阅读">全屏</button>
                  <button v-else class="log-line-action-btn log-line-action-btn-active" @click="toggleExpandedMode(item, 'normal')" title="退出全屏">退出全屏</button>
                  <button class="log-line-collapse-btn" @click="collapseLine(item)">收起</button>
                </div>
              </div>
              <pre class="log-line-expanded-content">{{ getExpandedContent(item) }}</pre>
            </div>
          </template>
        </div>
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
  getTicketLogLineContent,
  streamTicketLogMemoryMetrics,
} from '@/api/ticket/ticket'
import { useLogPrepareProgress } from '@/views/ticket/hooks/useLogPrepareProgress'
import LogMemoryChartPanel from './LogMemoryChartPanel.vue'

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
// ── 内存分析状态 ──
const memoryPanelVisible = ref(false)
const memoryLoading = ref(false)
const memoryMetrics = ref(null)
const memoryError = ref('')
// ── 内存分析进度状态 ──
const memoryProgress = ref({ percent: 0, file: '', fileIndex: 0, fileCount: 0, points: 0 })
const memoryElapsedSeconds = ref(0)
const memoryElapsedTimer = ref(null)
const memoryAbortController = ref(null)
const memoryProgressPercent = computed(() =>
  Math.min(99, Math.max(1, Math.round(Number(memoryProgress.value.percent) || 0)))
)
const memoryElapsedText = computed(() => formatMemoryDuration(memoryElapsedSeconds.value))
const memoryEtaText = computed(() => {
  const percent = Number(memoryProgress.value.percent) || 0
  if (percent < 3) return ''
  const etaSeconds = (memoryElapsedSeconds.value / percent) * (100 - percent)
  if (!Number.isFinite(etaSeconds) || etaSeconds <= 0) return ''
  return `预计剩余 ${formatMemoryDuration(etaSeconds)}`
})

/** 将秒数格式化为“x 秒 / x 分 y 秒”的可读文案。 */
function formatMemoryDuration(seconds) {
  const value = Math.max(0, Math.round(Number(seconds) || 0))
  if (value < 60) return `${value} 秒`
  return `${Math.floor(value / 60)} 分 ${value % 60} 秒`
}

/** 启动内存分析耗时计时器。 */
function startMemoryElapsedTimer() {
  stopMemoryElapsedTimer()
  const startedAt = Date.now()
  memoryElapsedSeconds.value = 0
  memoryElapsedTimer.value = window.setInterval(() => {
    memoryElapsedSeconds.value = (Date.now() - startedAt) / 1000
  }, 500)
}

/** 停止内存分析耗时计时器。 */
function stopMemoryElapsedTimer() {
  if (memoryElapsedTimer.value) {
    window.clearInterval(memoryElapsedTimer.value)
    memoryElapsedTimer.value = null
  }
}

/** 中止进行中的内存分析请求并清理计时器。 */
function abortMemoryAnalysis() {
  memoryAbortController.value?.abort()
  memoryAbortController.value = null
  stopMemoryElapsedTimer()
}
const hasFullscreenPanel = computed(
  () => resultViewMode.value === 'fullscreen' || contextViewMode.value === 'fullscreen'
    || hasExpandedFullscreen.value
)

const hasExpandedFullscreen = computed(() =>
  Object.values(expandedModeMap.value).includes('fullscreen')
)

const { width: windowWidth, height: windowHeight } = useWindowSize()

// ── 搜索表单 ──
const form = ref({
  keywords: '',
  searchMode: 'any',
  files: [],
  ignoreCase: false,
  wordRegexp: false,
  contextLines: 20,
  limit: 500,
})
const contextJumpLine = ref(1)
const resultSortOrder = ref('')

// ── 高亮状态 ──
const highlightKeywords = ref([])
const highlightText = ref('')
const highlightSummary = computed(() => highlightKeywords.value.join('、'))
const selectionHighlightKeyword = ref('')
const selectionHighlightOwned = ref(false)
const contextBlockRef = ref(null)

const highlightNamePrefix = 'ticket-log-context-highlight'
const highlightColorCount = 20
const highlightNativeNames = Array.from({ length: highlightColorCount }, (_, index) =>
  `${highlightNamePrefix}-${index}`
)
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
    contentLength: item.contentLength || 0,
    contentTruncated: item.contentTruncated || false,
    parts: nativeHighlightSupported.value
      ? [{ text: item.content || '', highlight: false }]
      : splitHighlightParts(item.content || ''),
  }))
})

// ── 超大行展开/收起状态 ──
const expandedLineMap = ref({})
const loadingLineSet = ref(new Set())
const expandedModeMap = ref({})
const copySuccessMap = ref({})

/**
 * 生成展开行的唯一标识键。
 * @param {{ file: string, line: number }} item 上下文行
 * @returns {string} 唯一键
 */
function expandedLineKey(item) {
  return `${item.file}:${item.line}`
}

/**
 * 判断指定行是否已展开完整内容。
 * @param {{ file: string, line: number }} item 上下文行
 * @returns {boolean} 是否已展开
 */
function isLineExpanded(item) {
  const key = expandedLineKey(item)
  return key in expandedLineMap.value
}

/**
 * 获取已展开行的完整内容。
 * @param {{ file: string, line: number }} item 上下文行
 * @returns {string} 完整内容
 */
function getExpandedContent(item) {
  const key = expandedLineKey(item)
  return expandedLineMap.value[key] || ''
}

/**
 * 格式化文件大小。
 * @param {number} bytes 字节数
 * @returns {string} 可读大小
 */
function formatFileSize(bytes) {
  const size = Number(bytes || 0)
  if (size <= 0) return '0 B'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(2)} MB`
}

/**
 * 展开截断行，请求后端获取完整内容。
 * @param {{ file: string, line: number }} item 上下文行
 * @returns {Promise<void>}
 */
async function expandLine(item) {
  const key = expandedLineKey(item)
  if (key in expandedLineMap.value || loadingLineSet.value.has(key)) return
  loadingLineSet.value.add(key)
  try {
    const ticketId = props.record?.ticketId || 0
    const recordId = props.record?.id
    const response = await getTicketLogLineContent({
      ticket_id: ticketId,
      record_id: recordId,
      file: item.file,
      line: item.line,
    })
    expandedLineMap.value = { ...expandedLineMap.value, [key]: typeof response === 'string' ? response : (response?.data || '') }
  } catch {
    // 加载失败时静默处理，不展开
  } finally {
    loadingLineSet.value.delete(key)
  }
}

/**
 * 收起已展开的超大行。
 * @param {{ file: string, line: number }} item 上下文行
 */
function collapseLine(item) {
  const key = expandedLineKey(item)
  const next = { ...expandedLineMap.value }
  delete next[key]
  expandedLineMap.value = next
  const nextMode = { ...expandedModeMap.value }
  delete nextMode[key]
  expandedModeMap.value = nextMode
  const nextCopy = { ...copySuccessMap.value }
  delete nextCopy[key]
  copySuccessMap.value = nextCopy
}

/**
 * 获取当前行的展开模式。
 * @param {{ file: string, line: number }} item 上下文行
 * @returns {'normal'|'fullwidth'|'fullscreen'} 展开模式
 */
function getExpandedMode(item) {
  return expandedModeMap.value[expandedLineKey(item)] || 'normal'
}

/**
 * 切换当前行的展开模式。
 * @param {{ file: string, line: number }} item 上下文行
 * @param {'normal'|'fullwidth'|'fullscreen'} mode 目标模式
 */
function toggleExpandedMode(item, mode) {
  expandedModeMap.value = { ...expandedModeMap.value, [expandedLineKey(item)]: mode }
}

/**
 * 复制展开行的完整内容到剪贴板。
 * @param {{ file: string, line: number }} item 上下文行
 * @returns {Promise<void>}
 */
async function copyLineContent(item) {
  const key = expandedLineKey(item)
  const content = getExpandedContent(item)
  if (!content) return
  try {
    await navigator.clipboard.writeText(content)
    copySuccessMap.value = { ...copySuccessMap.value, [key]: true }
    setTimeout(() => {
      const next = { ...copySuccessMap.value }
      delete next[key]
      copySuccessMap.value = next
    }, 2000)
  } catch {
    // 复制失败静默处理
  }
}

/**
 * 判断指定行复制是否成功（用于显示"已复制"反馈）。
 * @param {{ file: string, line: number }} item 上下文行
 * @returns {boolean} 是否复制成功
 */
function isCopySuccess(item) {
  return !!copySuccessMap.value[expandedLineKey(item)]
}

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

const RESULT_COLUMN_DEFAULT_WIDTHS = {
  file: 140,
  line: 90,
  content: 360,
  actions: 130,
}

const RESULT_COLUMN_MIN_WIDTHS = {
  file: 120,
  line: 80,
  content: 260,
  actions: 120,
}

const resultColumnWidths = ref({ ...RESULT_COLUMN_DEFAULT_WIDTHS })
const resultColumnResizeState = ref(null)

function renderHitTextCell(className, value, style) {
  const text = String(value ?? '')
  return h('span', { class: className, style, title: text }, text)
}

/**
 * 从日志命中行提取可显示、可排序的时间；没有标准时间时保留为空。
 * @param {string} content 日志命中行内容
 * @returns {{ text: string, value: number|null }} 日志时间文本与时间戳
 */
function extractLogTime(content) {
  const text = String(content || '')
  const dateTimeMatch = text.match(/\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2}[ T]\d{1,2}:\d{2}:\d{2}(?:[,.]\d{1,6})?)/)
  const timeMatch = text.match(/\b(\d{1,2}:\d{2}:\d{2}(?:[,.]\d{1,6})?)/)
  const matched = dateTimeMatch?.[1] || timeMatch?.[1] || ''
  if (!matched) return { text: '', value: null }
  const normalized = dateTimeMatch
    ? matched.replace(/\//g, '-').replace(',', '.').replace(' ', 'T')
    : `1970-01-01T${matched.replace(',', '.')}`
  const value = Date.parse(normalized)
  return { text: matched, value: Number.isFinite(value) ? value : null }
}

/**
 * 获取当前结果列宽，并在缺省时回退到默认值。
 * @param {keyof typeof RESULT_COLUMN_DEFAULT_WIDTHS} columnKey 列键
 * @returns {number} 当前列宽
 */
function getResultColumnWidth(columnKey) {
  return Number(resultColumnWidths.value[columnKey] || RESULT_COLUMN_DEFAULT_WIDTHS[columnKey] || 0)
}

/**
 * 将列宽限制在安全范围内，避免拖拽后列完全消失。
 * @param {keyof typeof RESULT_COLUMN_DEFAULT_WIDTHS} columnKey 列键
 * @param {number} width 目标宽度
 * @returns {number} 修正后的列宽
 */
function clampResultColumnWidth(columnKey, width) {
  const minWidth = Number(RESULT_COLUMN_MIN_WIDTHS[columnKey] || 80)
  return Math.max(Math.round(Number(width) || minWidth), minWidth)
}

/**
 * 返回当前时间排序箭头，未排序时显示中性箭头。
 * @returns {string} 排序箭头
 */
function getResultSortIndicator() {
  if (resultSortOrder.value === 'asc') return '▲'
  if (resultSortOrder.value === 'desc') return '▼'
  return '↕'
}

/**
 * 开始拖动结果表列宽，仅更新当前列宽状态，不改动命中数据。
 * @param {PointerEvent} event 指针按下事件
 * @param {keyof typeof RESULT_COLUMN_DEFAULT_WIDTHS} columnKey 列键
 * @returns {void}
 */
function startResultColumnResize(event, columnKey) {
  // Pointer Events 同时覆盖鼠标、触控板和触摸屏；只允许鼠标左键开始调整。
  if (!columnKey || (event.pointerType === 'mouse' && event.button !== 0)) return
  event.preventDefault()
  event.stopPropagation()
  resultColumnResizeState.value = {
    columnKey,
    startX: Number(event.clientX || 0),
    startWidth: getResultColumnWidth(columnKey),
  }

  // 捕获指针，防止拖动过快离开手柄后丢失 move / up 事件。
  event.currentTarget?.setPointerCapture?.(event.pointerId)
  document.body.classList.add('log-viewer-column-resizing')
  window.addEventListener('pointermove', handleResultColumnResize)
  window.addEventListener('pointerup', stopResultColumnResize)
  window.addEventListener('pointercancel', stopResultColumnResize)
}

/**
 * 在拖拽过程中实时更新列宽；虚拟表格仅重算列配置，性能影响有限。
 * @param {PointerEvent} event 指针移动事件
 * @returns {void}
 */
function handleResultColumnResize(event) {
  const state = resultColumnResizeState.value
  if (!state) return
  const deltaX = Number(event.clientX || 0) - state.startX
  const nextWidth = clampResultColumnWidth(state.columnKey, state.startWidth + deltaX)
  resultColumnWidths.value = {
    ...resultColumnWidths.value,
    [state.columnKey]: nextWidth,
  }
}

/** 停止列宽拖拽并清理全局事件。 */
function stopResultColumnResize() {
  if (!resultColumnResizeState.value) return
  resultColumnResizeState.value = null
  document.body.classList.remove('log-viewer-column-resizing')
  window.removeEventListener('pointermove', handleResultColumnResize)
  window.removeEventListener('pointerup', stopResultColumnResize)
  window.removeEventListener('pointercancel', stopResultColumnResize)
}

/**
 * 渲染带可选排序入口和列宽拖拽手柄的表头。
 * @param {{ title: string, columnKey: keyof typeof RESULT_COLUMN_DEFAULT_WIDTHS, sortable?: boolean }} options 表头配置
 * @returns {import('vue').VNode} 表头节点
 */
function renderResultHeader(options) {
  const { title, columnKey, sortable = false } = options
  const titleNode = sortable
    ? h(
        'span',
        {
          class: 'log-hit-sort-header',
          role: 'button',
          tabindex: 0,
          title: '点击按日志时间切换升序或降序',
          'aria-label': '切换日志时间排序',
          onClick: toggleLogTimeSort,
          onKeydown: (event) => {
            if (event.key !== 'Enter' && event.key !== ' ') return
            event.preventDefault()
            toggleLogTimeSort()
          },
        },
        [
          h('span', title),
          h('span', { class: 'log-hit-sort-indicator' }, getResultSortIndicator()),
        ]
      )
    : h('span', { class: 'log-hit-header-title', title }, title)
  const resizeHandle =
    columnKey === 'actions'
      ? null
      : h('span', {
          class: 'log-hit-resize-handle',
          role: 'separator',
          title: '拖动调整列宽',
          'aria-label': '拖动调整' + title + '列宽',
          onPointerdown: (event) => startResultColumnResize(event, columnKey),
        })
  return h('div', { class: 'log-hit-header-cell' }, [titleNode, resizeHandle])
}

const resultTableColumns = computed(() => [
  {
    key: 'file',
    dataKey: 'file',
    title: '文件',
    width: getResultColumnWidth('file'),
    minWidth: RESULT_COLUMN_MIN_WIDTHS.file,
    headerCellRenderer: () => renderResultHeader({ title: '文件', columnKey: 'file' }),
    cellRenderer: ({ rowData }) => renderHitTextCell('log-hit-cell log-hit-cell-file', rowData.file),
  },
  {
    key: 'line',
    dataKey: 'line',
    title: '行号',
    width: getResultColumnWidth('line'),
    minWidth: RESULT_COLUMN_MIN_WIDTHS.line,
    align: 'center',
    headerCellRenderer: () => renderResultHeader({ title: '行号', columnKey: 'line' }),
    cellRenderer: ({ rowData }) => renderHitTextCell('log-hit-cell log-hit-cell-line', rowData.line),
  },
  {
    key: 'content',
    dataKey: 'content',
    title: '日志内容',
    width: getResultColumnWidth('content'),
    minWidth: RESULT_COLUMN_MIN_WIDTHS.content,
    flexGrow: 1,
    headerCellRenderer: () =>
      renderResultHeader({ title: '日志内容', columnKey: 'content', sortable: true }),
    cellRenderer: ({ rowData }) =>
      renderHitTextCell(
        'log-hit-cell log-hit-cell-content',
        `${String(rowData.content ?? '')}${rowData.contentTruncated ? '...' : ''}`,
        {
          display: 'inline-block',
          maxWidth: '100%',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          verticalAlign: 'top',
        }
      ),
  },
  {
    key: 'actions',
    title: '操作',
    width: getResultColumnWidth('actions'),
    minWidth: RESULT_COLUMN_MIN_WIDTHS.actions,
    fixed: 'right',
    align: 'center',
    headerCellRenderer: () => renderResultHeader({ title: '操作', columnKey: 'actions' }),
    cellRenderer: ({ rowData }) =>
      h(
        'el-button',
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
])
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
  form.value.files = []
  form.value.ignoreCase = false
  form.value.wordRegexp = false
  contextJumpLine.value = 1
  resultSortOrder.value = ''
  resultColumnWidths.value = { ...RESULT_COLUMN_DEFAULT_WIDTHS }
  stopResultColumnResize()
  clearHighlight()
  resultViewMode.value = 'normal'
  contextViewMode.value = 'normal'
  wrapEnabled.value = false
  expandedLineMap.value = {}
  loadingLineSet.value.clear()
  expandedModeMap.value = {}
  copySuccessMap.value = {}
  memoryPanelVisible.value = false
  memoryLoading.value = false
  memoryMetrics.value = null
  memoryError.value = ''
  abortMemoryAnalysis()
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
 * 切换内存分析面板显示，首次展开时自动加载当前记录的监控数据。
 * @returns {void} 无返回值
 */
function toggleMemoryPanel() {
  memoryPanelVisible.value = !memoryPanelVisible.value
  if (memoryPanelVisible.value) {
    if (!memoryMetrics.value) {
      loadMemoryMetrics()
    }
  } else {
    abortMemoryAnalysis()
  }
}

/**
 * 加载当前日志拉取记录的进程资源监控数据，用于内存分析图表。
 * @returns {void} 无返回值
 */
function loadMemoryMetrics() {
  const ticketId = props.record?.ticketId || 0
  const recordId = props.record?.id
  if (!recordId) return
  // 中止上一次未完成的分析，避免旧事件写入新一轮进度
  abortMemoryAnalysis()
  const controller = new AbortController()
  memoryAbortController.value = controller
  memoryLoading.value = true
  memoryError.value = ''
  memoryMetrics.value = null
  memoryProgress.value = { percent: 0, file: '', fileIndex: 0, fileCount: 0, points: 0 }
  startMemoryElapsedTimer()
  const finishLoading = () => {
    if (memoryAbortController.value === controller) {
      memoryAbortController.value = null
    }
    stopMemoryElapsedTimer()
    memoryLoading.value = false
  }
  streamTicketLogMemoryMetrics(
    { ticketId, recordId, maxPoints: 2000 },
    {
      signal: controller.signal,
      onStart: (event) => {
        memoryProgress.value = {
          ...memoryProgress.value,
          fileCount: Number(event?.fileCount) || 0,
        }
      },
      onProgress: (event) => {
        memoryProgress.value = {
          percent: Number(event?.percent) || 0,
          file: String(event?.file || ''),
          fileIndex: Number(event?.fileIndex) || 0,
          fileCount: Number(event?.fileCount) || memoryProgress.value.fileCount,
          points: Number(event?.points) || 0,
        }
      },
      onResult: (data) => {
        memoryMetrics.value = data
        finishLoading()
      },
    }
  )
    .catch((error) => {
      // 用户主动中止（关闭面板/刷新）不算错误
      if (error?.name === 'AbortError') return
      memoryError.value = String(error?.message || error || '内存分析数据加载失败')
      memoryMetrics.value = null
      finishLoading()
    })
    .finally(() => {
      if (memoryLoading.value) {
        finishLoading()
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
/**
 * 归一化日志搜索关键字，并将搜索关键字上限提升到 20 个。
 * @param {unknown} value 搜索关键字输入
 * @returns {string[]} 去重后的搜索关键字列表
 */
function normalizeSearchKeywords(value) {
  const rawItems = Array.isArray(value) ? value : String(value || '').split(/[\n,，;；]+/)
  const keywords = []
  rawItems.forEach((item) => {
    const keyword = String(item || '').trim()
    if (keyword && !keywords.includes(keyword)) {
      keywords.push(keyword.slice(0, 200))
    }
  })
  return keywords.slice(0, 20)
}

/**
 * 归一化高亮关键字，最多保留 20 个，避免一次性高亮过多关键词影响阅读与渲染。
 * @param {unknown} value 高亮关键字输入
 * @returns {string[]} 去重后的高亮关键字列表
 */
function normalizeHighlightKeywords(value) {
  const rawItems = Array.isArray(value) ? value : String(value || '').split(/[\n,，;；]+/)
  const keywords = []
  rawItems.forEach((item) => {
    const keyword = String(item || '').trim()
    if (keyword && !keywords.includes(keyword)) {
      keywords.push(keyword.slice(0, 200))
    }
  })
  return keywords.slice(0, 20)
}

/**
 * 归一化上下文高亮关键字，保留输入顺序但会在渲染前按长度降序匹配。
 * @returns {{ keyword: string, keywordIndex: number }[]} 可用于高亮渲染的关键字条目
 */
function getHighlightKeywordEntries() {
  return Array.from(new Set(highlightKeywords.value || []))
    .map((item, keywordIndex) => ({
      keyword: String(item || '').trim(),
      keywordIndex,
    }))
    .filter((item) => item.keyword)
    .sort(
      (left, right) =>
        right.keyword.length - left.keyword.length || left.keywordIndex - right.keywordIndex
    )
}
/**
 * 归一化已选搜索文件，保留选择顺序并去除空项。
 * @param {unknown} value 文件选择值
 * @returns {string[]} 可安全提交的相对文件路径列表
 */
function normalizeSelectedFiles(value) {
  const files = []
  const rawFiles = Array.isArray(value) ? value : [value]
  rawFiles.forEach((item) => {
    const file = String(item || '').trim()
    if (file && !files.includes(file)) files.push(file)
  })
  return files
}

// ── 搜索 ──
function searchKeyword() {
  const keywords = normalizeSearchKeywords(form.value.keywords)
  const files = normalizeSelectedFiles(form.value.files)
  if (!keywords.length) {
    if (files.length) {
      hits.value = []
      context.value = null
      errorSummary.value = null
      contextJumpLine.value = 1
      resultSortOrder.value = ''
      loadContext(files[0], 1)
    }
    return
  }
  form.value.keywords = keywords.join('\n')
  syncHighlightKeywords(keywords)
  searching.value = true
  const contextLines = Number(form.value.contextLines || 0)
  const limit = Math.min(Math.max(Number(form.value.limit || 500), 1), 5000)
  const payload = {
    ticketId: props.record?.ticketId || 0,
    recordId: props.record?.id,
    keywords,
    searchMode: String(form.value.searchMode || 'any').trim().toLowerCase() === 'all' ? 'all' : 'any',
    files,
    ignoreCase: Boolean(form.value.ignoreCase),
    wordRegexp: Boolean(form.value.wordRegexp),
    contextBefore: contextLines,
    contextAfter: contextLines,
    limit,
    withContext: false,
  }
  searchTicketLogs(payload)
    .then((response) => {
      setHits(response?.data || [])
    })
    .finally(() => {
      searching.value = false
    })
}

function setHits(rows = []) {
  hits.value = rows.map((item, index) => {
    const logTime = extractLogTime(item.content)
    return {
      ...item,
      hitKey: `${item.file || ''}:${item.line || 0}:${index}`,
      hitSortIndex: index,
      logTime: logTime.text,
      logTimeValue: logTime.value,
    }
  })
  context.value = null
  contextJumpLine.value = 1
  resultSortOrder.value = ''
  if (hits.value.length === 1) {
    selectHit(hits.value[0])
  }
}

function selectHit(row) {
  if (!row) return
  ensureSearchKeywordsHighlighted()
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
      contextJumpLine.value = Number(context.value?.line || line || 1)
      expandedLineMap.value = {}
      loadingLineSet.value.clear()
      expandedModeMap.value = {}
      copySuccessMap.value = {}
    })
    .finally(() => {
      searching.value = false
    })
}

/**
 * 跳转当前上下文文件的指定行，并沿用当前上下文行数设置。
 * @returns {void}
 */
function jumpToContextLine() {
  const file = String(context.value?.file || '').trim()
  const line = Math.max(Math.floor(Number(contextJumpLine.value || 1)), 1)
  if (!file) return
  loadContext(file, line)
}

/**
 * 合并当前搜索词到高亮输入框，保留已有的手工或选区高亮词。
 * @returns {void}
 */
function ensureSearchKeywordsHighlighted() {
  const searchKeywords = normalizeSearchKeywords(form.value.keywords)
  const missingKeywords = searchKeywords.filter((keyword) => !highlightKeywords.value.includes(keyword))
  if (!missingKeywords.length) return
  syncHighlightKeywords([...highlightKeywords.value, ...missingKeywords])
}

/**
 * 切换当前已加载日志结果的时间排序方向，不触发新的日志搜索。
 * @returns {void}
 */
function toggleLogTimeSort() {
  resultSortOrder.value = resultSortOrder.value === 'asc' ? 'desc' : 'asc'
  const direction = resultSortOrder.value === 'asc' ? 1 : -1
  hits.value = [...hits.value].sort((left, right) => {
    const leftValue = left.logTimeValue
    const rightValue = right.logTimeValue
    if (!Number.isFinite(leftValue) && !Number.isFinite(rightValue)) return left.hitSortIndex - right.hitSortIndex
    if (!Number.isFinite(leftValue)) return 1
    if (!Number.isFinite(rightValue)) return -1
    return (leftValue - rightValue) * direction || left.hitSortIndex - right.hitSortIndex
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
  form.value.files = normalizeSelectedFiles([file])
  searchKeyword()
}
function clearFileScope() {
  form.value.files = []
}

// ── 高亮 ──
function syncHighlightKeywords(value) {
  const keywords = normalizeHighlightKeywords(value)
  highlightKeywords.value = keywords
  highlightText.value = keywords.join('\n')
}

function updateHighlightKeywords(value) {
  // 用户输入触发：只更新高亮关键词数组，不回写 highlightText
  // 避免 normalizeHighlightKeywords 去掉尾部换行导致光标跳转，使回车换行失效
  const keywords = normalizeHighlightKeywords(value)
  const selectedKw = selectionHighlightKeyword.value
  if (selectedKw && !keywords.includes(selectedKw)) {
    keywords.push(selectedKw)
    syncHighlightKeywords(keywords)
    return
  }
  highlightKeywords.value = keywords
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
    return normalizeHighlightKeywords(highlightKeywords.value)
  }
  return normalizeHighlightKeywords(highlightKeywords.value).filter((kw) => kw !== selectedKw)
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
  highlightNativeNames.forEach((highlightName) => {
    window.CSS.highlights.delete(highlightName)
  })
}

function buildHighlightRanges(textNode, keywordEntries, rangesByKeywordIndex) {
  const text = textNode.textContent || ''
  let cursor = 0
  let hasMatch = false
  while (cursor < text.length) {
    let nextMatch = null
    keywordEntries.forEach((entry) => {
      const index = text.indexOf(entry.keyword, cursor)
      if (index < 0) return
      if (
        !nextMatch ||
        index < nextMatch.index ||
        (index === nextMatch.index && entry.keyword.length > nextMatch.keyword.length)
      ) {
        nextMatch = {
          index,
          keyword: entry.keyword,
          keywordIndex: entry.keywordIndex,
        }
      }
    })
    if (!nextMatch) break
    const range = new window.Range()
    range.setStart(textNode, nextMatch.index)
    range.setEnd(textNode, nextMatch.index + nextMatch.keyword.length)
    rangesByKeywordIndex[nextMatch.keywordIndex].push(range)
    hasMatch = true
    cursor = nextMatch.index + nextMatch.keyword.length
  }
  return hasMatch
}

function refreshNativeHighlights() {
  if (!nativeHighlightSupported.value) return
  const block = contextBlockRef.value
  const keywordEntries = getHighlightKeywordEntries()
  if (!block || !keywordEntries.length || contextViewMode.value === 'minimized') {
    clearNativeHighlights()
    return
  }
  const rangesByKeywordIndex = Array.from({ length: highlightColorCount }, () => [])
  let hasRanges = false
  block.querySelectorAll('.log-context-line-content').forEach((contentNode) => {
    const walker = document.createTreeWalker(contentNode, window.NodeFilter.SHOW_TEXT)
    let textNode = walker.nextNode()
    while (textNode) {
      if (buildHighlightRanges(textNode, keywordEntries, rangesByKeywordIndex)) {
        hasRanges = true
      }
      textNode = walker.nextNode()
    }
  })
  if (!hasRanges) {
    clearNativeHighlights()
    return
  }
  clearNativeHighlights()
  rangesByKeywordIndex.forEach((ranges, index) => {
    if (!ranges.length) return
    window.CSS.highlights.set(
      highlightNativeNames[index],
      new window.Highlight(...ranges)
    )
  })
}

// ── 回退 DOM mark 高亮 ──
function splitHighlightParts(content) {
  const text = String(content || '')
  const keywords = getHighlightKeywordEntries()
  if (!keywords.length) return [{ text, highlight: false }]
  const parts = []
  let cursor = 0
  while (cursor < text.length) {
    let nextMatch = null
    keywords.forEach((entry) => {
      const index = text.indexOf(entry.keyword, cursor)
      if (index < 0) return
      if (
        !nextMatch ||
        index < nextMatch.index ||
        (index === nextMatch.index && entry.keyword.length > nextMatch.keyword.length)
      ) {
        nextMatch = {
          index,
          keyword: entry.keyword,
          keywordIndex: entry.keywordIndex,
        }
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
      highlightClass: `log-context-highlight-${nextMatch.keywordIndex % highlightColorCount}`,
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
    return
  }
  if (contextViewMode.value === 'fullscreen') {
    contextViewMode.value = 'normal'
    return
  }
  // 退出展开块的全屏模式
  const fullscreenKey = Object.entries(expandedModeMap.value).find(([, v]) => v === 'fullscreen')
  if (fullscreenKey) {
    expandedModeMap.value = { ...expandedModeMap.value, [fullscreenKey[0]]: 'normal' }
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
  stopResultColumnResize()
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

.log-context-jump-input {
  width: 132px;
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
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.55;
}

.log-content-wrap {
  /* 换行开关由子元素 .log-context-line-content 控制，见下方 */
}

.log-context-line {
  display: block;
  white-space: nowrap;
  overflow: visible;
  line-height: 1.55;
  min-height: 0;
  margin: 0;
  padding: 0;
}

.log-content-wrap .log-context-line {
  white-space: normal;
  overflow: visible;
}

.log-context-line-no {
  display: inline-block;
  user-select: none;
  color: #64748b;
  vertical-align: baseline;
  min-width: 6ch;
}

.log-context-line-content {
  display: inline;
  vertical-align: baseline;
  white-space: pre;
}

.log-content-wrap .log-context-line-content {
  white-space: pre-wrap;
  word-break: break-word;
}

.log-context-line-content-ph {
  color: #94a3b8;
  font-style: italic;
  font-size: 11px;
}

.log-line-expand-btn {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 8px;
  border: 1px solid #f59e0b;
  border-radius: 3px;
  background: #fef3c7;
  color: #92400e;
  font-size: 11px;
  font-family: inherit;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  vertical-align: middle;
  line-height: 1.4;
}

.log-line-expand-btn:hover {
  background: #fde68a;
  border-color: #d97706;
}

.log-line-expanded-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-left: 6ch;
  max-width: calc(100% - 6ch);
  padding: 12px 14px;
  border: 1px solid #f59e0b;
  border-radius: 8px;
  background: #1e293b;
  box-sizing: border-box;
  max-height: 58vh;
  overflow: auto;
  contain: content;
}

.log-line-expanded-block-fullwidth {
  margin-left: 0;
  max-width: 100%;
}

.log-line-expanded-block-fullscreen {
  position: fixed;
  inset: 16px;
  z-index: 3500;
  margin-left: 0;
  max-width: none;
  max-height: none;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}

.log-line-expanded-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex: none;
}

.log-line-expanded-title {
  color: #fbbf24;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1 1 auto;
  min-width: 0;
}

.log-line-expanded-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: none;
}

.log-line-action-btn {
  padding: 2px 10px;
  border: 1px solid #475569;
  border-radius: 4px;
  background: #334155;
  color: #cbd5e1;
  font-size: 11px;
  font-family: inherit;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  line-height: 1.5;
  transition: background 0.15s, border-color 0.15s;
}

.log-line-action-btn:hover {
  background: #475569;
  border-color: #94a3b8;
  color: #f1f5f9;
}

.log-line-action-btn-active {
  background: #1e40af;
  border-color: #3b82f6;
  color: #bfdbfe;
}

.log-line-action-btn-active:hover {
  background: #1e3a8a;
  border-color: #60a5fa;
  color: #dbeafe;
}

.log-line-expanded-content {
  margin: 0;
  padding: 10px 12px;
  min-width: 100%;
  box-sizing: border-box;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.7;
  color: #e2e8f0;
  background: #0f172a;
  border-radius: 6px;
  font-family: inherit;
}

.log-line-collapse-btn {
  display: inline-block;
  flex: none;
  padding: 1px 8px;
  border: 1px solid #64748b;
  border-radius: 3px;
  background: #334155;
  color: #cbd5e1;
  font-size: 11px;
  font-family: inherit;
  cursor: pointer;
  user-select: none;
}

.log-line-collapse-btn:hover {
  background: #475569;
  color: #f1f5f9;
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
/*
 * el-table-v2 在 Element Plus 子组件内部调用 headerCellRenderer/cellRenderer。
 * 这类回调生成的 VNode 不会稳定携带本组件的 scoped 标记，拖动手柄样式若写在
 * <style scoped> 中会失效，最终表现为没有竖向分隔条、鼠标没有 col-resize 光标。
 * 因此这里使用弹窗类名作为作用域，既确保样式能命中动态单元格，也不影响其他表格。
 */
.ticket-log-viewer-dialog .log-hit-row {
  cursor: pointer;
}

.ticket-log-viewer-dialog .log-hit-cell {
  display: block;
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ticket-log-viewer-dialog .log-hit-cell-line {
  text-align: center;
}

.ticket-log-viewer-dialog .log-hit-header-cell {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  height: 24px;
  padding-right: 10px;
  gap: 4px;
}

.ticket-log-viewer-dialog .log-hit-header-title {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ticket-log-viewer-dialog .log-hit-sort-header {
  display: inline-flex;
  flex: 1 1 auto;
  align-items: center;
  gap: 4px;
  min-width: 0;
  height: 24px;
  cursor: pointer;
  user-select: none;
}

.ticket-log-viewer-dialog .log-hit-sort-header:focus-visible {
  outline: 2px solid #409eff;
  outline-offset: -2px;
}

.ticket-log-viewer-dialog .log-hit-sort-indicator {
  color: #909399;
  font-size: 11px;
}

/* 手柄脱离表头 Flex 布局，避免最小高度把虚拟表格表头撑高。 */
.ticket-log-viewer-dialog .log-hit-resize-handle {
  position: absolute;
  top: 50%;
  right: 0;
  width: 12px;
  height: 22px;
  min-height: 0;
  cursor: col-resize !important;
  touch-action: none;
  user-select: none;
  transform: translateY(-50%);
}

/* 仅保留紧凑的 1px、16px 高分隔线；12px 宽的透明区域仍可稳定拖动。 */
.ticket-log-viewer-dialog .log-hit-resize-handle::before {
  position: absolute;
  top: 3px;
  bottom: 3px;
  left: 50%;
  width: 1px;
  content: '';
  pointer-events: none;
  background: #d0d5dd;
  border-radius: 1px;
  transform: translateX(-50%);
  transition: background-color 0.16s ease, width 0.16s ease;
}

.ticket-log-viewer-dialog .log-hit-resize-handle:hover::before,
.ticket-log-viewer-dialog .log-hit-resize-handle:focus-visible::before {
  width: 2px;
  background: #409eff;
}

body.log-viewer-column-resizing,
body.log-viewer-column-resizing * {
  cursor: col-resize !important;
  user-select: none !important;
}

.ticket-log-viewer-dialog .log-hit-action-btn {
  padding: 0;
  border: 0;
  background: transparent;
  color: #409eff;
  cursor: pointer;
  font: inherit;
}

.ticket-log-viewer-dialog .log-hit-action-btn:hover {
  text-decoration: underline;
}

/* 全局样式：CSS Highlight API 伪元素 */
::highlight(ticket-log-context-highlight-0) { color: #111827; background: #fde68a; }
::highlight(ticket-log-context-highlight-1) { color: #111827; background: #bfdbfe; }
::highlight(ticket-log-context-highlight-2) { color: #111827; background: #bbf7d0; }
::highlight(ticket-log-context-highlight-3) { color: #111827; background: #fecaca; }
::highlight(ticket-log-context-highlight-4) { color: #111827; background: #ddd6fe; }
::highlight(ticket-log-context-highlight-5) { color: #111827; background: #fed7aa; }
::highlight(ticket-log-context-highlight-6) { color: #111827; background: #a7f3d0; }
::highlight(ticket-log-context-highlight-7) { color: #111827; background: #bae6fd; }
::highlight(ticket-log-context-highlight-8) { color: #111827; background: #fbcfe8; }
::highlight(ticket-log-context-highlight-9) { color: #111827; background: #c7d2fe; }
::highlight(ticket-log-context-highlight-10) { color: #111827; background: #fcd34d; }
::highlight(ticket-log-context-highlight-11) { color: #111827; background: #93c5fd; }
::highlight(ticket-log-context-highlight-12) { color: #111827; background: #86efac; }
::highlight(ticket-log-context-highlight-13) { color: #111827; background: #fda4af; }
::highlight(ticket-log-context-highlight-14) { color: #111827; background: #d8b4fe; }
::highlight(ticket-log-context-highlight-15) { color: #111827; background: #fdba74; }
::highlight(ticket-log-context-highlight-16) { color: #111827; background: #6ee7b7; }
::highlight(ticket-log-context-highlight-17) { color: #111827; background: #7dd3fc; }
::highlight(ticket-log-context-highlight-18) { color: #111827; background: #f9a8d4; }
::highlight(ticket-log-context-highlight-19) { color: #111827; background: #ecfccb; }
/* LogViewerDialog 弹窗全屏高度适配 */
.ticket-log-viewer-dialog .el-dialog__body {
  position: relative;
  height: calc(100vh - 56px);
  overflow: hidden;
}

/* 内存分析面板：实时进度区 */
.ticket-log-viewer-dialog .log-memory-progress {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 0;
}

.ticket-log-viewer-dialog .log-memory-progress-text {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  color: #606266;
  font-size: 13px;
}

.ticket-log-viewer-dialog .log-memory-eta {
  color: #409eff;
}
</style>
