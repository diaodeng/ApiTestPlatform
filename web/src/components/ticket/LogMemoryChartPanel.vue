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
 */
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  /** 内存分析结果数据，包含 points 数据点与汇总信息 */
  metrics: { type: Object, default: null },
  /** 无数据时的提示文案 */
  emptyText: { type: String, default: '暂无内存监控数据' },
})

const memoryChartRef = ref(null)
const cpuChartRef = ref(null)
const threadsChartRef = ref(null)
let memoryChart = null
let cpuChart = null
let threadsChart = null

/** 将后端 ISO 时间格式化为 HH:mm:ss 展示。 */
function formatTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (item) => String(item).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

/** 构建三张图表共享的 X 轴时间列表。 */
function buildTimeAxis() {
  return (props.metrics?.points || []).map((point) => formatTime(point.time))
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
            data: points.map((point) => point.memMb),
            lineStyle: { width: 1.5, color: '#2196F3' },
            areaStyle: { opacity: 0.12, color: '#2196F3' },
          },
          {
            name: '内存 (%)',
            type: 'line',
            showSymbol: false,
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
    }
    // CPU 曲线
    if (cpuChartRef.value) {
      cpuChart = cpuChart || echarts.init(cpuChartRef.value)
      cpuChart.setOption(buildOption(times, [
        {
          name: 'CPU (%)',
          type: 'line',
          showSymbol: false,
          data: points.map((point) => point.cpuPercent),
          lineStyle: { width: 1.5, color: '#FF9800' },
          areaStyle: { opacity: 0.12, color: '#FF9800' },
        },
      ]), { notMerge: true })
    }
    // 线程曲线：活跃线程与线程上限
    if (threadsChartRef.value) {
      threadsChart = threadsChart || echarts.init(threadsChartRef.value)
      threadsChart.setOption(buildOption(times, [
        {
          name: '活跃线程',
          type: 'line',
          showSymbol: false,
          data: points.map((point) => point.threadsActive),
          lineStyle: { width: 1.5, color: '#4CAF50' },
        },
        {
          name: '线程上限',
          type: 'line',
          showSymbol: false,
          data: points.map((point) => point.threadsMax),
          lineStyle: { width: 1, type: 'dashed', color: '#9E9E9E' },
        },
      ]), { notMerge: true })
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
}

/** 供外部在容器尺寸变化后重绘图表。 */
function resizeCharts() {
  memoryChart?.resize()
  cpuChart?.resize()
  threadsChart?.resize()
}

defineExpose({ resizeCharts })

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
