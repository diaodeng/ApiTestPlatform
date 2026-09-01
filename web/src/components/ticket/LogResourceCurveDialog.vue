<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="86%"
    top="4vh"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    class="log-resource-curve-dialog"
  >
    <div v-loading="loading" class="log-resource-curve-body">
      <el-alert v-if="error" type="error" show-icon :closable="false" :title="error" class="mb8" />
      <!-- 上半：资源曲线（复用内存分析图表组件，支持缩放/tooltip/点击联动） -->
      <LogMemoryChartPanel
        ref="chartPanelRef"
        :metrics="metrics"
        empty-text="当前日志拉取记录中未找到 Process 资源监控数据"
        @point-click="handlePointJump"
      />
      <!-- 下半：解析出的数据点列表（分页），点击行同样联动跳转日志 -->
      <template v-if="points.length">
        <el-divider content-position="left">资源数据点（{{ points.length }} 条）</el-divider>
        <el-table
          :data="pagedPoints"
          size="small"
          height="280"
          highlight-current-row
          @row-click="handleRowClick"
        >
          <el-table-column label="时间" prop="timeText" width="170" show-overflow-tooltip />
          <el-table-column label="文件" prop="sourceFile" min-width="220" show-overflow-tooltip />
          <el-table-column label="行号" prop="line" width="90" align="center" />
          <el-table-column label="CPU(%)" prop="cpuPercent" width="100" align="center" />
          <el-table-column label="内存(%)" prop="memPercent" width="100" align="center" />
          <el-table-column label="内存(Mb)" prop="memMb" width="110" align="center" />
          <el-table-column label="活跃线程" prop="threadsActive" width="100" align="center" />
          <el-table-column label="线程上限" prop="threadsMax" width="100" align="center" />
        </el-table>
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="points.length"
          layout="total, prev, pager, next"
          class="mt8"
        />
      </template>
    </div>
    <!-- 点击曲线点/列表行时打开完整日志查看器并跳转对应行 -->
    <LogViewerDialog ref="viewerRef" v-model="viewerVisible" :record="viewerRecord" />
  </el-dialog>
</template>

<script setup>
/**
 * 日志拉取记录 - 资源曲线弹窗。
 *
 * 从日志拉取记录管理页入口打开，对该记录全局扫描 Process 资源监控数据：
 * 上半部分用 ECharts 绘制内存/CPU/线程曲线，下半部分展示结构化数据点列表；
 * 点击曲线点或列表行会打开完整日志查看器并跳转到对应日志行上下文。
 */
import { computed, nextTick, ref, watch } from 'vue'
import { getTicketLogMemoryMetrics } from '@/api/ticket/ticket'
import LogMemoryChartPanel from '@/components/ticket/LogMemoryChartPanel.vue'
import LogViewerDialog from '@/components/ticket/LogViewerDialog.vue'

const props = defineProps({
  /** 控制弹窗可见性 */
  modelValue: { type: Boolean, default: false },
  /** 日志拉取记录对象，需包含 id、ticketId、ticketNo、title */
  record: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const dialogTitle = computed(() => {
  const ticketNo = String(props.record?.ticketNo || '').trim()
  const label = ticketNo ? ` - ${ticketNo}` : ''
  return `资源曲线（Process 资源监控）${label}`
})

const loading = ref(false)
const metrics = ref(null)
const error = ref('')
const chartPanelRef = ref(null)
// 数据点列表分页状态
const page = ref(1)
const pageSize = 50
// 日志查看器联动状态
const viewerVisible = ref(false)
const viewerRecord = ref(null)
const viewerRef = ref(null)

const points = computed(() => metrics.value?.points || [])
const pagedPoints = computed(() => {
  const start = (page.value - 1) * pageSize
  return points.value.slice(start, start + pageSize).map((point) => ({
    ...point,
    timeText: formatPointTime(point),
  }))
})

/** 将数据点时间（epoch 秒优先）格式化为 yyyy-MM-dd HH:mm:ss。 */
function formatPointTime(point) {
  let date
  if (Number(point.epoch)) {
    date = new Date(Number(point.epoch) * 1000)
  } else {
    date = new Date(point.time)
  }
  if (!date || Number.isNaN(date.getTime())) return String(point.time || '-')
  const pad = (item) => String(item).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  )
}

/** 打开弹窗时自动加载该记录的资源监控数据（全局扫描，不带文件过滤）。 */
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    loadMetrics()
  }
)

/** 加载当前记录的资源监控数据点。 */
async function loadMetrics() {
  const recordId = props.record?.id
  if (!recordId) return
  loading.value = true
  error.value = ''
  metrics.value = null
  page.value = 1
  try {
    const response = await getTicketLogMemoryMetrics({
      ticketId: props.record?.ticketId || 0,
      recordId,
      maxPoints: 2000,
    })
    metrics.value = response?.data || null
  } catch (err) {
    error.value = String(err?.message || err || '资源数据加载失败')
    metrics.value = null
  } finally {
    loading.value = false
  }
}

/**
 * 曲线点/列表行点击联动：打开完整日志查看器并跳转到对应行上下文。
 * @param {{ file: string, line: number }} payload 文件与行号
 * @returns {void} 无返回值
 */
function handlePointJump(payload) {
  const file = String(payload?.file || '')
  const line = Number(payload?.line) || 0
  if (!file || !line || !props.record?.id) return
  viewerRecord.value = {
    id: props.record.id,
    ticketId: props.record.ticketId || 0,
    ticketNo: props.record.ticketNo || '',
    title: props.record.title || props.record.ticketTitle || '',
  }
  viewerVisible.value = true
  // 等查看器弹窗挂载后直接跳转目标行上下文
  nextTick(() => {
    viewerRef.value?.jumpToContext(file, line)
  })
}

/** 列表行点击：复用曲线点跳转逻辑。 */
function handleRowClick(row) {
  handlePointJump({ file: row.sourceFile, line: row.line })
}
</script>

<style scoped>
.log-resource-curve-body {
  min-height: 240px;
}

.mb8 { margin-bottom: 8px; }
.mt8 { margin-top: 8px; }
</style>
