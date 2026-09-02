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
      <el-table-column label="总 Token" align="center" min-width="120">
        <template #default="scope">{{ formatTokenCount(scope.row.totalTokenCount) }}</template>
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
        <el-descriptions-item label="总 Token">{{ formatTokenCount(detailData.totalTokenCount) }}</el-descriptions-item>
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

// 任务类型枚举：与后端审计写入点保持一致（ticket_light_ai_service / ticket_ai_analysis_service /
// ticket_embedding_service / ticket_topic_stats_service / 自动分类链路），未知类型由 formatTaskType 兜底显示原值。
const taskTypeOptions = [
  { label: '同步统一提取', value: 'ticket_sync_extract' },
  { label: '翻译', value: 'ticket_translate' },
  { label: '分类统计', value: 'ticket_stat_classify' },
  { label: '自动分类', value: 'ticket_category_classify' },
  { label: '知识提炼', value: 'ticket_knowledge_extract' },
  { label: '标题总结', value: 'ticket_title_summary' },
  { label: '专题分类批次', value: 'ticket_topic_classify' },
  { label: '工单AI分析', value: 'ticket_ai_analysis' },
  { label: '向量化Embedding', value: 'ticket_embedding' },
]

// 来源类型静态枚举：来源类型多由“同步场景 + 动作”拼接生成（如 external_sync_sync_extract），
// 动态部分由 SOURCE_SCENE_LABELS / SOURCE_ACTION_LABELS 规则解析。
const sourceTypeOptions = [
  { label: '工单', value: 'ticket' },
  { label: 'AI测试', value: 'ai_test' },
  { label: 'AI分析', value: 'ai_analysis' },
  { label: '飞书专题', value: 'feishu_topic' },
  { label: '批量重分类', value: 'ticket_batch_reclassify' },
  { label: '手动翻译', value: 'ticket_manual_translate' },
  { label: '外部同步-统一提取', value: 'external_sync_sync_extract' },
  { label: '外部同步-自动分类', value: 'external_sync_auto_category' },
  { label: '外部同步-状态变更自动分类', value: 'external_sync_status_change_auto_category' },
  { label: '多维表格同步-统一提取', value: 'bitable_pull_sync_extract' },
  { label: '多维表格同步-自动分类', value: 'bitable_pull_auto_category' },
  { label: '多维表格同步-状态变更自动分类', value: 'bitable_pull_status_change_auto_category' },
  { label: '远程同步-统一提取', value: 'remote_pull_sync_extract' },
  { label: '远程同步-自动分类', value: 'remote_pull_auto_category' },
  { label: '远程同步-状态变更自动分类', value: 'remote_pull_status_change_auto_category' },
]

// 来源类型中同步场景前缀的中文标签。
const SOURCE_SCENE_LABELS = {
  external_sync: '外部同步',
  bitable_pull: '多维表格同步',
  remote_pull: '远程同步',
}

// 来源类型中动作后缀的中文标签，长后缀必须放在前面优先匹配。
const SOURCE_ACTION_LABELS = [
  { suffix: 'status_change_auto_category', label: '状态变更自动分类' },
  { suffix: 'auto_category', label: '自动分类' },
  { suffix: 'sync_extract', label: '统一提取' },
]

const statusOptions = [
  { label: '待执行', value: 'pending' },
  { label: '执行中', value: 'running' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '跳过', value: 'skipped' },
  { label: '已取消（重复请求）', value: 'canceled' },
  { label: '复用历史结果', value: 'reused' },
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
  if (!sourceType) return '-'
  const item = sourceTypeOptions.find(row => row.value === sourceType)
  if (item) return item.label
  // 规则兜底：{场景}_{动作} 拼接的来源类型解析为“场景-动作”中文，避免新增场景后再显示英文原值
  for (const [scene, sceneLabel] of Object.entries(SOURCE_SCENE_LABELS)) {
    if (!sourceType.startsWith(`${scene}_`)) continue
    for (const action of SOURCE_ACTION_LABELS) {
      if (sourceType === `${scene}_${action.suffix}`) {
        return `${sceneLabel}-${action.label}`
      }
    }
  }
  return sourceType
}

function formatStatus(status) {
  const item = statusOptions.find(row => row.value === status)
  return item ? item.label : status || '-'
}

function statusTagType(status) {
  if (status === 'success') return 'success'
  if (status === 'running' || status === 'pending') return 'warning'
  if (status === 'failed') return 'danger'
  if (status === 'reused') return 'success'
  return 'info'
}

function formatTokenCount(value) {
  return Number.isFinite(Number(value)) ? String(Number(value)) : '-'
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
