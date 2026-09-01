<template>
  <div class="log-memory-chart">
    <el-alert
      v-if="!metrics || !metrics.total"
      type="info"
      show-icon
      :closable="false"
      :title="emptyText"
    />
    <template v-else>
      <div class="log-memory-summary">
        <el-tag type="info">数据点 {{ metrics.total }}</el-tag>
        <el-tag v-if="metrics.truncated" type="warning">已降采样</el-tag>
        <el-tag v-if="metrics.skippedLineCount" type="danger">跳过解析失败 {{ metrics.skippedLineCount }} 行</el-tag>
        <el-tag>时间 {{ formatTime(metrics.startTime) }} ~ {{ formatTime(metrics.endTime) }}</el-tag>
        <el-tag type="primary">内存 {{ metrics.memMbMin }} ~ {{ metrics.memMbMax }} Mb</el-tag>
        <el-tag type="warning">CPU {{ metrics.cpuPercentMin }}% ~ {{ metrics.cpuPercentMax }}%</el-tag>
        <el-tag type="success">线程 {{ metrics.threadsActiveMin }} ~ {{ metrics.threadsActiveMax }}</el-tag>
      </div>
      <div ref="memoryChartRef" class="log-memory-chart-canvas" />
      <div ref="cpuChartRef" class="log-memory-chart-canvas" />
      <div ref="threadsChartRef" class="log-memory-chart-canvas" />
    </template>
  </div>
</template>

<script setup>
/**
 * 工单日志内存分析图表组件。
 *
 * 使用 ECharts 渲染日志中 Process cpu/mem/threads 资源监控数据的
 * 内存曲线、CPU 曲线和线程曲线，数据由日志查看器弹窗负责加载。
 *
 * 联动能力：
 * - 点击曲线数据点回抛 point-click 事件（携带 file/line/time/epoch），由父组件跳转日志上下文；
 * - 暴露 highlightTime(epochMs)，父组件点击日志行时在曲线上按时间就近画标记线。
 */
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  /** 内存分析结果数据，包含 points 数据点与汇总信息 */
  metrics: { type: Object, default: null },
  /** 无数据时的提示文案 */
  emptyText: { type: String, default: '暂无内存监控数据' },
})

const emit = defineEmits(['point-click'])

const memoryChartRef = ref(null)
const cpuChartRef = ref(null)
const threadsChartRef = ref(null)
let memoryChart = null
let cpuChart = null
let threadsChart = null
// 当前反向联动标记时间（毫秒 epoch），重渲染时保持
let highlightEpochMs = null

/** 将后端时间（epoch 秒优先，兼容 ISO 字符串）格式化为 HH:mm:ss 展示。 */
function formatTime(value) {
  if (value === null || value === undefined || value === '') return '-'
  let date
  if (typeof value === 'number') {
    // epoch 秒 -> 毫秒
    date = new Date(value < 1e12 ? value * 1000 : value)
  } else {
    date = new Date(value)
  }
  if (!date || Number.isNaN(date.getTime())) return String(value)
  const pad = (item) => String(item).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

/** 取数据点展示时间标签：优先 epoch（跨端解析安全），回退 ISO 字符串。 */
function pointTimeLabel(point) {
  if (point.epoch) return formatTime(point.epoch)
  return formatTime(point.time)
}

/** 构建三张图表共享的 X 轴时间列表。 */
function buildTimeAxis() {
  return (props.metrics?.points || []).map((point) => pointTimeLabel(point))
}

/** 构建单张折线图配置，series 由调用方传入。 */
function buildOption(times, seriesList) {
  return {
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) => (value === null || value === undefined ? '-' : value),
    },
    legend: { top: 0 },
    grid: { left: 64, right: 32, top: 32, bottom: 56 },
    xAxis: {
      type: 'category',
      data: times,
      boundaryGap: false,
      axisLabel: { rotate: 30 },
    },
    yAxis: { type: 'value', scale: true },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', height: 18, bottom: 8 },
    ],
    series: seriesList,
  }
}

/**
 * 找到与目标时间（毫秒 epoch）最接近的数据点下标。
 * @param {number} epochMs 目标时间毫秒值
 * @returns {number} 最接近的数据点下标，无数据时返回 -1
 */
function findNearestIndex(epochMs) {
  const points = props.metrics?.points || []
  if (!points.length || !Number.isFinite(Number(epochMs))) return -1
  const target = Number(epochMs)
  let nearest = -1
  let minDelta = Infinity
  points.forEach((point, index) => {
    const pointMs = Number(point.epoch) ? Number(point.epoch) * 1000 : Date.parse(point.time)
    if (!Number.isFinite(pointMs)) return
    const delta = Math.abs(pointMs - target)
    if (delta < minDelta) {
      minDelta = delta
      nearest = index
    }
  })
  return nearest
}

/**
 * 反向联动：在所有曲线上按时间就近画标记线；重复调用会先清除旧标记。
 * @param {number} epochMs 目标时间毫秒值（来自日志行的解析时间）
 * @returns {void} 无返回值
 */
