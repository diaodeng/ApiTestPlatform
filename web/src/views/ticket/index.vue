<template>
  <div class="app-container ticket-page">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="关键字" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="标题/描述/根因/方案"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="自然语言">
        <el-input
          v-model="naturalKeyword"
          placeholder="如：支付超时且根因是下游接口"
          clearable
          style="width: 260px"
          @keyup.enter="handleNaturalSearch"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="工单状态" clearable style="width: 160px">
          <el-option v-for="item in ticketStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="商家" prop="merchantName">
        <el-input
          v-model="queryParams.merchantName"
          placeholder="所属商家"
          clearable
          style="width: 180px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="模块" prop="moduleName">
        <el-input
          v-model="queryParams.moduleName"
          placeholder="所属模块"
          clearable
          style="width: 180px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="内部优先级" prop="internalPriority">
        <el-select v-model="queryParams.internalPriority" placeholder="内部优先级" clearable style="width: 140px">
          <el-option v-for="item in priorityOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleSearch">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['ticket:ticket:add']">
          新增
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="success" plain icon="Upload" @click="importOpen = true" v-hasPermi="['ticket:ticket:import']">
          导入
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="warning" plain icon="Download" @click="downloadTemplate" v-hasPermi="['ticket:ticket:import']">
          下载模板
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
    </el-row>

    <el-table v-loading="loading" :data="ticketList" row-key="ticketId">
      <el-table-column label="工单编号" prop="ticketNo" width="190" show-overflow-tooltip />
      <el-table-column label="标题" prop="title" min-width="240" show-overflow-tooltip />
      <el-table-column label="状态" prop="status" width="120" align="center">
        <template #default="scope">
          <el-tag :type="getStatusTagType(scope.row.status)">
            {{ getOptionLabel(ticketStatusOptions, scope.row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="商家" prop="merchantName" width="140" show-overflow-tooltip />
      <el-table-column label="模块" prop="moduleName" width="140" show-overflow-tooltip />
      <el-table-column label="对方优先级" prop="customerPriority" width="110" align="center" />
      <el-table-column label="内部优先级" prop="internalPriority" width="110" align="center" />
      <el-table-column label="来源" prop="source" width="110">
        <template #default="scope">{{ getOptionLabel(sourceOptions, scope.row.source) }}</template>
      </el-table-column>
      <el-table-column label="当前处理人" prop="currentAssigneeName" width="130" show-overflow-tooltip />
      <el-table-column label="创建时间" prop="createTime" width="170">
        <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="330" fixed="right">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="openDetail(scope.row)" v-hasPermi="['ticket:ticket:query']">
            详情
          </el-button>
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['ticket:ticket:edit']">
            编辑
          </el-button>
          <el-button
            link
            type="warning"
            icon="User"
            @click="openAssign(scope.row)"
            v-hasPermi="['ticket:ticket:assign']"
          >
            指派
          </el-button>
          <el-button
            link
            type="success"
            icon="Switch"
            @click="openStatus(scope.row)"
            v-hasPermi="['ticket:ticket:status']"
          >
            流转
          </el-button>
          <el-button
            link
            type="danger"
            icon="Delete"
            @click="handleDelete(scope.row)"
            v-hasPermi="['ticket:ticket:remove']"
          >
            删除
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

    <el-dialog :title="title" v-model="open" width="980px" append-to-body>
      <el-form ref="ticketRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item label="标题" prop="title">
              <el-input v-model="form.title" placeholder="请输入工单标题" maxlength="500" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属商家" prop="merchantName">
              <el-input v-model="form.merchantName" placeholder="请输入所属商家" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属模块" prop="moduleName">
              <el-input v-model="form.moduleName" placeholder="请输入所属模块" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="对方优先级" prop="customerPriority">
              <el-select v-model="form.customerPriority" placeholder="请选择">
                <el-option v-for="item in priorityOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="内部优先级" prop="internalPriority">
              <el-select v-model="form.internalPriority" placeholder="请选择">
                <el-option v-for="item in priorityOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="来源" prop="source">
              <el-select v-model="form.source" placeholder="请选择" clearable>
                <el-option v-for="item in sourceOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="严重等级" prop="severity">
              <el-select v-model="form.severity" placeholder="请选择" clearable>
                <el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="分类" prop="categoryName">
              <el-input v-model="form.categoryName" placeholder="如接口异常/数据问题" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="标签" prop="tagText">
              <el-input v-model="tagText" placeholder="逗号分隔，如支付,超时" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="描述" prop="description">
              <el-input v-model="form.description" type="textarea" :rows="5" placeholder="请输入问题现象和上下文" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="根因">
              <el-input v-model="form.rootCause" type="textarea" :rows="3" placeholder="最终根因，可后续RCA同步" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="解决方案">
              <el-input v-model="form.solution" type="textarea" :rows="3" placeholder="最终解决方案，可后续RCA同步" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="submitForm">确 定</el-button>
          <el-button @click="cancel">取 消</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog title="指派工单" v-model="assignOpen" width="520px" append-to-body>
      <el-form ref="assignRef" :model="assignForm" :rules="assignRules" label-width="100px">
        <el-form-item label="处理人ID" prop="toUserId">
          <UserSelect
            v-model="assignForm.toUserId"
            :initial-option="currentAssigneeOption"
            @change="handleAssigneeChange"
          />
        </el-form-item>
        <el-form-item label="处理人名称" prop="toUserName">
          <el-input v-model="assignForm.toUserName" placeholder="选择用户后自动填充，也可手动调整" />
        </el-form-item>
        <el-form-item label="指派原因">
          <el-input v-model="assignForm.reason" type="textarea" :rows="3" placeholder="请输入指派原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="submitAssign">确 定</el-button>
        <el-button @click="assignOpen = false">取 消</el-button>
      </template>
    </el-dialog>

    <el-dialog title="状态流转" v-model="statusOpen" width="640px" append-to-body>
      <el-form ref="statusRef" :model="statusForm" :rules="statusRules" label-width="100px">
        <el-form-item label="目标状态" prop="toStatus">
          <el-select v-model="statusForm.toStatus" placeholder="请选择目标状态">
            <el-option v-for="item in ticketStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="是否问题">
          <el-select v-model="statusForm.isProblem" placeholder="请选择" clearable>
            <el-option label="真实问题" :value="true" />
            <el-option label="非问题" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="statusForm.comment" type="textarea" :rows="3" placeholder="请输入状态流转说明" />
        </el-form-item>
        <el-form-item label="根因">
          <el-input v-model="statusForm.rootCause" type="textarea" :rows="2" placeholder="关闭/解决时建议填写" />
        </el-form-item>
        <el-form-item label="解决方案">
          <el-input v-model="statusForm.solution" type="textarea" :rows="2" placeholder="关闭/解决时建议填写" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="submitStatus">确 定</el-button>
        <el-button @click="statusOpen = false">取 消</el-button>
      </template>
    </el-dialog>

    <el-dialog title="导入工单数据" v-model="importOpen" width="720px" append-to-body>
      <el-alert
        title="支持飞书多维表格导出的 xlsx。工单号重复时会跳过，并在导入结果中列出未导入的重复工单号。"
        type="info"
        show-icon
        class="mb16"
      />
      <el-upload
        ref="uploadRef"
        drag
        action="#"
        accept=".xlsx"
        :limit="1"
        :auto-upload="false"
        :http-request="handleImportRequest"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将 Excel 拖到此处，或 <em>点击选择</em></div>
      </el-upload>
      <div v-if="importResult" class="import-result">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="读取行数">{{ importResult.totalRows }}</el-descriptions-item>
          <el-descriptions-item label="导入成功">{{ importResult.importedCount }}</el-descriptions-item>
          <el-descriptions-item label="已向量化">{{ importResult.embeddingCount }}</el-descriptions-item>
          <el-descriptions-item label="重复跳过">{{ importResult.duplicateCount }}</el-descriptions-item>
          <el-descriptions-item label="失败行">{{ importResult.failedCount }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="importResult.duplicateTicketNos?.length" class="mt12">
          <div class="result-title">重复未导入工单号</div>
          <el-tag v-for="item in importResult.duplicateTicketNos" :key="item" class="mr8 mb8" type="warning">
            {{ item }}
          </el-tag>
        </div>
        <el-table v-if="importResult.failedRows?.length" :data="importResult.failedRows" class="mt12">
          <el-table-column label="行号" prop="row" width="90" />
          <el-table-column label="失败原因" prop="reason" />
        </el-table>
      </div>
      <template #footer>
        <el-button type="primary" :loading="importing" @click="submitImport">开始导入</el-button>
        <el-button @click="importOpen = false">关 闭</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailOpen" :title="detailTitle" size="70%" append-to-body>
      <template v-if="detail.ticketId">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="编号">{{ detail.ticketNo }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusTagType(detail.status)">
              {{ getOptionLabel(ticketStatusOptions, detail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="当前处理人">{{ detail.currentAssigneeName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="所属商家">{{ detail.merchantName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="所属模块">{{ detail.moduleName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ getOptionLabel(sourceOptions, detail.source) }}</el-descriptions-item>
          <el-descriptions-item label="对方优先级">{{ detail.customerPriority || '-' }}</el-descriptions-item>
          <el-descriptions-item label="内部优先级">{{ detail.internalPriority || '-' }}</el-descriptions-item>
          <el-descriptions-item label="总耗时">{{ formatSeconds(detail.totalProcessSeconds) }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="3">{{ detail.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="根因" :span="3">{{ detail.rootCause || '-' }}</el-descriptions-item>
          <el-descriptions-item label="解决方案" :span="3">{{ detail.solution || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-tabs class="mt16">
          <el-tab-pane label="时间线">
            <el-timeline>
              <el-timeline-item
                v-for="item in timelineItems"
                :key="item.key"
                :timestamp="parseTime(item.time)"
                placement="top"
              >
                <el-card shadow="never">
                  <div class="timeline-title">{{ item.title }}</div>
                  <div class="timeline-content">{{ item.content || '-' }}</div>
                </el-card>
              </el-timeline-item>
            </el-timeline>
          </el-tab-pane>
          <el-tab-pane label="评论">
            <el-form :model="commentForm" label-width="80px" class="mb16">
              <el-form-item label="评论">
                <el-input v-model="commentForm.content" type="textarea" :rows="3" placeholder="请输入沟通评论" />
              </el-form-item>
              <el-form-item>
                <el-checkbox v-model="commentForm.isInternal">内部评论</el-checkbox>
                <el-button type="primary" class="ml12" @click="submitComment" v-hasPermi="['ticket:comment:add']">
                  提交评论
                </el-button>
              </el-form-item>
            </el-form>
            <el-empty v-if="!timeline.comments?.length" description="暂无评论" />
            <el-card v-for="item in timeline.comments" :key="item.id" shadow="never" class="mb8">
              <div class="record-head">
                <span>{{ item.userName || '-' }}</span>
                <el-tag v-if="item.isInternal" size="small" type="warning">内部</el-tag>
                <span>{{ parseTime(item.createTime) }}</span>
              </div>
              <div>{{ item.content }}</div>
            </el-card>
          </el-tab-pane>
          <el-tab-pane label="排查事件">
            <el-form :model="eventForm" label-width="90px" class="mb16">
              <el-form-item label="事件类型">
                <el-select v-model="eventForm.eventType" placeholder="请选择">
                  <el-option v-for="item in eventTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="事件说明">
                <el-input v-model="eventForm.content" type="textarea" :rows="3" placeholder="记录查了什么、结论是什么" />
              </el-form-item>
              <el-form-item label="结构化数据">
                <el-input
                  v-model="eventDataText"
                  type="textarea"
                  :rows="4"
                  placeholder='JSON，如 {"traceIds":["abc"],"checkedServices":["order-api"]}'
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="submitEvent" v-hasPermi="['ticket:event:add']">提交事件</el-button>
              </el-form-item>
            </el-form>
            <el-empty v-if="!timeline.events?.length" description="暂无事件" />
            <el-card v-for="item in timeline.events" :key="item.id" shadow="never" class="mb8">
              <div class="record-head">
                <span>{{ item.eventType }}</span>
                <span>{{ item.operatorName || '-' }}</span>
                <span>{{ parseTime(item.createTime) }}</span>
              </div>
              <div>{{ item.content || '-' }}</div>
              <pre v-if="item.eventData" class="json-block">{{ formatJson(item.eventData) }}</pre>
            </el-card>
          </el-tab-pane>
          <el-tab-pane label="RCA">
            <el-form ref="rcaRef" :model="rcaForm" label-width="100px">
              <el-form-item label="问题现象">
                <el-input v-model="rcaForm.symptom" type="textarea" :rows="2" />
              </el-form-item>
              <el-form-item label="影响范围">
                <el-input v-model="rcaForm.impactScope" type="textarea" :rows="2" />
              </el-form-item>
              <el-form-item label="复现步骤">
                <el-input v-model="rcaForm.reproduceSteps" type="textarea" :rows="3" />
              </el-form-item>
              <el-form-item label="排查过程">
                <el-input v-model="rcaForm.investigationProcess" type="textarea" :rows="4" />
              </el-form-item>
              <el-form-item label="根因分类">
                <el-input v-model="rcaForm.rootCauseCategory" />
              </el-form-item>
              <el-form-item label="根因详情">
                <el-input v-model="rcaForm.rootCauseDetail" type="textarea" :rows="3" />
              </el-form-item>
              <el-form-item label="修复方案">
                <el-input v-model="rcaForm.fixSolution" type="textarea" :rows="3" />
              </el-form-item>
              <el-form-item label="验证方式">
                <el-input v-model="rcaForm.verifyMethod" type="textarea" :rows="2" />
              </el-form-item>
              <el-form-item label="长期预防">
                <el-input v-model="rcaForm.preventionSolution" type="textarea" :rows="3" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="submitRca" v-hasPermi="['ticket:rca:edit']">保存RCA</el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>
  </div>
</template>

<script setup name="TicketIndex">
import { saveAs } from 'file-saver'
import {
  addTicket,
  addTicketComment,
  addTicketEvent,
  assignTicket,
  changeTicketStatus,
  delTicket,
  downloadTicketImportTemplate,
  getTicket,
  getTicketTimeline,
  importTicketExcel,
  listTicket,
  saveTicketRca,
  searchTicketNaturalLanguage,
  updateTicket
} from '@/api/ticket/ticket'
import {
  eventTypeOptions,
  getOptionLabel,
  getStatusTagType,
  priorityOptions,
  severityOptions,
  sourceOptions,
  ticketStatusOptions
} from './constants'
import UserSelect from './components/UserSelect.vue'

const { proxy } = getCurrentInstance()

const loading = ref(false)
const showSearch = ref(true)
const ticketList = ref([])
const total = ref(0)
const open = ref(false)
const assignOpen = ref(false)
const statusOpen = ref(false)
const importOpen = ref(false)
const importing = ref(false)
const detailOpen = ref(false)
const title = ref('')
const currentTicketId = ref()
const currentAssigneeOption = ref(null)
const detail = ref({})
const timeline = ref({})
const tagText = ref('')
const eventDataText = ref('')
const naturalKeyword = ref('')
const importResult = ref(null)

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyword: undefined,
    status: undefined,
    merchantName: undefined,
    moduleName: undefined,
    internalPriority: undefined
  },
  form: {},
  assignForm: {},
  statusForm: {},
  commentForm: {
    content: '',
    isInternal: false
  },
  eventForm: {
    eventType: 'ANALYSIS',
    content: ''
  },
  rcaForm: {},
  rules: {
    title: [{ required: true, message: '工单标题不能为空', trigger: 'blur' }],
    customerPriority: [{ required: true, message: '对方优先级不能为空', trigger: 'change' }],
    internalPriority: [{ required: true, message: '内部优先级不能为空', trigger: 'change' }]
  },
  assignRules: {
    toUserId: [{ required: true, message: '请选择处理人', trigger: 'change' }],
    toUserName: [{ required: true, message: '处理人名称不能为空', trigger: 'blur' }]
  },
  statusRules: {
    toStatus: [{ required: true, message: '目标状态不能为空', trigger: 'change' }]
  }
})

const {
  queryParams,
  form,
  assignForm,
  statusForm,
  commentForm,
  eventForm,
  rcaForm,
  rules,
  assignRules,
  statusRules
} = toRefs(data)

const detailTitle = computed(() => `工单详情：${detail.value.title || ''}`)
const timelineItems = computed(() => {
  const items = []
  ;(timeline.value.statusHistory || []).forEach(item => {
    items.push({
      key: `status-${item.id}`,
      time: item.startedAt,
      title: `状态流转：${getOptionLabel(ticketStatusOptions, item.fromStatus)} -> ${getOptionLabel(ticketStatusOptions, item.toStatus)}`,
      content: item.comment
    })
  })
  ;(timeline.value.assignHistory || []).forEach(item => {
    items.push({
      key: `assign-${item.id}`,
      time: item.assignedAt,
      title: `指派：${item.fromUserName || '未指派'} -> ${item.toUserName || '-'}`,
      content: item.reason
    })
  })
  ;(timeline.value.events || []).forEach(item => {
    items.push({
      key: `event-${item.id}`,
      time: item.createTime,
      title: `事件：${item.eventType}`,
      content: item.content
    })
  })
  return items.sort((a, b) => new Date(a.time || 0) - new Date(b.time || 0))
})

function getList() {
  loading.value = true
  listTicket(queryParams.value).then(response => {
    ticketList.value = response.rows || []
    total.value = response.total || 0
  }).finally(() => {
    loading.value = false
  })
}

function reset() {
  form.value = {
    ticketId: undefined,
    title: undefined,
    description: undefined,
    merchantName: undefined,
    moduleName: undefined,
    customerPriority: 'P3',
    internalPriority: 'P3',
    severity: undefined,
    source: undefined,
    categoryName: undefined,
    rootCause: undefined,
    solution: undefined
  }
  tagText.value = ''
  proxy.resetForm('ticketRef')
}

function handleQuery() {
  queryParams.value.pageNum = 1
  getList()
}

function handleSearch() {
  if (naturalKeyword.value) {
    handleNaturalSearch()
    return
  }
  handleQuery()
}

function resetQuery() {
  proxy.resetForm('queryRef')
  naturalKeyword.value = ''
  handleQuery()
}

function handleNaturalSearch() {
  if (!naturalKeyword.value) {
    handleQuery()
    return
  }
  loading.value = true
  searchTicketNaturalLanguage({ keyword: naturalKeyword.value, limit: queryParams.value.pageSize }).then(response => {
    ticketList.value = response.data || []
    total.value = ticketList.value.length
  }).finally(() => {
    loading.value = false
  })
}

function downloadTemplate() {
  downloadTicketImportTemplate().then(data => {
    saveAs(new Blob([data]), '工单导入模板.xlsx')
  })
}

function submitImport() {
  importResult.value = null
  proxy.$refs.uploadRef.submit()
}

function handleImportRequest(option) {
  const formData = new FormData()
  formData.append('file', option.file)
  importing.value = true
  importTicketExcel(formData).then(response => {
    importResult.value = response.data
    proxy.$modal.msgSuccess('导入完成')
    proxy.$refs.uploadRef.clearFiles()
    getList()
  }).finally(() => {
    importing.value = false
  })
}

function handleAdd() {
  reset()
  open.value = true
  title.value = '新增工单'
}

function handleUpdate(row) {
  reset()
  getTicket(row.ticketId).then(response => {
    form.value = response.data || {}
    tagText.value = Array.isArray(form.value.tags) ? form.value.tags.join(',') : ''
    open.value = true
    title.value = '编辑工单'
  })
}

function submitForm() {
  proxy.$refs.ticketRef.validate(valid => {
    if (!valid) return
    const payload = {
      ...form.value,
      tags: tagText.value ? tagText.value.split(',').map(item => item.trim()).filter(Boolean) : undefined
    }
    const request = payload.ticketId ? updateTicket(payload) : addTicket(payload)
    request.then(() => {
      proxy.$modal.msgSuccess(payload.ticketId ? '修改成功' : '新增成功')
      open.value = false
      getList()
    })
  })
}

function handleDelete(row) {
  proxy.$modal.confirm(`是否确认删除工单 "${row.title}"？`).then(() => delTicket(row.ticketId)).then(() => {
    proxy.$modal.msgSuccess('删除成功')
    getList()
  }).catch(() => {})
}

function openAssign(row) {
  currentTicketId.value = row.ticketId
  currentAssigneeOption.value = row.currentAssigneeId
    ? {
        userId: row.currentAssigneeId,
        userName: row.currentAssigneeName,
        nickName: row.currentAssigneeName,
        label: row.currentAssigneeName
      }
    : null
  assignForm.value = {
    toUserId: row.currentAssigneeId,
    toUserName: row.currentAssigneeName,
    reason: ''
  }
  assignOpen.value = true
}

function submitAssign() {
  proxy.$refs.assignRef.validate(valid => {
    if (!valid) return
    assignTicket(currentTicketId.value, assignForm.value).then(() => {
      proxy.$modal.msgSuccess('指派成功')
      assignOpen.value = false
      getList()
    })
  })
}

function handleAssigneeChange(user) {
  assignForm.value.toUserName = user?.nickName || user?.userName || ''
  currentAssigneeOption.value = user
}

function openStatus(row) {
  currentTicketId.value = row.ticketId
  statusForm.value = {
    toStatus: undefined,
    comment: '',
    rootCause: row.rootCause,
    solution: row.solution,
    isProblem: row.isProblem
  }
  statusOpen.value = true
}

function submitStatus() {
  proxy.$refs.statusRef.validate(valid => {
    if (!valid) return
    changeTicketStatus(currentTicketId.value, statusForm.value).then(() => {
      proxy.$modal.msgSuccess('状态流转成功')
      statusOpen.value = false
      getList()
    })
  })
}

function openDetail(row) {
  currentTicketId.value = row.ticketId
  detailOpen.value = true
  Promise.all([getTicket(row.ticketId), getTicketTimeline(row.ticketId)]).then(([detailResponse, timelineResponse]) => {
    detail.value = detailResponse.data || {}
    timeline.value = timelineResponse.data || {}
    rcaForm.value = timeline.value.rca || {}
  })
}

function refreshTimeline() {
  return getTicketTimeline(currentTicketId.value).then(response => {
    timeline.value = response.data || {}
    rcaForm.value = timeline.value.rca || rcaForm.value
  })
}

function submitComment() {
  if (!commentForm.value.content) {
    proxy.$modal.msgWarning('请填写评论内容')
    return
  }
  addTicketComment(currentTicketId.value, commentForm.value).then(() => {
    proxy.$modal.msgSuccess('评论成功')
    commentForm.value = { content: '', isInternal: false }
    refreshTimeline()
  })
}

function submitEvent() {
  let eventData
  if (eventDataText.value) {
    try {
      eventData = JSON.parse(eventDataText.value)
    } catch (error) {
      proxy.$modal.msgError('结构化数据必须是合法 JSON')
      return
    }
  }
  addTicketEvent(currentTicketId.value, { ...eventForm.value, eventData }).then(() => {
    proxy.$modal.msgSuccess('事件记录成功')
    eventForm.value = { eventType: 'ANALYSIS', content: '' }
    eventDataText.value = ''
    refreshTimeline()
  })
}

function submitRca() {
  saveTicketRca(currentTicketId.value, rcaForm.value).then(() => {
    proxy.$modal.msgSuccess('RCA保存成功')
    refreshTimeline()
    getTicket(currentTicketId.value).then(response => {
      detail.value = response.data || {}
    })
  })
}

function formatJson(value) {
  return JSON.stringify(value, null, 2)
}

function formatSeconds(seconds) {
  if (!seconds) return '-'
  const hour = Math.floor(seconds / 3600)
  const minute = Math.floor((seconds % 3600) / 60)
  const second = seconds % 60
  return `${hour}小时${minute}分${second}秒`
}

getList()
</script>

<style scoped>
.ticket-page :deep(.el-drawer__body) {
  padding-top: 8px;
}

.mt16 {
  margin-top: 16px;
}

.mb16 {
  margin-bottom: 16px;
}

.mb8 {
  margin-bottom: 8px;
}

.ml12 {
  margin-left: 12px;
}

.mt12 {
  margin-top: 12px;
}

.mr8 {
  margin-right: 8px;
}

.import-result {
  margin-top: 16px;
}

.result-title {
  margin-bottom: 8px;
  color: #606266;
  font-weight: 600;
}

.record-head {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
  color: #606266;
  font-size: 13px;
}

.timeline-title {
  font-weight: 600;
  margin-bottom: 6px;
}

.timeline-content {
  color: #606266;
}

.json-block {
  padding: 10px;
  margin: 10px 0 0;
  overflow: auto;
  background: #f6f8fa;
  border-radius: 4px;
}
</style>
