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

    <MetricsCollectorDialog ref="dialogRef" @saved="loadAll" />
  </div>
</template>

<script setup name="MetricsCollector">
import {
  changeMetricsCollectorStatus,
  delMetricsCollector,
  getMetricsCollectorRuntime,
  listMetricsCollectors,
} from '@/api/system/metricsCollector'
import MetricsCollectorDialog from './components/MetricsCollectorDialog.vue'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const collectors = ref([])
const runtime = ref([])
const dialogRef = ref()
const statusChanging = reactive({})
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
  return Promise.all([loadCollectors(), loadRuntime()])
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
</style>
