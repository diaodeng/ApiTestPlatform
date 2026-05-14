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
          <div class="metric-label">问题分类数</div>
          <div class="metric-value">{{ overview.categoryCounts?.length || 0 }}</div>
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
          <template #header>分类分布</template>
          <el-table v-loading="loading" :data="overview.categoryCounts || []">
            <el-table-column label="分类" prop="category" />
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
  </div>
</template>

<script setup name="TicketStatistics">
import { getTicketStatistics } from '@/api/ticket/ticket'
import { getOptionLabel, ticketStatusOptions } from '../constants'

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

getStatistics()
</script>

<style scoped>
.mb16 {
  margin-bottom: 16px;
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
