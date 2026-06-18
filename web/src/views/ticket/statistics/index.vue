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
          :disabled="!selectedProjectIds.length"
        >
          <el-option
            v-for="item in moduleOptions"
            :key="`${item.projectId}-${item.moduleId}`"
            :label="formatModuleOptionLabel(item)"
            :value="item.moduleId"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">查询</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
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

    <el-row :gutter="16">
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>状态分布</template>
          <el-table v-loading="loading" :data="overview.statusCounts || []">
            <el-table-column label="状态" prop="status">
              <template #default="scope">{{ getOptionLabel(ticketStatusOptions, scope.row.status) }}</template>
            </el-table-column>
            <el-table-column label="数量" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>模块分布</template>
          <el-table v-loading="loading" :data="overview.moduleCounts || []">
            <el-table-column label="模块" prop="module" />
            <el-table-column label="数量" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>人员处理量</template>
          <el-table v-loading="loading" :data="overview.assigneeCounts || []">
            <el-table-column label="处理人" prop="userName" />
            <el-table-column label="数量" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt16">
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>问题分类</template>
          <el-table v-loading="loading" :data="overview.categoryCounts || []">
            <el-table-column label="分类" prop="category" />
            <el-table-column label="数量" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>原因分类</template>
          <el-table v-loading="loading" :data="overview.rootCauseCounts || []">
            <el-table-column label="原因" prop="rootCause" />
            <el-table-column label="数量" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>状态流转</template>
          <el-table v-loading="loading" :data="overview.transitionCounts || []">
            <el-table-column label="流转">
              <template #default="scope">
                {{ formatTransition(scope.row) }}
              </template>
            </el-table-column>
            <el-table-column label="次数" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt16">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>来源分布</template>
          <el-table v-loading="loading" :data="overview.sourceCounts || []">
            <el-table-column label="来源">
              <template #default="scope">{{ getOptionLabel(sourceOptions, scope.row.source) }}</template>
            </el-table-column>
            <el-table-column label="数量" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>内部优先级</template>
          <el-table v-loading="loading" :data="overview.priorityCounts || []">
            <el-table-column label="优先级" prop="priority" />
            <el-table-column label="数量" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt16">
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>工单类型</template>
          <el-table v-loading="loading" :data="overview.issueTypeCounts || []">
            <el-table-column label="类型">
              <template #default="scope">{{ formatIssueType(scope.row) }}</template>
            </el-table-column>
            <el-table-column label="数量" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>是否真实问题</template>
          <el-table v-loading="loading" :data="overview.problemCounts || []">
            <el-table-column label="问题性质">
              <template #default="scope">{{ formatProblemFlag(scope.row.isProblem) }}</template>
            </el-table-column>
            <el-table-column label="数量" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>根因分类</template>
          <el-table v-loading="loading" :data="overview.rootCauseTypeCounts || []">
            <el-table-column label="根因">
              <template #default="scope">{{ getStatOptionLabel(rootCauseTypeOptions, scope.row.rootCauseType) }}</template>
            </el-table-column>
            <el-table-column label="数量" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt16">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>解决方式</template>
          <el-table v-loading="loading" :data="overview.solutionTypeCounts || []">
            <el-table-column label="方式">
              <template #default="scope">{{ getStatOptionLabel(solutionTypeOptions, scope.row.solutionType) }}</template>
            </el-table-column>
            <el-table-column label="数量" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>关闭结果</template>
          <el-table v-loading="loading" :data="overview.resolutionCounts || []">
            <el-table-column label="结果">
              <template #default="scope">{{ formatResolution(scope.row) }}</template>
            </el-table-column>
            <el-table-column label="数量" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
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

const loading = ref(false)
const dateRange = ref([])
const overview = ref({})
const projectOptions = ref([])
const moduleOptions = ref([])
const selectedProjectIds = ref([])
const selectedModuleIds = ref([])
const issueTypeOptions = ref([])
const rootCauseTypeOptions = ref([])
const solutionTypeOptions = ref([])
const resolutionOptions = ref([])
const queryParams = ref({
  beginTime: undefined,
  endTime: undefined
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
    moduleIds: selectedModuleIds.value.length ? selectedModuleIds.value.join(',') : undefined
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

function loadProjectOptions() {
  return listTicketProjectOptions().then(response => {
    projectOptions.value = response.data || []
  })
}

async function loadModuleOptions(projectIds = []) {
  const ids = Array.isArray(projectIds) ? projectIds.filter(Boolean) : []
  if (!ids.length) {
    moduleOptions.value = []
    selectedModuleIds.value = []
    return
  }
  const responses = await Promise.all(ids.map(projectId => listTicketModuleOptions({ projectId })))
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
  const validModuleIds = new Set(moduleOptions.value.map(item => item.moduleId))
  selectedModuleIds.value = selectedModuleIds.value.filter(moduleId => validModuleIds.has(moduleId))
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
  moduleOptions.value = []
  queryParams.value = { beginTime: undefined, endTime: undefined }
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

function formatTransition(row) {
  const fromStatus = row.fromStatus === '创建' ? '创建' : getOptionLabel(ticketStatusOptions, row.fromStatus)
  return `${fromStatus} -> ${getOptionLabel(ticketStatusOptions, row.toStatus)}`
}

loadProjectOptions()
loadStatClassificationOptions()
getStatistics()
</script>

<style scoped>
.mb16 {
  margin-bottom: 16px;
}

.mt16 {
  margin-top: 16px;
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
