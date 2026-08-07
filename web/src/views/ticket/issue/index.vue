<template>
  <div class="app-container ticket-issue-page">
    <el-form ref="queryRef" :model="queryParams" :inline="true" v-show="showSearch" class="mb8">
      <el-form-item label="关键字" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="编号/标题/摘要"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="问题编号" prop="issueNo">
        <el-input
          v-model="queryParams.issueNo"
          placeholder="问题实例编号"
          clearable
          style="width: 180px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="问题标题" prop="title">
        <el-input
          v-model="queryParams.title"
          placeholder="问题标题"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="全部" clearable style="width: 150px">
          <el-option v-for="item in issueStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="项目" prop="projectId">
        <el-select v-model="queryParams.projectId" placeholder="全部" clearable filterable style="width: 180px">
          <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
        </el-select>
      </el-form-item>
      <el-form-item label="模块" prop="moduleId">
        <el-select v-model="queryParams.moduleId" placeholder="全部" clearable filterable style="width: 220px">
          <el-option
            v-for="item in queryModuleOptions"
            :key="item.moduleId"
            :label="buildModuleOptionLabel(item)"
            :value="item.moduleId"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="负责人" prop="ownerId">
        <el-select v-model="queryParams.ownerId" placeholder="全部" clearable filterable style="width: 180px">
          <el-option v-for="item in ownerOptions" :key="item.userId" :label="item.label" :value="item.userId" />
        </el-select>
      </el-form-item>
      <el-form-item label="细分问题" prop="problemPatternCode">
        <el-select v-model="queryParams.problemPatternCode" placeholder="全部" clearable filterable style="width: 220px">
          <el-option
            v-for="item in problemPatternOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['ticket:issue:add']">
          新增问题实例
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button plain icon="Setting" @click="columnConfigOpen = true">列设置</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
    </el-row>

    <el-table v-loading="loading" :data="issueList" row-key="issueId" @row-dblclick="handleDetail">
      <el-table-column v-if="isIssueColumnVisible('issueNo')" label="问题编号" prop="issueNo" width="180" show-overflow-tooltip />
      <el-table-column v-if="isIssueColumnVisible('title')" label="问题标题" prop="title" min-width="220" show-overflow-tooltip />
      <el-table-column v-if="isIssueColumnVisible('status')" label="状态" prop="status" width="100" align="center">
        <template #default="scope">
          <el-tag :type="getIssueStatusTagType(scope.row.status)">{{ formatIssueStatus(scope.row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="isIssueColumnVisible('severity')" label="严重等级" prop="severity" width="110" show-overflow-tooltip />
      <el-table-column v-if="isIssueColumnVisible('projectName')" label="项目" prop="projectName" min-width="160" show-overflow-tooltip />
      <el-table-column v-if="isIssueColumnVisible('moduleName')" label="模块" prop="moduleName" min-width="180" show-overflow-tooltip />
      <el-table-column v-if="isIssueColumnVisible('rootCauseType')" label="根因分类" prop="rootCauseType" min-width="150" show-overflow-tooltip />
      <el-table-column v-if="isIssueColumnVisible('problemPatternName')" label="细分问题" prop="problemPatternName" min-width="180" show-overflow-tooltip />
      <el-table-column v-if="isIssueColumnVisible('ownerName')" label="负责人" prop="ownerName" min-width="140" show-overflow-tooltip />
      <el-table-column v-if="isIssueColumnVisible('affectedTicketCount')" label="影响工单数" prop="affectedTicketCount" width="110" align="center" />
      <el-table-column v-if="isIssueColumnVisible('updateTime')" label="更新时间" prop="updateTime" width="170">
        <template #default="scope">{{ parseTime(scope.row.updateTime) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="handleDetail(scope.row)" v-hasPermi="['ticket:issue:query']">
            详情
          </el-button>
          <el-button link type="primary" icon="Edit" @click="handleEdit(scope.row)" v-hasPermi="['ticket:issue:edit']">
            编辑
          </el-button>
          <el-button link type="primary" icon="Connection" @click="openIssueTickets(scope.row)" v-hasPermi="['ticket:issue:query']">
            绑定工单
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

    <el-dialog
      v-model="open"
      :title="dialogTitle"
      width="860px"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="问题编号" prop="issueNo">
              <el-input v-model="form.issueNo" placeholder="不填则自动生成" :disabled="isEdit" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status" style="width: 100%">
                <el-option v-for="item in issueStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="标题" prop="title">
              <el-input v-model="form.title" maxlength="500" show-word-limit />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="严重等级" prop="severity">
              <el-select v-model="form.severity" clearable filterable style="width: 100%">
                <el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="摘要" prop="summary">
              <el-input v-model="form.summary" type="textarea" :rows="4" maxlength="4000" show-word-limit />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目" prop="projectId">
              <el-select v-model="form.projectId" placeholder="请选择项目" clearable filterable style="width: 100%" @change="handleFormProjectChange">
                <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目名称">
              <el-input v-model="form.projectName" disabled />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模块" prop="moduleId">
              <el-select v-model="form.moduleId" placeholder="请选择模块" clearable filterable style="width: 100%" @change="handleFormModuleChange">
                <el-option
                  v-for="item in formModuleOptions"
                  :key="item.moduleId"
                  :label="buildModuleOptionLabel(item)"
                  :value="item.moduleId"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模块名称">
              <el-input v-model="form.moduleName" disabled />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="根因分类" prop="rootCauseType">
              <el-select v-model="form.rootCauseType" clearable filterable style="width: 100%">
                <el-option v-for="item in rootCauseTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="细分问题" prop="problemPatternCode">
              <el-select v-model="form.problemPatternCode" clearable filterable style="width: 100%" @change="handlePatternChange">
                <el-option v-for="item in problemPatternOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="细分问题名称">
              <el-input v-model="form.problemPatternName" disabled />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负责人" prop="ownerId">
              <el-select v-model="form.ownerId" placeholder="请选择负责人" clearable filterable style="width: 100%" @change="handleOwnerChange">
                <el-option v-for="item in ownerOptions" :key="item.userId" :label="item.label" :value="item.userId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负责人名称">
              <el-input v-model="form.ownerName" disabled />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="3" maxlength="1000" show-word-limit />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="open = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailOpen" :title="detail.issueNo || detail.title || '问题实例详情'" size="78%" append-to-body>
      <el-skeleton :loading="detailLoading" animated :rows="8">
        <template #default>
          <el-descriptions :column="3" border>
            <el-descriptions-item label="问题编号">{{ detail.issueNo || '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getIssueStatusTagType(detail.status)">{{ formatIssueStatus(detail.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="影响工单数">{{ detail.affectedTicketCount ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="标题" :span="2">{{ detail.title || '-' }}</el-descriptions-item>
            <el-descriptions-item label="严重等级">{{ detail.severity || '-' }}</el-descriptions-item>
            <el-descriptions-item label="项目">{{ detail.projectName || '-' }}</el-descriptions-item>
            <el-descriptions-item label="模块">{{ detail.moduleName || '-' }}</el-descriptions-item>
            <el-descriptions-item label="根因分类">{{ detail.rootCauseType || '-' }}</el-descriptions-item>
            <el-descriptions-item label="细分问题">{{ detail.problemPatternName || '-' }}</el-descriptions-item>
            <el-descriptions-item label="负责人">{{ detail.ownerName || '-' }}</el-descriptions-item>
            <el-descriptions-item label="首张工单">{{ detail.firstTicketId || '-' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ parseTime(detail.createTime) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ parseTime(detail.updateTime) }}</el-descriptions-item>
            <el-descriptions-item label="摘要" :span="3">{{ detail.summary || '-' }}</el-descriptions-item>
          </el-descriptions>

          <el-card shadow="never" class="issue-panel mt16">
            <template #header>
              <div class="panel-header">
                <span>绑定工单</span>
                <el-button link type="primary" icon="Connection" @click="scrollToBindForm">快速绑定</el-button>
              </div>
            </template>
            <el-table :data="detail.tickets || []" row-key="ticketId" empty-text="暂无绑定工单">
              <el-table-column label="工单编号" prop="ticketNo" width="180" show-overflow-tooltip />
              <el-table-column label="标题" prop="title" min-width="220" show-overflow-tooltip />
              <el-table-column label="状态" prop="status" width="120" />
              <el-table-column label="当前处理人" prop="currentAssigneeName" min-width="140" show-overflow-tooltip />
              <el-table-column label="提交时间" prop="submitTime" width="170">
                <template #default="scope">{{ parseTime(scope.row.submitTime) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="200" fixed="right">
                <template #default="scope">
                  <el-button link type="primary" icon="View" @click="openTicketDetail(scope.row.ticketId)">
                    打开工单
                  </el-button>
                  <el-button
                    link
                    type="danger"
                    icon="Delete"
                    @click="handleUnbindTicket(scope.row.ticketId)"
                    v-hasPermi="['ticket:issue:remove']"
                  >
                    解绑
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <el-card shadow="never" class="issue-panel mt16" id="bind-issue-ticket-form">
            <template #header>
              <span>绑定已有工单</span>
            </template>
            <el-form :inline="true" :model="bindForm" label-width="90px">
              <el-form-item label="工单ID">
                <el-input-number v-model="bindForm.ticketId" :min="1" :controls="false" style="width: 180px" />
              </el-form-item>
              <el-form-item label="归因类型">
                <el-select v-model="bindForm.relationType" style="width: 160px">
                  <el-option v-for="item in relationTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="已确认">
                <el-switch v-model="bindForm.confirmed" />
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="bindForm.remark" placeholder="可选" style="width: 260px" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="binding" @click="handleBindTicket">绑定到当前问题</el-button>
              </el-form-item>
            </el-form>
          </el-card>

          <el-card shadow="never" class="issue-panel mt16" id="issue-relation-form">
            <template #header>
              <span>补充关系</span>
            </template>
            <el-alert
              v-if="(detail.tickets || []).length < 2"
              title="当前问题实例下的工单少于 2 个，建议先绑定更多工单后再维护补充关系。"
              type="info"
              show-icon
              class="mb12"
            />
            <el-form :inline="true" :model="relationForm" label-width="90px">
              <el-form-item label="源工单">
                <el-select v-model="relationForm.sourceTicketId" filterable placeholder="请选择" style="width: 220px">
                  <el-option
                    v-for="item in detailTicketOptions"
                    :key="item.ticketId"
                    :label="item.label"
                    :value="item.ticketId"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="目标工单">
                <el-select v-model="relationForm.targetTicketId" filterable placeholder="请选择" style="width: 220px">
                  <el-option
                    v-for="item in detailTicketOptions"
                    :key="item.ticketId"
                    :label="item.label"
                    :value="item.ticketId"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="关系类型">
                <el-select v-model="relationForm.relationType" style="width: 150px">
                  <el-option v-for="item in relationTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="置信度">
                <el-input-number v-model="relationForm.confidence" :min="0" :max="1" :step="0.05" :precision="2" style="width: 160px" />
              </el-form-item>
              <el-form-item label="来源">
                <el-select v-model="relationForm.source" style="width: 140px">
                  <el-option v-for="item in relationSourceOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="确认">
                <el-switch v-model="relationForm.confirmed" />
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="relationForm.remark" placeholder="可选" style="width: 260px" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="relationSaving" @click="handleAddRelation">新增关系</el-button>
              </el-form-item>
            </el-form>
          </el-card>

          <el-card shadow="never" class="issue-panel mt16">
            <template #header>
              <span>补充关系列表</span>
            </template>
            <el-table :data="detail.relations || []" row-key="relationId" empty-text="暂无补充关系">
              <el-table-column label="关系类型" prop="relationType" width="120">
                <template #default="scope">{{ formatRelationType(scope.row.relationType) }}</template>
              </el-table-column>
              <el-table-column label="源工单" min-width="220">
                <template #default="scope">{{ formatRelationTicket(scope.row.sourceTicketNo, scope.row.sourceTicketTitle) }}</template>
              </el-table-column>
              <el-table-column label="目标工单" min-width="220">
                <template #default="scope">{{ formatRelationTicket(scope.row.targetTicketNo, scope.row.targetTicketTitle) }}</template>
              </el-table-column>
              <el-table-column label="置信度" width="100" align="center">
                <template #default="scope">{{ formatConfidence(scope.row.confidence) }}</template>
              </el-table-column>
              <el-table-column label="来源" prop="source" width="100" align="center" />
              <el-table-column label="确认" width="90" align="center">
                <template #default="scope">
                  <el-tag :type="scope.row.confirmed ? 'success' : 'warning'">{{ scope.row.confirmed ? '已确认' : '待确认' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="备注" prop="remark" min-width="160" show-overflow-tooltip />
              <el-table-column label="操作" width="170" fixed="right">
                <template #default="scope">
                  <el-button
                    v-if="!scope.row.confirmed"
                    link
                    type="primary"
                    icon="Check"
                    @click="handleConfirmRelation(scope.row.relationId)"
                    v-hasPermi="['ticket:relation:edit']"
                  >
                    确认
                  </el-button>
                  <el-button
                    link
                    type="danger"
                    icon="Delete"
                    @click="handleDeleteRelation(scope.row.relationId)"
                    v-hasPermi="['ticket:relation:remove']"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </template>
      </el-skeleton>
    </el-drawer>

    <el-dialog v-model="columnConfigOpen" title="列设置" width="520px" append-to-body>
      <el-checkbox-group v-model="visibleIssueColumnKeys">
        <el-row :gutter="12">
          <el-col v-for="item in issueColumnOptions" :key="item.key" :span="12" class="mb8">
            <el-checkbox :label="item.key" :disabled="item.required">{{ item.label }}</el-checkbox>
          </el-col>
        </el-row>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="resetIssueColumnConfig">恢复默认</el-button>
        <el-button @click="columnConfigOpen = false">取消</el-button>
        <el-button type="primary" :loading="savingColumnConfig" @click="saveIssueColumnConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="TicketIssue">
import {
  addTicketIssue,
  addTicketRelation,
  bindTicketIssue,
  confirmTicketRelation,
  delTicketRelation,
  getTicketIssue,
  getTicketStatClassificationOptions,
  listTicketIssues,
  listTicketModuleOptions,
  listTicketProjectOptions,
  listTicketUserOptions,
  unbindTicketIssue,
  updateTicketIssue,
} from '@/api/ticket/ticket'
import { getCurrentUserConfig, saveCurrentUserConfig } from '@/api/system/userConfig'
import { severityOptions } from '../constants'
import { useRoute, useRouter } from 'vue-router'

const { proxy } = getCurrentInstance()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const saving = ref(false)
const binding = ref(false)
const relationSaving = ref(false)
const detailLoading = ref(false)
const open = ref(false)
const isEdit = ref(false)
const showSearch = ref(true)
const detailOpen = ref(false)

const issueList = ref([])
const total = ref(0)
const projectOptions = ref([])
const allModuleOptions = ref([])
const ownerOptions = ref([])
const problemPatternOptions = ref([])
const columnConfigOpen = ref(false)
const savingColumnConfig = ref(false)
const visibleIssueColumnKeys = ref([
  'issueNo',
  'title',
  'status',
  'severity',
  'projectName',
  'moduleName',
  'rootCauseType',
  'problemPatternName',
  'ownerName',
  'affectedTicketCount',
  'updateTime',
])

const issueColumnOptions = [
  { key: 'issueNo', label: '问题编号', required: true },
  { key: 'title', label: '问题标题', required: true },
  { key: 'status', label: '状态', required: true },
  { key: 'severity', label: '严重等级' },
  { key: 'projectName', label: '项目' },
  { key: 'moduleName', label: '模块' },
  { key: 'rootCauseType', label: '根因分类' },
  { key: 'problemPatternName', label: '细分问题' },
  { key: 'ownerName', label: '负责人' },
  { key: 'affectedTicketCount', label: '影响工单数' },
  { key: 'updateTime', label: '更新时间' },
]
const defaultIssueColumnKeys = issueColumnOptions.map((item) => item.key)
const requiredIssueColumnKeys = issueColumnOptions.filter((item) => item.required).map((item) => item.key)

const detail = ref({})

const issueStatusOptions = [
  { label: '未开始', value: 'open', type: 'info' },
  { label: '处理中', value: 'processing', type: 'warning' },
  { label: '已解决', value: 'resolved', type: 'success' },
  { label: '已关闭', value: 'closed', type: 'success' },
]

const relationTypeOptions = [
  { label: '主归因', value: 'primary' },
  { label: '相似确认', value: 'similar' },
  { label: '重复工单', value: 'duplicate' },
  { label: '相关工单', value: 'related' },
  { label: '手工归因', value: 'manual' },
]

const relationSourceOptions = [
  { label: '手工', value: 'manual' },
  { label: 'AI', value: 'ai' },
  { label: '系统', value: 'system' },
]

const queryParams = ref({
  pageNum: 1,
  pageSize: 20,
  keyword: '',
  issueNo: '',
  title: '',
  status: '',
  projectId: '',
  moduleId: '',
  ownerId: '',
  problemPatternCode: '',
})

const form = ref(createDefaultForm())
const bindForm = ref(createDefaultBindForm())
const relationForm = ref(createDefaultRelationForm())

const rules = {
  title: [{ required: true, message: '问题标题不能为空', trigger: 'blur' }],
}

const queryModuleOptions = computed(() => filterModules(queryParams.value.projectId))
const formModuleOptions = computed(() => filterModules(form.value.projectId))
const detailTicketOptions = computed(() =>
  (detail.value.tickets || []).map((item) => ({
    ticketId: Number(item.ticketId || item.ticket_id || 0),
    label: `${item.ticketNo || item.ticket_no || item.ticketId} ${item.title || ''}`.trim(),
  }))
)

const dialogTitle = computed(() => (isEdit.value ? '修改问题实例' : '新增问题实例'))

function createDefaultForm() {
  return {
    issueId: undefined,
    issueNo: '',
    title: '',
    summary: '',
    status: 'open',
    severity: '',
    projectId: '',
    projectName: '',
    moduleId: '',
    moduleName: '',
    rootCauseType: '',
    problemPatternCode: '',
    problemPatternName: '',
    ownerId: '',
    ownerName: '',
    remark: '',
  }
}

function createDefaultBindForm() {
  return {
    ticketId: undefined,
    relationType: 'manual',
    confirmed: true,
    remark: '',
  }
}

function createDefaultRelationForm() {
  return {
    sourceTicketId: undefined,
    targetTicketId: undefined,
    relationType: 'related',
    confidence: 0.8,
    source: 'manual',
    confirmed: false,
    remark: '',
  }
}

function normalizeOptionRows(rows = []) {
  return (Array.isArray(rows) ? rows : [])
    .map((item) => ({
      ...item,
      value: item.value ?? item.code ?? item.userId ?? item.id,
      label: String(item.label || item.name || item.userName || item.nickName || item.projectName || item.moduleName || '').trim(),
    }))
    .filter((item) => item.value !== undefined && item.value !== null && String(item.value).trim() !== '')
}

function normalizeIssueColumnKeys(value) {
  const rawKeys = Array.isArray(value?.visibleColumns) ? value.visibleColumns : value
  const validKeys = new Set(issueColumnOptions.map((item) => item.key))
  const normalized = (Array.isArray(rawKeys) ? rawKeys : defaultIssueColumnKeys)
    .map((item) => String(item || '').trim())
    .filter((item) => validKeys.has(item))
  requiredIssueColumnKeys.forEach((key) => {
    if (!normalized.includes(key)) {
      normalized.push(key)
    }
  })
  return normalized.length ? normalized : [...defaultIssueColumnKeys]
}

function isIssueColumnVisible(key) {
  return visibleIssueColumnKeys.value.includes(key)
}

function buildModuleOptionLabel(item) {
  const moduleName = String(item.moduleName || '').trim()
  const moduleCode = String(item.moduleCode || '').trim()
  return [moduleName, moduleCode ? `[${moduleCode}]` : ''].filter(Boolean).join(' ')
}

function filterModules(projectId) {
  const resolvedProjectId = Number(projectId)
  return resolvedProjectId
    ? allModuleOptions.value.filter((item) => Number(item.projectId) === resolvedProjectId)
    : allModuleOptions.value
}

function getIssueStatusTagType(value) {
  const item = issueStatusOptions.find((row) => row.value === String(value || '').trim())
  return item?.type || 'info'
}

function formatIssueStatus(value) {
  const item = issueStatusOptions.find((row) => row.value === String(value || '').trim())
  return item?.label || value || '-'
}

function formatRelationType(value) {
  const item = relationTypeOptions.find((row) => row.value === String(value || '').trim())
  return item?.label || value || '-'
}

function formatRelationTicket(ticketNo, title) {
  const no = String(ticketNo || '').trim()
  const text = String(title || '').trim()
  return [no, text].filter(Boolean).join(' ') || '-'
}

function formatConfidence(value) {
  if (value === undefined || value === null || value === '') {
    return '-'
  }
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric.toFixed(2) : String(value)
}

function loadProjectOptions() {
  return listTicketProjectOptions().then((response) => {
    projectOptions.value = Array.isArray(response.data) ? response.data : []
  })
}

function loadModuleOptions() {
  return listTicketModuleOptions({}).then((response) => {
    allModuleOptions.value = Array.isArray(response.data) ? response.data : []
  })
}

function loadOwnerOptions() {
  return listTicketUserOptions().then((response) => {
    ownerOptions.value = normalizeOptionRows(response.data)
  })
}

function loadProblemPatternOptions() {
  return getTicketStatClassificationOptions().then((response) => {
    const config = response.data || {}
    problemPatternOptions.value = normalizeOptionRows(config.problemPatterns)
  }).catch(() => {
    problemPatternOptions.value = []
  })
}

function loadBaseOptions() {
  return Promise.all([
    loadProjectOptions(),
    loadModuleOptions(),
    loadOwnerOptions(),
    loadProblemPatternOptions(),
    loadIssueColumnConfig(),
  ])
}

function loadIssueColumnConfig() {
  return getCurrentUserConfig('ticket', 'ticket_issue_list_columns')
    .then((response) => {
      visibleIssueColumnKeys.value = normalizeIssueColumnKeys(response.data?.configValue)
    })
    .catch(() => {
      visibleIssueColumnKeys.value = [...defaultIssueColumnKeys]
    })
}

function saveIssueColumnConfig() {
  savingColumnConfig.value = true
  visibleIssueColumnKeys.value = normalizeIssueColumnKeys(visibleIssueColumnKeys.value)
  return saveCurrentUserConfig({
    configType: 'ticket',
    configKey: 'ticket_issue_list_columns',
    configValue: {
      visibleColumns: visibleIssueColumnKeys.value,
    },
    remark: '问题实例列表显示列配置',
  })
    .then(() => {
      columnConfigOpen.value = false
      proxy.$modal.msgSuccess('保存成功')
    })
    .finally(() => {
      savingColumnConfig.value = false
    })
}

function resetIssueColumnConfig() {
  visibleIssueColumnKeys.value = [...defaultIssueColumnKeys]
}

function buildQueryParams() {
  return Object.fromEntries(
    Object.entries(queryParams.value).filter(([, value]) => value !== undefined && value !== null && value !== '')
  )
}

function getList() {
  loading.value = true
  return listTicketIssues(buildQueryParams()).then((response) => {
    issueList.value = response.rows || []
    total.value = response.total || 0
  }).finally(() => {
    loading.value = false
  })
}

function resetQuery() {
  proxy.resetForm('queryRef')
  queryParams.value = {
    pageNum: 1,
    pageSize: 20,
    keyword: '',
    issueNo: '',
    title: '',
    status: '',
    projectId: '',
    moduleId: '',
    ownerId: '',
    problemPatternCode: '',
  }
  handleQuery()
}

function handleQuery() {
  queryParams.value.pageNum = 1
  getList()
}

function handleAdd() {
  isEdit.value = false
  form.value = createDefaultForm()
  open.value = true
}

function handleEdit(row) {
  isEdit.value = true
  detailLoading.value = true
  getTicketIssue(row.issueId).then((response) => {
    form.value = buildFormFromIssue(response.data || row)
    open.value = true
  }).finally(() => {
    detailLoading.value = false
  })
}

function handleDetail(row) {
  openIssueDetail(row.issueId)
}

function buildFormFromIssue(issue) {
  const data = issue || {}
  return {
    issueId: data.issueId || data.issue_id,
    issueNo: data.issueNo || data.issue_no || '',
    title: data.title || '',
    summary: data.summary || '',
    status: data.status || 'open',
    severity: data.severity || '',
    projectId: data.projectId || data.project_id || '',
    projectName: data.projectName || data.project_name || '',
    moduleId: data.moduleId || data.module_id || '',
    moduleName: data.moduleName || data.module_name || '',
    rootCauseType: data.rootCauseType || data.root_cause_type || '',
    problemPatternCode: data.problemPatternCode || data.problem_pattern_code || '',
    problemPatternName: data.problemPatternName || data.problem_pattern_name || '',
    ownerId: data.ownerId || data.owner_id || '',
    ownerName: data.ownerName || data.owner_name || '',
    remark: data.remark || '',
  }
}

function openIssueDetail(issueId) {
  const resolvedIssueId = Number(issueId || 0)
  if (!Number.isFinite(resolvedIssueId) || resolvedIssueId <= 0) {
    proxy.$modal.msgWarning('问题实例ID无效')
    return
  }
  detailLoading.value = true
  detailOpen.value = true
  getTicketIssue(resolvedIssueId).then((response) => {
    detail.value = response.data || {}
  }).finally(() => {
    detailLoading.value = false
  })
}

function openIssueTickets(row) {
  openIssueDetail(row.issueId)
}

function submitForm() {
  if (!form.value.title?.trim()) {
    proxy.$modal.msgWarning('问题标题不能为空')
    return
  }
  const payload = { ...form.value }
  saving.value = true
  const request = isEdit.value ? updateTicketIssue(payload) : addTicketIssue(payload)
  request.then((response) => {
    proxy.$modal.msgSuccess(isEdit.value ? '问题实例更新成功' : '问题实例创建成功')
    open.value = false
    getList()
    const issueId = response?.data?.issueId || response?.data?.issue_id || payload.issueId
    if (!isEdit.value && issueId) {
      openIssueDetail(issueId)
    }
  }).finally(() => {
    saving.value = false
  })
}

function resetForm() {
  form.value = createDefaultForm()
  proxy.resetForm('formRef')
}

function handleFormProjectChange(value) {
  const option = projectOptions.value.find((item) => Number(item.projectId) === Number(value))
  form.value.projectName = option?.projectName || ''
  form.value.moduleId = ''
  form.value.moduleName = ''
}

function handleFormModuleChange(value) {
  const option = formModuleOptions.value.find((item) => Number(item.moduleId) === Number(value))
  form.value.moduleName = option ? buildModuleOptionLabel(option) : ''
}

function handleOwnerChange(value) {
  const option = ownerOptions.value.find((item) => Number(item.userId) === Number(value))
  form.value.ownerName = option?.label || ''
}

function handlePatternChange(value) {
  const option = problemPatternOptions.value.find((item) => String(item.value) === String(value || '').trim())
  form.value.problemPatternName = option?.label || ''
}

function handleBindTicket() {
  const ticketId = Number(bindForm.value.ticketId)
  if (!Number.isFinite(ticketId) || ticketId <= 0) {
    proxy.$modal.msgWarning('请输入有效工单ID')
    return
  }
  if (!detail.value.issueId) {
    proxy.$modal.msgWarning('当前问题实例不存在')
    return
  }
  binding.value = true
  bindTicketIssue(ticketId, {
    issueId: detail.value.issueId,
    relationType: bindForm.value.relationType || 'manual',
    confirmed: bindForm.value.confirmed !== false,
    remark: bindForm.value.remark || '',
  }).then(() => {
    proxy.$modal.msgSuccess('工单绑定成功')
    bindForm.value = createDefaultBindForm()
    openIssueDetail(detail.value.issueId)
    getList()
  }).finally(() => {
    binding.value = false
  })
}

function handleAddRelation() {
  const sourceTicketId = Number(relationForm.value.sourceTicketId)
  const targetTicketId = Number(relationForm.value.targetTicketId)
  if (!Number.isFinite(sourceTicketId) || !Number.isFinite(targetTicketId) || sourceTicketId <= 0 || targetTicketId <= 0) {
    proxy.$modal.msgWarning('请选择有效的源工单和目标工单')
    return
  }
  relationSaving.value = true
  addTicketRelation({
    sourceTicketId,
    targetTicketId,
    relationType: relationForm.value.relationType || 'related',
    confidence: relationForm.value.confidence,
    source: relationForm.value.source || 'manual',
    confirmed: relationForm.value.confirmed === true,
    remark: relationForm.value.remark || '',
  }).then(() => {
    proxy.$modal.msgSuccess('补充关系创建成功')
    relationForm.value = createDefaultRelationForm()
    if (detail.value.issueId) {
      openIssueDetail(detail.value.issueId)
    }
  }).finally(() => {
    relationSaving.value = false
  })
}

function handleConfirmRelation(relationId) {
  if (!relationId) {
    proxy.$modal.msgWarning('关系ID无效')
    return
  }
  confirmTicketRelation(relationId).then(() => {
    proxy.$modal.msgSuccess('关系已确认')
    if (detail.value.issueId) {
      openIssueDetail(detail.value.issueId)
    }
  })
}

function handleDeleteRelation(relationId) {
  if (!relationId) {
    proxy.$modal.msgWarning('关系ID无效')
    return
  }
  proxy.$modal.confirm('是否确认删除该补充关系？').then(() => {
    return delTicketRelation(relationId)
  }).then(() => {
    proxy.$modal.msgSuccess('关系已删除')
    if (detail.value.issueId) {
      openIssueDetail(detail.value.issueId)
    }
  })
}

function handleUnbindTicket(ticketId) {
  const resolvedTicketId = Number(ticketId)
  if (!Number.isFinite(resolvedTicketId) || resolvedTicketId <= 0) {
    proxy.$modal.msgWarning('工单ID无效')
    return
  }
  proxy.$modal.confirm('是否确认解除该工单与当前问题实例的归因？').then(() => {
    return unbindTicketIssue(resolvedTicketId)
  }).then(() => {
    proxy.$modal.msgSuccess('工单已解绑')
    if (detail.value.issueId) {
      openIssueDetail(detail.value.issueId)
    }
    getList()
  })
}

function openTicketDetail(ticketId) {
  const resolvedTicketId = Number(ticketId)
  if (!Number.isFinite(resolvedTicketId) || resolvedTicketId <= 0) {
    proxy.$modal.msgWarning('工单ID无效')
    return
  }
  const resolved = router.resolve({
    name: 'TicketDetail',
    params: { ticketId: resolvedTicketId },
  })
  window.open(resolved.href, '_blank', 'noopener')
}

function openIssueManagement() {
  const resolved = router.resolve({
    name: 'TicketIssue',
  })
  window.open(resolved.href, '_blank', 'noopener')
}

function scrollToBindForm() {
  const element = document.getElementById('bind-issue-ticket-form')
  element?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

watch(
  () => route.query.issueId,
  (value) => {
    const issueId = Number(value || 0)
    if (Number.isFinite(issueId) && issueId > 0) {
      openIssueDetail(issueId)
    }
  },
  { immediate: true }
)

onMounted(() => {
  loadBaseOptions()
  getList()
})
</script>

<style scoped>
.ticket-issue-page {
  padding-bottom: 16px;
}

.issue-panel {
  margin-top: 16px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
