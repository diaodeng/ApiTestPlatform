<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="90px">
      <el-form-item label="关键字" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="任务名/来源/错误信息"
          clearable
          style="width: 260px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="任务类型" prop="taskType">
        <el-select v-model="queryParams.taskType" placeholder="全部类型" clearable style="width: 180px">
          <el-option v-for="item in taskTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="来源类型" prop="sourceType">
        <el-select v-model="queryParams.sourceType" placeholder="全部来源" clearable style="width: 180px">
          <el-option v-for="item in sourceTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="Provider" prop="providerCode">
        <el-input v-model="queryParams.providerCode" placeholder="Provider编码" clearable style="width: 180px" />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="全部状态" clearable style="width: 160px">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
    </el-row>

    <el-table v-loading="loading" :data="executionList">
      <el-table-column label="ID" align="center" prop="executionId" width="100" />
      <el-table-column label="任务类型" align="center" prop="taskType" width="150">
        <template #default="scope">{{ formatTaskType(scope.row.taskType) }}</template>
      </el-table-column>
      <el-table-column label="任务名称" align="left" prop="taskName" min-width="180" :show-overflow-tooltip="true" />
      <el-table-column label="来源类型" align="center" prop="sourceType" width="120">
        <template #default="scope">{{ formatSourceType(scope.row.sourceType) }}</template>
      </el-table-column>
      <el-table-column label="来源引用" align="left" prop="sourceRef" min-width="180" :show-overflow-tooltip="true" />
      <el-table-column label="Provider" align="center" prop="providerCode" min-width="140" :show-overflow-tooltip="true" />
      <el-table-column label="Prompt" align="center" prop="promptCode" min-width="150" :show-overflow-tooltip="true" />
      <el-table-column label="模型" align="center" prop="modelName" min-width="140" :show-overflow-tooltip="true" />
      <el-table-column label="状态" align="center" width="110">
        <template #default="scope">
          <el-tag :type="statusTagType(scope.row.status)">
            {{ formatStatus(scope.row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" min-width="180">
        <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="错误信息" align="left" prop="errorMessage" min-width="240" :show-overflow-tooltip="true" />
      <el-table-column label="操作" align="center" width="100" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="handleViewDetail(scope.row)" v-hasPermi="['system:aitaskexecution:query']">
            详情
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination
      v-show="total > 0"
      :total="total"
      v-model:page="queryParams.pageNum"
      v-model:limit="queryParams.pageSize"
      @pagination="getList"
    />

    <el-drawer v-model="detailOpen" title="AI 执行审计详情" size="720px" direction="rtl" append-to-body destroy-on-close>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="ID">{{ detailData.executionId || '-' }}</el-descriptions-item>
        <el-descriptions-item label="任务类型">{{ formatTaskType(detailData.taskType) }}</el-descriptions-item>
        <el-descriptions-item label="任务名称">{{ detailData.taskName || '-' }}</el-descriptions-item>
        <el-descriptions-item label="来源类型">{{ formatSourceType(detailData.sourceType) }}</el-descriptions-item>
        <el-descriptions-item label="来源ID">{{ detailData.sourceId ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="来源引用">{{ detailData.sourceRef || '-' }}</el-descriptions-item>
        <el-descriptions-item label="Provider">{{ detailData.providerCode || '-' }}</el-descriptions-item>
        <el-descriptions-item label="Prompt">{{ detailData.promptCode || '-' }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ detailData.modelName || '-' }}</el-descriptions-item>
        <el-descriptions-item label="Base URL">{{ detailData.baseUrl || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTagType(detailData.status)">{{ formatStatus(detailData.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detailData.createTime ? parseTime(detailData.createTime) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ detailData.updateTime ? parseTime(detailData.updateTime) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="错误信息">{{ detailData.errorMessage || '-' }}</el-descriptions-item>
      </el-descriptions>

      <div class="audit-section">
        <div class="audit-title">请求载荷</div>
        <pre class="audit-pre">{{ formatJson(detailData.requestPayload) }}</pre>
      </div>
      <div class="audit-section">
        <div class="audit-title">响应载荷</div>
        <pre class="audit-pre">{{ formatJson(detailData.responsePayload) }}</pre>
      </div>
      <div class="audit-section">
        <div class="audit-title">原始响应文本</div>
        <pre class="audit-pre">{{ detailData.responseText || '-' }}</pre>
      </div>
      <div class="audit-section">
        <div class="audit-title">Token 用量</div>
        <pre class="audit-pre">{{ formatJson(detailData.tokenUsage) }}</pre>
      </div>
    </el-drawer>
  </div>
</template>

<script setup name="AiTaskExecution">
import { getAiTaskExecution, listAiTaskExecution } from '@/api/system/aitaskexecution'

const { proxy } = getCurrentInstance()

const taskTypeOptions = [
  { label: '工单翻译', value: 'ticket_translate' },
  { label: '知识提炼', value: 'ticket_knowledge_extract' },
]

const sourceTypeOptions = [
  { label: '工单', value: 'ticket' },
  { label: '日志拉取', value: 'log_pull' },
  { label: '消息', value: 'message' },
  { label: '其他', value: 'other' },
]

const statusOptions = [
  { label: '待执行', value: 'pending' },
  { label: '执行中', value: 'running' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '跳过', value: 'skipped' },
]

const executionList = ref([])
const loading = ref(false)
const showSearch = ref(true)
const total = ref(0)
const detailOpen = ref(false)
const detailData = ref({})

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyword: undefined,
    taskType: undefined,
    sourceType: undefined,
    providerCode: undefined,
    status: undefined,
  },
})

const { queryParams } = toRefs(data)

function formatTaskType(taskType) {
  const item = taskTypeOptions.find(row => row.value === taskType)
  return item ? item.label : taskType || '-'
}

function formatSourceType(sourceType) {
  const item = sourceTypeOptions.find(row => row.value === sourceType)
  return item ? item.label : sourceType || '-'
}

function formatStatus(status) {
  const item = statusOptions.find(row => row.value === status)
  return item ? item.label : status || '-'
}

function statusTagType(status) {
  if (status === 'success') return 'success'
  if (status === 'running' || status === 'pending') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

function formatJson(value) {
  if (value === undefined || value === null || value === '') {
    return '-'
  }
  if (typeof value === 'string') {
    try {
      return JSON.stringify(JSON.parse(value), null, 2)
    } catch {
      return value
    }
  }
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function getList() {
  loading.value = true
  listAiTaskExecution(queryParams.value)
    .then(response => {
      executionList.value = response.rows || []
      total.value = response.total || 0
    })
    .finally(() => {
      loading.value = false
    })
}

function handleQuery() {
  queryParams.value.pageNum = 1
  getList()
}

function resetQuery() {
  proxy.resetForm('queryRef')
  handleQuery()
}

function handleViewDetail(row) {
  getAiTaskExecution(row.executionId).then(response => {
    detailData.value = response.data || {}
    detailOpen.value = true
  })
}

getList()
</script>

<style scoped>
.audit-section {
  margin-top: 16px;
}

.audit-title {
  margin-bottom: 8px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.audit-pre {
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow: auto;
}
</style>
