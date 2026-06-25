<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true">
      <el-form-item label="时间范围">
        <el-date-picker
          v-model="dateRange"
          value-format="YYYY-MM-DD"
          type="daterange"
          range-separator="-"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
        />
      </el-form-item>
      <el-form-item label="项目">
        <el-select
          v-model="selectedProjectIds"
          multiple
          clearable
          collapse-tags
          collapse-tags-tooltip
          filterable
          placeholder="所属项目"
          style="width: 260px"
          @change="handleProjectChange"
        >
          <el-option
            v-for="item in projectOptions"
            :key="item.projectId"
            :label="item.projectName"
            :value="item.projectId"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="模块">
        <el-select
          v-model="selectedModuleIds"
          multiple
          clearable
          collapse-tags
          collapse-tags-tooltip
          filterable
          placeholder="所属模块"
          style="width: 280px"
        >
          <el-option
            v-for="item in moduleOptions"
            :key="`${item.projectId}-${item.moduleId}`"
            :label="formatModuleOptionLabel(item)"
            :value="item.moduleId"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="模块Code">
        <el-select
          v-model="selectedModuleCodes"
          multiple
          clearable
          collapse-tags
          collapse-tags-tooltip
          filterable
          placeholder="模块Code"
          style="width: 240px"
        >
          <el-option
            v-for="item in moduleCodeOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">查询</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
        <el-button icon="Setting" @click="blockConfigOpen = true">显示配置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="16" class="mb16">
      <el-col :span="6">
        <el-card shadow="never">
          <div class="metric-label">工单总数</div>
          <div class="metric-value">{{ overview.total || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="metric-label">平均处理耗时</div>
          <div class="metric-value">{{ formatSeconds(overview.avgProcessSeconds) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="metric-label">状态类型数</div>
          <div class="metric-value">{{ overview.statusCounts?.length || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="metric-label">涉及模块数</div>
          <div class="metric-value">{{ overview.moduleCounts?.length || 0 }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="stats-block-grid">
      <el-col v-for="block in visibleStatisticsBlocks" :key="block.key" :span="block.span" class="stats-block-col">
        <el-card shadow="never">
          <template #header>{{ block.title }}</template>
          <el-table v-loading="loading" :data="overview[block.dataKey] || []">
            <el-table-column :label="block.label">
              <template #default="scope">{{ block.format(scope.row) }}</template>
            </el-table-column>
            <el-table-column :label="block.countLabel" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog title="统计块显示配置" v-model="blockConfigOpen" width="560px" append-to-body>
      <el-checkbox-group v-model="visibleStatisticsBlockKeys" class="statistics-block-config">
        <el-checkbox v-for="item in statisticsBlockOptions" :key="item.key" :label="item.key">
          {{ item.title }}
        </el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="resetStatisticsBlockConfig">恢复默认</el-button>
        <el-button type="primary" @click="saveStatisticsBlockConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="TicketStatistics">
import {
  getTicketStatClassificationOptions,
  getTicketStatistics,
  listTicketModuleOptions,
  listTicketProjectOptions
} from '@/api/ticket/ticket'
import { getOptionLabel, sourceOptions, ticketStatusOptions } from '../constants'
import { getCurrentUserConfig, saveCurrentUserConfig } from '@/api/system/userConfig'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const dateRange = ref([])
const overview = ref({})
const projectOptions = ref([])
const moduleOptions = ref([])
const moduleCodeOptions = ref([])
const selectedProjectIds = ref([])
const selectedModuleIds = ref([])
const selectedModuleCodes = ref([])
const issueTypeOptions = ref([])
const rootCauseTypeOptions = ref([])
const solutionTypeOptions = ref([])
const resolutionOptions = ref([])
const blockConfigOpen = ref(false)
const queryParams = ref({
  beginTime: undefined,
  endTime: undefined
})

const statisticsBlockOptions = [
  {
    key: 'status',
    title: '状态分布',
    dataKey: 'statusCounts',
    label: '状态',
    countLabel: '数量',
    span: 8,
    format: row => getOptionLabel(ticketStatusOptions, row.status)
  },
  {
    key: 'module',
    title: '模块分布',
    dataKey: 'moduleCounts',
    label: '模块',
    countLabel: '数量',
    span: 8,
    format: row => row.module || '未填写'
  },
  {
    key: 'assignee',
    title: '人员处理量',
    dataKey: 'assigneeCounts',
    label: '处理人',
    countLabel: '数量',
    span: 8,
    format: row => row.userName || '未分配'
  },
  {
    key: 'category',
    title: '问题分类',
    dataKey: 'categoryCounts',
    label: '分类',
    countLabel: '数量',
    span: 8,
    format: row => row.category || '未填写'
  },
  {
    key: 'rootCause',
    title: '原因分类',
    dataKey: 'rootCauseCounts',
    label: '原因',
    countLabel: '数量',
    span: 8,
    format: row => row.rootCause || '未填写'
  },
  {
    key: 'transition',
    title: '状态流转',
    dataKey: 'transitionCounts',
    label: '流转',
    countLabel: '次数',
    span: 8,
    format: row => formatTransition(row)
  },
  {
    key: 'source',
    title: '来源分布',
    dataKey: 'sourceCounts',
    label: '来源',
    countLabel: '数量',
    span: 12,
    format: row => getOptionLabel(sourceOptions, row.source)
  },
  {
    key: 'priority',
    title: '内部优先级',
    dataKey: 'priorityCounts',
    label: '优先级',
    countLabel: '数量',
    span: 12,
    format: row => row.priority || '未填写'
  },
  {
    key: 'issueType',
    title: '工单类型',
    dataKey: 'issueTypeCounts',
    label: '类型',
    countLabel: '数量',
    span: 8,
    format: row => formatIssueType(row)
  },
  {
    key: 'problem',
    title: '是否真实问题',
    dataKey: 'problemCounts',
    label: '问题性质',
    countLabel: '数量',
    span: 8,
    format: row => formatProblemFlag(row.isProblem)
  },
  {
    key: 'rootCauseType',
    title: '根因分类',
    dataKey: 'rootCauseTypeCounts',
    label: '根因',
    countLabel: '数量',
    span: 8,
    format: row => getStatOptionLabel(rootCauseTypeOptions, row.rootCauseType)
  },
  {
    key: 'solutionType',
    title: '解决方式',
    dataKey: 'solutionTypeCounts',
    label: '方式',
    countLabel: '数量',
    span: 12,
    format: row => getStatOptionLabel(solutionTypeOptions, row.solutionType)
  },
  {
    key: 'resolution',
    title: '关闭结果',
    dataKey: 'resolutionCounts',
    label: '结果',
    countLabel: '数量',
    span: 12,
    format: row => formatResolution(row)
  }
]
const defaultStatisticsBlockKeys = statisticsBlockOptions.map(item => item.key)
const visibleStatisticsBlockKeys = ref([...defaultStatisticsBlockKeys])
const visibleStatisticsBlocks = computed(() => {
  const visibleKeys = new Set(visibleStatisticsBlockKeys.value)
  return statisticsBlockOptions.filter(item => visibleKeys.has(item.key))
})

function getStatistics() {
  loading.value = true
  getTicketStatistics(buildQueryParams()).then(response => {
    overview.value = response.data || {}
  }).finally(() => {
    loading.value = false
  })
}

function buildQueryParams() {
  return {
    ...queryParams.value,
    projectIds: selectedProjectIds.value.length ? selectedProjectIds.value.join(',') : undefined,
    moduleIds: selectedModuleIds.value.length ? selectedModuleIds.value.join(',') : undefined,
    moduleCodes: selectedModuleCodes.value.length ? selectedModuleCodes.value.join(',') : undefined
  }
}

function normalizeStatOptions(items = []) {
  return (Array.isArray(items) ? items : [])
    .map(item => ({
      value: String(item.value || item.code || '').trim(),
      label: String(item.label || item.name || item.value || item.code || '').trim()
    }))
    .filter(item => item.value)
}

function loadStatClassificationOptions() {
  getTicketStatClassificationOptions().then(response => {
    const config = response.data || {}
    issueTypeOptions.value = normalizeStatOptions(config.issueTypes)
    rootCauseTypeOptions.value = normalizeStatOptions(config.rootCauseTypes)
    solutionTypeOptions.value = normalizeStatOptions(config.solutionTypes)
    resolutionOptions.value = normalizeStatOptions(config.resolutions)
  })
}

function normalizeStatisticsBlockKeys(value) {
  const rawKeys = Array.isArray(value?.visibleBlocks) ? value.visibleBlocks : value
  const validKeys = new Set(statisticsBlockOptions.map(item => item.key))
  const normalized = (Array.isArray(rawKeys) ? rawKeys : defaultStatisticsBlockKeys)
    .map(item => String(item || '').trim())
    .filter(item => validKeys.has(item))
  return normalized.length ? normalized : [...defaultStatisticsBlockKeys]
}

function loadStatisticsBlockConfig() {
  return getCurrentUserConfig('ticket', 'ticket_statistics_blocks').then(response => {
    visibleStatisticsBlockKeys.value = normalizeStatisticsBlockKeys(response.data?.configValue)
  }).catch(() => {
    visibleStatisticsBlockKeys.value = [...defaultStatisticsBlockKeys]
  })
}

function saveStatisticsBlockConfig() {
  visibleStatisticsBlockKeys.value = normalizeStatisticsBlockKeys(visibleStatisticsBlockKeys.value)
  saveCurrentUserConfig({
    configType: 'ticket',
    configKey: 'ticket_statistics_blocks',
    configValue: {
      visibleBlocks: visibleStatisticsBlockKeys.value
    },
    remark: '工单统计页面显示块配置'
  }).then(() => {
    blockConfigOpen.value = false
    proxy.$modal.msgSuccess('保存成功')
  })
}

function resetStatisticsBlockConfig() {
  visibleStatisticsBlockKeys.value = [...defaultStatisticsBlockKeys]
}

function loadProjectOptions() {
  return listTicketProjectOptions().then(response => {
    projectOptions.value = response.data || []
  })
}

async function loadModuleOptions(projectIds = []) {
  const ids = Array.isArray(projectIds) ? projectIds.filter(Boolean) : []
  const requests = ids.length
    ? ids.map(projectId => listTicketModuleOptions({ projectId }))
    : [listTicketModuleOptions({})]
  const responses = await Promise.all(requests)
  const moduleMap = new Map()
  responses.forEach(response => {
    ;(response.data || []).forEach(item => {
      const key = `${item.projectId || ''}-${item.moduleId}`
      if (item.moduleId && !moduleMap.has(key)) {
        moduleMap.set(key, item)
      }
    })
  })
  moduleOptions.value = Array.from(moduleMap.values())
  moduleCodeOptions.value = buildModuleCodeOptions(moduleOptions.value)
  const validModuleIds = new Set(moduleOptions.value.map(item => item.moduleId))
  selectedModuleIds.value = selectedModuleIds.value.filter(moduleId => validModuleIds.has(moduleId))
  const validModuleCodes = new Set(moduleCodeOptions.value.map(item => item.value))
  selectedModuleCodes.value = selectedModuleCodes.value.filter(moduleCode => validModuleCodes.has(moduleCode))
}

function handleProjectChange(projectIds) {
  loadModuleOptions(projectIds)
}

function handleQuery() {
  queryParams.value.beginTime = dateRange.value?.[0]
  queryParams.value.endTime = dateRange.value?.[1]
  getStatistics()
}

function resetQuery() {
  dateRange.value = []
  selectedProjectIds.value = []
  selectedModuleIds.value = []
  selectedModuleCodes.value = []
  queryParams.value = { beginTime: undefined, endTime: undefined }
  loadModuleOptions([])
  getStatistics()
}

function formatSeconds(seconds) {
  if (!seconds) return '-'
  const hour = Math.floor(seconds / 3600)
  const minute = Math.floor((seconds % 3600) / 60)
  const second = seconds % 60
  return `${hour}小时${minute}分${second}秒`
}

function getStatOptionLabel(options, value) {
  const text = String(value || '').trim()
  if (!text || text === '未填写') {
    return '未填写'
  }
  const rows = Array.isArray(options) ? options : options.value || []
  return rows.find(item => item.value === text)?.label || text
}

function formatIssueType(row) {
  if (row.issueTypeName) {
    return row.issueTypeName
  }
  return getStatOptionLabel(issueTypeOptions, row.issueTypeId)
}

function formatProblemFlag(value) {
  if (value === true) return '真实问题'
  if (value === false) return '非问题'
  return '未填写'
}

function formatResolution(row) {
  if (row.resolutionName) {
    return row.resolutionName
  }
  return getStatOptionLabel(resolutionOptions, row.resolutionCode)
}

function formatModuleOptionLabel(item) {
  const project = projectOptions.value.find(projectItem => projectItem.projectId === item.projectId)
  return project?.projectName ? `${project.projectName} / ${item.moduleName}` : item.moduleName
}

function buildModuleCodeOptions(moduleItems = []) {
  const codeMap = new Map()
  ;(Array.isArray(moduleItems) ? moduleItems : []).forEach(item => {
    const code = String(item?.moduleCode || '').trim()
    if (!code || codeMap.has(code)) {
      return
    }
    codeMap.set(code, {
      value: code,
      label: code
    })
  })
  return Array.from(codeMap.values())
}

function formatTransition(row) {
  const fromStatus = row.fromStatus === '创建' ? '创建' : getOptionLabel(ticketStatusOptions, row.fromStatus)
  return `${fromStatus} -> ${getOptionLabel(ticketStatusOptions, row.toStatus)}`
}

loadProjectOptions().then(() => loadModuleOptions([]))
loadStatClassificationOptions()
loadStatisticsBlockConfig()
getStatistics()
</script>

<style scoped>
.mb16 {
  margin-bottom: 16px;
}

.mt16 {
  margin-top: 16px;
}

.stats-block-grid {
  row-gap: 16px;
}

.stats-block-col {
  margin-bottom: 16px;
}

.statistics-block-config {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px 16px;
}

.metric-label {
  color: #606266;
  font-size: 14px;
}

.metric-value {
  margin-top: 10px;
  color: #303133;
  font-size: 28px;
  font-weight: 700;
}
</style>
