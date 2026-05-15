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
  </div>
</template>

<script setup name="TicketStatistics">
import { getTicketStatistics } from '@/api/ticket/ticket'
import { getOptionLabel, sourceOptions, ticketStatusOptions } from '../constants'

const loading = ref(false)
const dateRange = ref([])
const overview = ref({})
const queryParams = ref({
  beginTime: undefined,
  endTime: undefined
})

function getStatistics() {
  loading.value = true
  getTicketStatistics(queryParams.value).then(response => {
    overview.value = response.data || {}
  }).finally(() => {
    loading.value = false
  })
}

function handleQuery() {
  queryParams.value.beginTime = dateRange.value?.[0]
  queryParams.value.endTime = dateRange.value?.[1]
  getStatistics()
}

function resetQuery() {
  dateRange.value = []
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

function formatTransition(row) {
  const fromStatus = row.fromStatus === '创建' ? '创建' : getOptionLabel(ticketStatusOptions, row.fromStatus)
  return `${fromStatus} -> ${getOptionLabel(ticketStatusOptions, row.toStatus)}`
}

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