function highlightTime(epochMs) {
  const index = findNearestIndex(epochMs)
  disposeMarkLines()
  if (index < 0) return
  const points = props.metrics?.points || []
  highlightEpochMs = Number(points[index].epoch) ? Number(points[index].epoch) * 1000 : Date.parse(points[index].time)
  const label = pointTimeLabel(points[index])
  const markLine = {
    symbol: 'none',
    silent: true,
    lineStyle: { color: '#F56C6C', type: 'dashed', width: 1.5 },
    label: { formatter: `行 ${points[index].line || '-'}`, position: 'insideEndTop' },
    data: [{ xAxis: label }],
  }
  memoryChart?.setOption({ series: [{ markLine }] })
  cpuChart?.setOption({ series: [{ markLine }] })
  threadsChart?.setOption({ series: [{ markLine }] })
}

/** 清除所有图表上的标记线。 */
function disposeMarkLines() {
  highlightEpochMs = null
  const empty = { series: [{ markLine: { data: [] } }] }
  memoryChart?.setOption(empty)
  cpuChart?.setOption(empty)
  threadsChart?.setOption(empty)
}

/** 绑定图表点击事件：按 dataIndex 回抛数据点，供父组件跳转日志上下文。 */
function bindClickEvent(chart) {
  if (!chart) return
  chart.off('click')
  chart.on('click', (params) => {
    const points = props.metrics?.points || []
    const point = points[params.dataIndex]
    if (!point) return
    emit('point-click', {
      file: point.sourceFile || point.source_file || '',
      line: Number(point.line) || 0,
      time: point.time,
      epoch: Number(point.epoch) || 0,
    })
  })
}

/** 渲染内存、CPU、线程三张图表。 */
function renderCharts() {
  const points = props.metrics?.points || []
  if (!points.length) return
  const times = buildTimeAxis()
  nextTick(() => {
    // 内存曲线：绝对占用（Mb）与占用百分比双轴展示
    if (memoryChartRef.value) {
      memoryChart = memoryChart || echarts.init(memoryChartRef.value)
      memoryChart.setOption({
        ...buildOption(times, [
          {
            name: '内存 (Mb)',
            type: 'line',
            showSymbol: false,
            sampling: 'lttb',
            data: points.map((point) => point.memMb),
            lineStyle: { width: 1.5, color: '#2196F3' },
            areaStyle: { opacity: 0.12, color: '#2196F3' },
          },
          {
            name: '内存 (%)',
            type: 'line',
            showSymbol: false,
            sampling: 'lttb',
            yAxisIndex: 1,
            data: points.map((point) => point.memPercent),
            lineStyle: { width: 1, type: 'dashed', color: '#9E9E9E' },
          },
        ]),
        legend: { top: 0 },
        yAxis: [
          { type: 'value', scale: true, name: 'Mb' },
          { type: 'value', scale: true, name: '%', position: 'right' },
        ],
      }, { notMerge: true })
      bindClickEvent(memoryChart)
    }
    // CPU 曲线
    if (cpuChartRef.value) {
      cpuChart = cpuChart || echarts.init(cpuChartRef.value)
      cpuChart.setOption(buildOption(times, [
        {
          name: 'CPU (%)',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          data: points.map((point) => point.cpuPercent),
          lineStyle: { width: 1.5, color: '#FF9800' },
          areaStyle: { opacity: 0.12, color: '#FF9800' },
        },
      ]), { notMerge: true })
      bindClickEvent(cpuChart)
    }
    // 线程曲线：活跃线程与线程上限
    if (threadsChartRef.value) {
      threadsChart = threadsChart || echarts.init(threadsChartRef.value)
      threadsChart.setOption(buildOption(times, [
        {
          name: '活跃线程',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          data: points.map((point) => point.threadsActive),
          lineStyle: { width: 1.5, color: '#4CAF50' },
        },
        {
          name: '线程上限',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          data: points.map((point) => point.threadsMax),
          lineStyle: { width: 1, type: 'dashed', color: '#9E9E9E' },
        },
      ]), { notMerge: true })
      bindClickEvent(threadsChart)
    }
    // 重渲染后如存在反向联动标记，恢复标记线
    if (highlightEpochMs) {
      const keep = highlightEpochMs
      highlightEpochMs = null
      highlightTime(keep)
    }
  })
}

/** 销毁图表实例，避免弹窗反复开关后残留监听。 */
function disposeCharts() {
  memoryChart?.dispose()
  cpuChart?.dispose()
  threadsChart?.dispose()
  memoryChart = null
  cpuChart = null
  threadsChart = null
  highlightEpochMs = null
}

/** 供外部在容器尺寸变化后重绘图表。 */
function resizeCharts() {
  memoryChart?.resize()
  cpuChart?.resize()
  threadsChart?.resize()
}

defineExpose({ resizeCharts, highlightTime })

watch(
  () => props.metrics,
  (value) => {
    if (value && value.total) {
      renderCharts()
    } else {
      disposeCharts()
    }
  },
  { deep: false }
)

// 挂载时如果数据已就绪也主动渲染一次：
// 数据先到、组件后挂载（如弹窗内成功态停留结束后才显示图表）的场景下，
// watch 不会再次触发，必须在挂载完成后补一次渲染，否则画布空白
onMounted(() => {
  if (props.metrics && props.metrics.total) {
    renderCharts()
  }
})

onBeforeUnmount(disposeCharts)
</script>

<style scoped>
.log-memory-chart {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.log-memory-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.log-memory-chart-canvas {
  width: 100%;
  height: 240px;
}
</style>
