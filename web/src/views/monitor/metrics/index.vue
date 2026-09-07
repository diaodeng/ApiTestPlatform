<template>
  <div class="app-container metrics-collector-page">
    <div class="table-toolbar">
      <el-button v-hasPermi="['monitor:metrics_collector:add']" type="primary" icon="Plus" @click="openDialog()">新增采集服务</el-button>
      <el-button icon="Refresh" @click="loadAll">刷新状态</el-button>
    </div>

    <el-table v-loading="loading" :data="collectors" border>
      <el-table-column prop="profileId" label="ID" width="70" />
      <el-table-column prop="profileName" label="服务名称" min-width="140" show-overflow-tooltip />
      <el-table-column label="推送地址" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">{{ row.pushUrl || '-' }}</template>
      </el-table-column>
      <el-table-column label="标签 (job/instance)" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ row.jobLabel }} / {{ row.instanceLabel }}</template>
      </el-table-column>
      <el-table-column label="间隔" width="90" align="center">
        <template #default="{ row }">{{ row.intervalSeconds }}s</template>
      </el-table-column>
      <el-table-column label="扩展指标" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.extendedEnabled ? 'success' : 'info'" size="small">{{ row.extendedEnabled ? '开' : '关' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最近推送" width="170">
        <template #default="{ row }">
          <el-tag v-if="row.lastPushStatus === 'success'" type="success" size="small">成功</el-tag>
          <el-tag v-else-if="row.lastPushStatus === 'failed'" type="danger" size="small">
            失败{{ row.pushFailureCount ? `(${row.pushFailureCount})` : '' }}
          </el-tag>
          <el-tag v-else type="info" size="small">未推送</el-tag>
          <span class="push-time">{{ formatTime(row.lastPushTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="90" align="center">
        <template #default="{ row }">
          <el-switch
            v-model="row.enabled"
            v-hasPermi="['monitor:metrics_collector:edit']"
            :disabled="statusChanging[row.profileId]"
            @change="value => changeStatus(row, value)"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button v-hasPermi="['monitor:metrics_collector:remove']" link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-divider content-position="left">运行状态（当前进程）</el-divider>
    <el-descriptions :column="2" border size="small" class="runtime-desc">
      <el-descriptions-item v-for="item in runtime" :key="item.role" :label="roleLabel(item.role)">
        <el-tag :type="item.running ? 'success' : 'info'" size="small">{{ item.running ? '采集中' : '未运行' }}</el-tag>
        <span class="unit-text">PID {{ item.pid }}，生效通道 {{ (item.activeProfileIds || []).length }} 个</span>
      </el-descriptions-item>
    </el-descriptions>

    <el-divider content-position="left">内存诊断快照（RSS 阈值触发 tracemalloc）</el-divider>
    <el-form label-width="150px" size="small" class="snapshot-form">
      <el-form-item label="启用快照">
        <el-switch v-model="snapshotConfig.enabled" />
        <span class="unit-text">开启后每个进程的采集线程每 10 秒检查一次自身 RSS</span>
      </el-form-item>
      <el-form-item label="RSS 阈值 (MB)">
        <el-input-number v-model="snapshotConfig.rssThresholdMb" :min="128" :max="65536" :step="50" />
        <span class="unit-text">进程 RSS 超过该值时采样，建议略高于常驻基线</span>
      </el-form-item>
      <el-form-item label="Top 分配源条数">
        <el-input-number v-model="snapshotConfig.topLines" :min="10" :max="500" :step="10" />
        <span class="unit-text">快照记录的分配点数量（10-500）</span>
      </el-form-item>
      <el-form-item label="冷却时间 (秒)">
        <el-input-number v-model="snapshotConfig.cooldownSeconds" :min="60" :max="86400" :step="60" />
        <span class="unit-text">两次采样之间的最小间隔（60-86400）</span>
      </el-form-item>
      <el-form-item>
        <el-button v-hasPermi="['monitor:metrics_collector:edit']" type="primary" :loading="snapshotSaving" @click="saveSnapshotConfig">
          保存配置
        </el-button>
        <span v-if="snapshotConfig.updateTime" class="unit-text">
          最近更新：{{ formatTime(snapshotConfig.updateTime) }}{{ snapshotConfig.updateBy ? ` (${snapshotConfig.updateBy})` : '' }}
        </span>
      </el-form-item>
    </el-form>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="快照文件写入日志目录 logs/<日期>/memory_snapshot_<角色>_<时间戳>，用于事后归因。tracemalloc 追踪期间内存分配开销约 2 倍，诊断完成后建议关闭开关。"
    />

    <MetricsCollectorDialog ref="dialogRef" @saved="loadAll" />
  </div>
</template>

<script setup name="MetricsCollector">
import {
  changeMetricsCollectorStatus,
  delMetricsCollector,
  getMemorySnapshotConfig,
  getMetricsCollectorRuntime,
  listMetricsCollectors,
  updateMemorySnapshotConfig,
} from '@/api/system/metricsCollector'
import MetricsCollectorDialog from './components/MetricsCollectorDialog.vue'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const collectors = ref([])
const runtime = ref([])
const dialogRef = ref()
const statusChanging = reactive({})
const snapshotConfig = reactive({
  enabled: false,
  rssThresholdMb: 900,
  topLines: 50,
  cooldownSeconds: 3600,
  updateTime: null,
  updateBy: '',
})
const snapshotSaving = ref(false)
let statusTimer = null

const roleLabels = { api: 'API 服务', celery_worker: 'Celery Worker', celery_beat: 'Celery Beat' }
const roleLabel = role => roleLabels[role] || role

function formatTime(value) {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(5, 16)
}

function loadCollectors() {
  loading.value = true
  return listMetricsCollectors().then(response => { collectors.value = response.data || [] }).finally(() => { loading.value = false })
}

function loadRuntime() {
  return getMetricsCollectorRuntime().then(response => { runtime.value = response.data?.processes || [] }).catch(() => {})
}

function loadAll() {
  return Promise.all([loadCollectors(), loadRuntime(), loadSnapshotConfig()])
}

function loadSnapshotConfig() {
  return getMemorySnapshotConfig()
    .then(response => {
      const data = response.data || {}
      snapshotConfig.enabled = !!data.enabled
      snapshotConfig.rssThresholdMb = data.rssThresholdMb ?? 900
      snapshotConfig.topLines = data.topLines ?? 50
      snapshotConfig.cooldownSeconds = data.cooldownSeconds ?? 3600
      snapshotConfig.updateTime = data.updateTime || null
      snapshotConfig.updateBy = data.updateBy || ''
    })
    .catch(() => {})
}

function saveSnapshotConfig() {
  snapshotSaving.value = true
  updateMemorySnapshotConfig({
    enabled: snapshotConfig.enabled,
    rssThresholdMb: snapshotConfig.rssThresholdMb,
    topLines: snapshotConfig.topLines,
    cooldownSeconds: snapshotConfig.cooldownSeconds,
  })
    .then(response => {
      proxy.$modal.msgSuccess(response.msg || '保存成功')
      return loadSnapshotConfig()
    })
    .catch(() => {})
    .finally(() => { snapshotSaving.value = false })
}

function openDialog(row) {
  dialogRef.value?.open(row)
}

function changeStatus(row, enabled) {
  statusChanging[row.profileId] = true
  changeMetricsCollectorStatus(row.profileId, { enabled })
    .then(() => {
      proxy.$modal.msgSuccess(enabled ? '已启动，采集将在 5 秒内生效' : '已停止，指标推送将断流')
      return loadRuntime()
    })
    .catch(() => { row.enabled = !enabled })
    .finally(() => { statusChanging[row.profileId] = false })
}

function remove(row) {
  proxy.$modal.confirm(`确认删除采集服务「${row.profileName}」？运行中的通道会自动停止。`)
    .then(() => delMetricsCollector(row.profileId))
    .then(() => { proxy.$modal.msgSuccess('删除成功'); loadAll() })
    .catch(() => {})
}

loadAll()
// 运行状态与最近推送情况定时刷新
statusTimer = setInterval(loadRuntime, 15000)
onBeforeUnmount(() => { if (statusTimer) clearInterval(statusTimer) })
</script>

<style scoped>
.table-toolbar { display: flex; justify-content: flex-end; margin-bottom: 12px; gap: 8px; }
.push-time { margin-left: 6px; color: var(--el-text-color-secondary); font-size: 12px; }
.runtime-desc { margin-top: 4px; }
.unit-text { color: var(--el-text-color-secondary); font-size: 12px; margin-left: 8px; }
.snapshot-form { max-width: 720px; margin-top: 4px; }
</style>
