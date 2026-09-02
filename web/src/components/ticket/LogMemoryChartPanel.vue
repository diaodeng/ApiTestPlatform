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
 * - X 轴为真实时间轴（type: 'time'，数据用 epoch 毫秒），降采样后点间距不均
 *   也不会造成时间视觉失真，跨天数据可正常展示日期；
 * - 点击图表任意位置（曲线、时间线、网格空白）通过 zr 全局点击 + convertFromPixel
 *   换算目标时间并就近匹配数据点，回抛 point-click 事件（携带 file/line/time/epoch），
 *   由父组件跳转日志上下文；点击 legend / dataZoom 等组件区域不触发跳转；
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
// 三个图表共享同一份数据点缓存（epoch 毫秒），渲染时构建一次，点击就近匹配直接复用
let cachedPointMsList = []

/** 将后端时间（epoch 秒优先，兼容 ISO 字符串）格式化为展示文本。 */
function formatTime(value, withDate = false) {
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
  const timeText = `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  if (!withDate) return timeText
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${timeText}`
}

/** 取数据点毫秒 epoch：优先 epoch 字段，回退 ISO 字符串解析。 */
function pointEpochMs(point) {
  if (Number(point.epoch)) return Number(point.epoch) * 1000
  const parsed = Date.parse(point.time)
  return Number.isFinite(parsed) ? parsed : NaN
}

/** 构建共享数据点缓存：epoch 毫秒列表（时间升序，由后端保证）。 */
function buildPointCache() {
  cachedPointMsList = (props.metrics?.points || []).map((point) => pointEpochMs(point))
}

/**
 * 找到与目标时间（毫秒 epoch）最接近的数据点下标（二分查找）。
 * @param {number} epochMs 目标时间毫秒值
 * @returns {number} 最接近的数据点下标，无数据时返回 -1
 */
function findNearestIndex(epochMs) {
  const points = props.metrics?.points || []
  if (!points.length || !Number.isFinite(Number(epochMs))) return -1
  const target = Number(epochMs)
  let low = 0
  let high = cachedPointMsList.length - 1
  if (target <= cachedPointMsList[0]) return 0
  if (target >= cachedPointMsList[high]) return high
  while (low <= high) {
    const mid = (low + high) >> 1
    const midMs = cachedPointMsList[mid]
    if (midMs === target) return mid
    if (midMs < target) {
      low = mid + 1
    } else {
      high = mid - 1
    }
  }
  // low/high 交叉后，比较两侧邻居取更近者
  const before = Math.max(0, Math.min(low, cachedPointMsList.length - 1))
  const after = Math.max(0, before - 1)
  const deltaBefore = Math.abs(cachedPointMsList[before] - target)
  const deltaAfter = Math.abs(cachedPointMsList[after] - target)
  return deltaBefore <= deltaAfter ? before : after
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
  highlightEpochMs = cachedPointMsList[index]
  const markLine = {
    symbol: 'none',
    silent: true,
    lineStyle: { color: '#F56C6C', type: 'dashed', width: 1.5 },
    label: {
      formatter: `行 ${points[index].line || '-'} · ${formatTime(highlightEpochMs)}`,
      position: 'insideEndTop',
    },
    // time 轴的 markLine 直接用毫秒值定位，不依赖 category 索引
    data: [{ xAxis: highlightEpochMs }],
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

/** 按下标回抛数据点点击事件，供父组件跳转日志上下文。 */
function emitPointClick(index) {
  const points = props.metrics?.points || []
  const point = points[index]
  if (!point) return
  emit('point-click', {
    file: point.sourceFile || point.source_file || '',
    line: Number(point.line) || 0,
    time: point.time,
    epoch: Number(point.epoch) || 0,
  })
}

/**
 * 绑定 zr 全局点击：点击图表任意位置（时间线、空白、曲线）都换算为时间并就近匹配数据点。
 * 只处理点击落在网格坐标系内的情形，legend / dataZoom / toolbox 等组件区域不触发跳转。
 * @param {object} chart ECharts 实例
 * @returns {void}
 */
function bindCanvasClick(chart) {
  if (!chart) return
  const zr = chart.getZr()
  if (!zr) return
  zr.off('click')
  zr.on('click', (event) => {
    // 命中图形元素（折线、symbol 等）时 event.target 存在且 topoi 为空；
    // 命中 legend/dataZoom 等组件时 ECharts 自己的 click 事件已处理或不需要处理，
    // 这里统一走坐标换算，但先确认像素点能转换为有效时间坐标
    if (event.target && event.target.eventData && event.target.eventData.componentType) {
      // 点到 legend / dataZoom / 标记线等组件元素时忽略，避免误跳转
      return
    }
    const pointInPixel = chart.convertFromPixel({ xAxisIndex: 0, yAxisIndex: 0 }, [event.offsetX, event.offsetY])
    if (!pointInPixel || !Number.isFinite(pointInPixel[0])) return
    const epochMs = pointInPixel[0]
    const index = findNearestIndex(epochMs)
    if (index >= 0) {
      emitPointClick(index)
    }
  })
}

/** 构建单张折线图配置（真实时间轴），series 由调用方传入。 */
function buildOption(seriesList) {
  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) => (value === null || value === undefined ? '-' : value),
    },
    legend: { top: 0 },
    grid: { left: 64, right: 32, top: 32, bottom: 56 },
    xAxis: {
      type: 'time',
      axisLabel: { hideOverlap: true },
    },
    yAxis: { type: 'value', scale: true },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, height: 18, bottom: 8 },
    ],
    series: seriesList,
  }
}

/** 渲染内存、CPU、线程三张图表。 */
function renderCharts() {
  const points = props.metrics?.points || []
  if (!points.length) return
  buildPointCache()
  nextTick(() => {
    // 内存曲线：绝对占用（Mb）与占用百分比双轴展示
    if (memoryChartRef.value) {
      memoryChart = memoryChart || echarts.init(memoryChartRef.value)
      memoryChart.setOption({
        ...buildOption([
          {
            name: '内存 (Mb)',
            type: 'line',
            showSymbol: false,
            sampling: 'lttb',
            data: points.map((point) => [pointEpochMs(point), point.memMb]),
            lineStyle: { width: 1.5, color: '#2196F3' },
            areaStyle: { opacity: 0.12, color: '#2196F3' },
          },
          {
            name: '内存 (%)',
            type: 'line',
            showSymbol: false,
            sampling: 'lttb',
            yAxisIndex: 1,
            data: points.map((point) => [pointEpochMs(point), point.memPercent]),
            lineStyle: { width: 1, type: 'dashed', color: '#9E9E9E' },
          },
        ]),
        legend: { top: 0 },
        yAxis: [
          { type: 'value', scale: true, name: 'Mb' },
          { type: 'value', scale: true, name: '%', position: 'right' },
        ],
      }, { notMerge: true })
      bindCanvasClick(memoryChart)
    }
    // CPU 曲线
    if (cpuChartRef.value) {
      cpuChart = cpuChart || echarts.init(cpuChartRef.value)
      cpuChart.setOption(buildOption([
        {
          name: 'CPU (%)',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          data: points.map((point) => [pointEpochMs(point), point.cpuPercent]),
          lineStyle: { width: 1.5, color: '#FF9800' },
          areaStyle: { opacity: 0.12, color: '#FF9800' },
        },
      ]), { notMerge: true })
      bindCanvasClick(cpuChart)
    }
    // 线程曲线：活跃线程与线程上限
    if (threadsChartRef.value) {
      threadsChart = threadsChart || echarts.init(threadsChartRef.value)
      threadsChart.setOption(buildOption([
        {
          name: '活跃线程',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          data: points.map((point) => [pointEpochMs(point), point.threadsActive]),
          lineStyle: { width: 1.5, color: '#4CAF50' },
        },
        {
          name: '线程上限',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          data: points.map((point) => [pointEpochMs(point), point.threadsMax]),
          lineStyle: { width: 1, type: 'dashed', color: '#9E9E9E' },
        },
      ]), { notMerge: true })
      bindCanvasClick(threadsChart)
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
  cachedPointMsList = []
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
