<template>
  <div class="app-container ticket-log-pull-record-page">
    <el-form ref="queryRef" :model="queryParams" :inline="true" v-show="showSearch" class="mb16">
      <el-form-item label="关联工单" prop="ticketId">
        <el-select
          v-model="queryParams.ticketId"
          placeholder="工单编号/标题"
          clearable
          filterable
          remote
          reserve-keyword
          :remote-method="searchTicketOptions"
          :loading="ticketLoading"
          style="width: 260px"
        >
          <el-option
            v-for="item in ticketOptions"
            :key="item.ticketId"
            :label="item.label"
            :value="item.ticketId"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="全部状态" clearable style="width: 160px">
          <el-option v-for="item in logPullStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键字" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="工单、异常、摘要、路径"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="商家" prop="vendorId">
        <el-select
          v-model="queryParams.vendorId"
          placeholder="选择商家"
          clearable
          filterable
          style="width: 220px"
          @change="handleQueryVendorChange"
        >
          <el-option
            v-for="item in vendorOptions"
            :key="item.vendorId"
            :label="item.label"
            :value="item.vendorId"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="门店" prop="storeId">
        <el-select
          v-model="queryParams.storeId"
          placeholder="先选择商家"
          clearable
          filterable
          :disabled="!queryParams.vendorId"
          style="width: 260px"
        >
          <el-option
            v-for="item in queryStoreOptions"
            :key="item.storeId"
            :label="item.label"
            :value="item.storeId"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="POS" prop="posNo">
        <el-input-number v-model="queryParams.posNo" :min="1" controls-position="right" placeholder="posNo" style="width: 150px" />
      </el-form-item>
      <el-form-item label="拉取日期" prop="modifyTime">
        <el-date-picker
          v-model="queryParams.modifyTime"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择拉取日期"
          clearable
          style="width: 170px"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="openCreateDialog" v-hasPermi="['ticket:logpull:add']">
          新增拉取
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
    </el-row>

    <el-table v-loading="loading" :data="recordList" row-key="id">
      <el-table-column label="记录ID" prop="id" width="180" show-overflow-tooltip />
      <el-table-column label="关联工单" min-width="220" show-overflow-tooltip>
        <template #default="scope">
          <div v-if="scope.row.ticketId">
            <div class="ticket-title">{{ scope.row.ticketNo || '-' }}</div>
            <div class="ticket-subtitle">{{ scope.row.ticketTitle || '-' }}</div>
          </div>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120" align="center">
        <template #default="scope">
          <el-tag :type="getLogPullStatusTagType(scope.row.status)">
            {{ scope.row.statusDesc || getOptionLabel(logPullStatusOptions, scope.row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="数据类型" width="110" align="center">
        <template #default="scope">{{ getOptionLabel(logPullDataTypeOptions, scope.row.commandDataType) }}</template>
      </el-table-column>
      <el-table-column label="vendor/store/pos" min-width="160" show-overflow-tooltip>
        <template #default="scope">
          {{ scope.row.vendorId || '-' }}/{{ scope.row.storeId || '-' }}/{{ scope.row.posNo || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="保存方式" width="100" align="center">
        <template #default="scope">{{ getOptionLabel(logPullStorageModeOptions, scope.row.storageMode) }}</template>
      </el-table-column>
      <el-table-column label="摘要/异常" min-width="240" prop="contentSummary" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.errorMessage || scope.row.contentSummary || '-' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="openContentDialog(scope.row)" v-hasPermi="['ticket:logpull:query']">
            查看日志
          </el-button>
          <el-button link type="warning" icon="Refresh" @click="retryLogPull(scope.row)" :disabled="actionLoading" v-hasPermi="['ticket:logpull:add']">
            重新拉取
          </el-button>
          <el-button
            link
            type="success"
            icon="Download"
            @click="redownloadLogPull(scope.row)"
            :disabled="actionLoading || (!scope.row.commandResultUrl && !scope.row.storagePath)"
            v-hasPermi="['ticket:logpull:add']"
          >
            重新下载
          </el-button>
          <el-button
            link
            type="danger"
            icon="Scissor"
            @click="reextractLogPull(scope.row)"
            :disabled="actionLoading || (!scope.row.commandResultUrl && !scope.row.storagePath)"
            v-hasPermi="['ticket:logpull:add']"
          >
            重新截取
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
      v-model="createOpen"
      title="新增日志拉取记录"
      width="860px"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetCreateForm"
    >
      <el-form ref="createRef" :model="createForm" :rules="createRules" label-width="110px">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="可选择关联工单，也可以不选择。未关联工单时仅创建独立日志拉取记录，不能启用自动AI分析。"
          class="mb16"
        />
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="关联工单">
              <el-select
                v-model="createForm.ticketId"
                placeholder="可选，关联工单"
                clearable
                filterable
                remote
                reserve-keyword
                :remote-method="searchTicketOptions"
                :loading="ticketLoading"
                style="width: 100%"
                @change="handleCreateTicketChange"
              >
                <el-option
                  v-for="item in ticketOptions"
                  :key="item.ticketId"
                  :label="item.label"
                  :value="item.ticketId"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="自动AI">
              <el-switch
                v-model="createForm.autoAiEnabled"
                inline-prompt
                active-text="是"
                inactive-text="否"
                :disabled="!createForm.ticketId"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="商家" prop="vendorId">
              <el-select
                v-model="createForm.vendorId"
                placeholder="选择商家"
                clearable
                filterable
                style="width: 100%"
                @change="handleCreateVendorChange"
              >
                <el-option
                  v-for="item in vendorOptions"
                  :key="item.vendorId"
                  :label="item.label"
                  :value="item.vendorId"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="门店" prop="storeId">
              <el-select
                v-model="createForm.storeId"
                placeholder="先选择商家"
                clearable
                filterable
                :disabled="!createForm.vendorId"
                style="width: 100%"
              >
                <el-option
                  v-for="item in createStoreOptions"
                  :key="item.storeId"
                  :label="item.label"
                  :value="item.storeId"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="posNo" prop="posNo">
              <el-input-number v-model="createForm.posNo" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数据类型">
              <el-select v-model="createForm.commandDataType" placeholder="请选择" style="width: 100%">
                <el-option v-for="item in logPullDataTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="modifyTime">
              <el-date-picker
                v-model="createForm.modifyTime"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="按日期拉取"
                clearable
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="path">
              <el-input v-model="createForm.path" placeholder="可选，按路径拉取" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="时间方式">
              <el-radio-group v-model="createForm.timeRangeMode">
                <el-radio value="between">开始 + 结束</el-radio>
                <el-radio value="point">时间点 + 前后范围</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <template v-if="createForm.timeRangeMode === 'between'">
            <el-col :span="12">
              <el-form-item label="开始时间">
                <el-date-picker
                  v-model="createForm.logBeginTime"
                  type="datetime"
                  value-format="YYYY-MM-DD HH:mm:ss"
                  placeholder="必填，筛选日志开始时间"
                  clearable
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="结束时间">
                <el-date-picker
                  v-model="createForm.logEndTime"
                  type="datetime"
                  value-format="YYYY-MM-DD HH:mm:ss"
                  placeholder="必填，筛选日志结束时间"
                  clearable
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
          </template>
          <template v-else>
            <el-col :span="12">
              <el-form-item label="时间点">
                <el-date-picker
                  v-model="createForm.logPointTime"
                  type="datetime"
                  value-format="YYYY-MM-DD HH:mm:ss"
                  placeholder="必填，基准时间点"
                  clearable
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="前后范围">
                <div class="time-range-inline">
                  <span>前</span>
                  <el-input-number v-model="createForm.rangeBeforeMinutes" :min="0" controls-position="right" />
                  <span>分钟，后</span>
                  <el-input-number v-model="createForm.rangeAfterMinutes" :min="0" controls-position="right" />
                  <span>分钟</span>
                </div>
              </el-form-item>
            </el-col>
          </template>
          <el-col :span="12">
            <el-form-item label="单文件上限">
              <el-input-number v-model="createForm.fileMaxSize" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="压缩包上限">
              <el-input-number v-model="createForm.zipMaxSize" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保存方式">
              <el-select v-model="createForm.storageMode" placeholder="请选择" style="width: 100%">
                <el-option
                  v-for="item in logPullStorageModeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="AI Agent">
              <el-select v-model="createForm.aiAgentCode" placeholder="选择Agent" filterable clearable :disabled="!createForm.autoAiEnabled" style="width: 100%">
                <el-option v-for="item in agentOptions" :key="item.agentCode" :label="`${item.agentName || item.agentCode} [${item.agentCode}]`" :value="item.agentCode" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreateForm">提交拉取</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="contentOpen"
      title="日志内容"
      width="80%"
      top="5vh"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetContentDialog"
    >
      <div v-loading="contentLoading">
        <el-descriptions :column="3" border class="mb16">
          <el-descriptions-item label="记录ID">{{ selectedRecord?.id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="关联工单">
            <span v-if="selectedRecord?.ticketId">
              {{ selectedRecord?.ticketNo || selectedRecord?.ticketId }} {{ selectedRecord?.ticketTitle || '' }}
            </span>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag v-if="selectedRecord?.status" :type="getLogPullStatusTagType(selectedRecord.status)">
              {{ selectedRecord.statusDesc || getOptionLabel(logPullStatusOptions, selectedRecord.status) }}
            </el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="查看模式">
            <el-radio-group v-model="viewForm.viewMode">
              <el-radio value="stored">入库内容</el-radio>
              <el-radio value="archive">原始文档</el-radio>
            </el-radio-group>
          </el-descriptions-item>
          <el-descriptions-item label="截取方式" :span="2">
            <el-radio-group v-model="viewForm.viewRangeMode">
              <el-radio value="between">开始 + 结束</el-radio>
              <el-radio value="point">时间点 + 前后范围</el-radio>
            </el-radio-group>
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">
            <el-date-picker
              v-model="viewForm.logBeginTime"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              placeholder="开始时间"
              clearable
              :disabled="viewForm.viewMode !== 'archive' || viewForm.viewRangeMode !== 'between'"
              class="log-view-time-picker"
            />
          </el-descriptions-item>
          <el-descriptions-item label="结束时间">
            <el-date-picker
              v-model="viewForm.logEndTime"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              placeholder="结束时间"
              clearable
              :disabled="viewForm.viewMode !== 'archive' || viewForm.viewRangeMode !== 'between'"
              class="log-view-time-picker"
            />
          </el-descriptions-item>
          <el-descriptions-item label="时间点">
            <el-date-picker
              v-model="viewForm.logPointTime"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              placeholder="时间点"
              clearable
              :disabled="viewForm.viewMode !== 'archive' || viewForm.viewRangeMode !== 'point'"
              class="log-view-time-picker"
            />
          </el-descriptions-item>
          <el-descriptions-item label="前后范围">
            <div class="time-range-inline">
              <span>前</span>
              <el-input-number
                v-model="viewForm.rangeBeforeMinutes"
                :min="0"
                controls-position="right"
                :disabled="viewForm.viewMode !== 'archive' || viewForm.viewRangeMode !== 'point'"
              />
              <span>分钟，后</span>
              <el-input-number
                v-model="viewForm.rangeAfterMinutes"
                :min="0"
                controls-position="right"
                :disabled="viewForm.viewMode !== 'archive' || viewForm.viewRangeMode !== 'point'"
              />
              <span>分钟</span>
            </div>
          </el-descriptions-item>
          <el-descriptions-item label="日志字符数">{{ contentDetail?.contentCharCount || 0 }}</el-descriptions-item>
          <el-descriptions-item label="命中条目">{{ contentDetail?.matchedEntryCount || 0 }}</el-descriptions-item>
          <el-descriptions-item label="压缩包文件数">{{ contentDetail?.archiveEntryCount || 0 }}</el-descriptions-item>
          <el-descriptions-item label="归档地址" :span="2">{{ contentDetail?.storagePath || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div class="content-toolbar">
          <el-input
            v-model="contentKeyword"
            placeholder="本地过滤关键字"
            clearable
            class="content-keyword"
          />
          <el-switch v-model="contentWrapEnabled" inline-prompt active-text="换行" inactive-text="不换行" />
          <el-button type="primary" @click="reloadContent">{{ viewForm.viewMode === 'archive' ? '按当前范围查看' : '查看入库内容' }}</el-button>
          <el-button type="warning" @click="retryLogPull(selectedRecord)" :disabled="actionLoading" v-hasPermi="['ticket:logpull:add']">重新拉取</el-button>
          <el-button type="success" @click="redownloadLogPull(selectedRecord)" :disabled="actionLoading || !canDownloadCurrent" v-hasPermi="['ticket:logpull:add']">重新下载</el-button>
          <el-button type="danger" @click="reextractLogPull(selectedRecord)" :disabled="actionLoading || viewForm.viewMode !== 'archive'" v-hasPermi="['ticket:logpull:add']">重新截取</el-button>
        </div>
        <el-alert
          v-if="contentDetail?.contentTruncated"
          type="warning"
          :closable="false"
          show-icon
          title="当前日志文本已按配置截断入库，如需更多内容请调整字符上限后重新拉取。"
          class="mb16"
        />
        <pre :class="['log-content-block', { 'log-content-wrap': contentWrapEnabled }]">{{ filteredContentText }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup name="TicketLogPullRecord">
import {
  createTicketLogPullRecord,
  getTicketLogPullContent,
  getTicketLogPullVendorStoreOptions,
  listTicket,
  listTicketLogPullRecords,
  redownloadTicketLogPull,
  reextractTicketLogPull,
  retryTicketLogPull
} from '@/api/ticket/ticket'
import { all as listAllAgents } from '@/api/hrm/agent'
import { getLogPullStatusTagType, getOptionLabel, logPullDataTypeOptions, logPullStatusOptions, logPullStorageModeOptions } from '../constants'

const { proxy } = getCurrentInstance()

const loading = ref(false)
const submitting = ref(false)
const actionLoading = ref(false)
const contentLoading = ref(false)
const createOpen = ref(false)
const contentOpen = ref(false)
const showSearch = ref(true)
const recordList = ref([])
const total = ref(0)
const ticketLoading = ref(false)
const ticketOptions = ref([])
const agentOptions = ref([])
const vendorOptions = ref([])
const selectedRecord = ref(null)
const contentDetail = ref(null)
const contentText = ref('')
const contentKeyword = ref('')
const contentWrapEnabled = ref(false)
const logPullRefreshTimer = ref(null)

const activeLogPullStatuses = ['created', 'submitting', 'polling', 'downloading', 'processing']

const queryParams = ref({
  pageNum: 1,
  pageSize: 10,
  ticketId: undefined,
  status: '',
  keyword: '',
  vendorId: undefined,
  storeId: undefined,
  posNo: undefined,
  modifyTime: ''
})

const createForm = ref(createDefaultForm())
const viewForm = ref(createDefaultViewForm())

const createRules = {
  vendorId: [{ required: true, message: 'vendorId 不能为空', trigger: 'change' }],
  storeId: [{ required: true, message: 'storeId 不能为空', trigger: 'change' }],
  posNo: [{ required: true, message: 'posNo 不能为空', trigger: 'blur' }]
}

function createDefaultForm() {
  return {
    ticketId: undefined,
    vendorId: undefined,
    storeId: undefined,
    posNo: undefined,
    commandDataType: 1,
    modifyTime: '',
    path: '',
    timeRangeMode: 'between',
    logBeginTime: '',
    logEndTime: '',
    logPointTime: '',
    rangeBeforeMinutes: 30,
    rangeAfterMinutes: 30,
    fileMaxSize: 500,
    zipMaxSize: 500,
    storageMode: 'local',
    autoAiEnabled: false,
    aiAgentCode: ''
  }
}

function createDefaultViewForm() {
  return {
    viewMode: 'stored',
    viewRangeMode: 'between',
    logBeginTime: '',
    logEndTime: '',
    logPointTime: '',
    rangeBeforeMinutes: 30,
    rangeAfterMinutes: 30
  }
}

function getList() {
  loading.value = true
  listTicketLogPullRecords(queryParams.value).then(response => {
    recordList.value = response.rows || []
    total.value = response.total || 0
    updateAutoRefresh()
  }).finally(() => {
    loading.value = false
  })
}

function handleQuery() {
  queryParams.value.pageNum = 1
  getList()
}

function resetQuery() {
  queryParams.value = {
    pageNum: 1,
    pageSize: 10,
    ticketId: undefined,
    status: '',
    keyword: '',
    vendorId: undefined,
    storeId: undefined,
    posNo: undefined,
    modifyTime: ''
  }
  handleQuery()
}

function loadTicketOptions(keyword = '') {
  ticketLoading.value = true
  return listTicket({ keyword, pageNum: 1, pageSize: 20 }).then(response => {
    const rows = response.rows || []
    const options = rows.map(item => ({
      ticketId: item.ticketId,
      ticketNo: item.ticketNo,
      ticketTitle: item.title,
      label: `${item.ticketNo || item.ticketId} ${item.title || ''}`.trim()
    }))
    const currentMap = new Map(ticketOptions.value.map(item => [item.ticketId, item]))
    options.forEach(item => currentMap.set(item.ticketId, item))
    ticketOptions.value = Array.from(currentMap.values())
  }).finally(() => {
    ticketLoading.value = false
  })
}

function searchTicketOptions(keyword) {
  loadTicketOptions(keyword)
}

function loadAgentOptions() {
  return listAllAgents().then(response => {
    const rows = response.data || []
    agentOptions.value = Array.isArray(rows) ? rows : []
  })
}

function normalizeVendorOptions(rows = []) {
  return rows.map(item => ({
    vendorId: Number(item.vendorId),
    vendorCode: String(item.vendorCode || '').trim(),
    vendorName: String(item.vendorName || item.vendorId || '').trim(),
    label: buildVendorOptionLabel(item),
    stores: Array.isArray(item.stores)
      ? item.stores.map(store => ({
        storeId: Number(store.storeId),
        storeCode: String(store.storeCode || '').trim(),
        storeName: String(store.storeName || store.storeId || '').trim(),
        label: buildStoreOptionLabel(store),
      }))
      : []
  }))
}

function buildVendorOptionLabel(vendor) {
  const name = String(vendor.vendorName || vendor.vendorId || '').trim()
  const code = String(vendor.vendorCode || '').trim()
  const id = String(vendor.vendorId || '').trim()
  return [name, code, id ? `[${id}]` : ''].filter(Boolean).join(' ')
}

function buildStoreOptionLabel(store) {
  const name = String(store.storeName || store.storeId || '').trim()
  const code = String(store.storeCode || '').trim()
  const id = String(store.storeId || '').trim()
  return [name, code, id ? `[${id}]` : ''].filter(Boolean).join(' ')
}

function loadVendorOptions() {
  return getTicketLogPullVendorStoreOptions().then(response => {
    vendorOptions.value = normalizeVendorOptions(response.data?.vendors || [])
  })
}

function getVendorStoreOptions(vendorId) {
  const resolvedVendorId = Number(vendorId)
  if (!resolvedVendorId) {
    return []
  }
  const vendor = vendorOptions.value.find(item => item.vendorId === resolvedVendorId)
  return vendor?.stores || []
}

const queryStoreOptions = computed(() => getVendorStoreOptions(queryParams.value.vendorId))
const createStoreOptions = computed(() => getVendorStoreOptions(createForm.value.vendorId))

function resetStoreSelection(target, vendorId) {
  const storeId = Number(target.storeId)
  if (!storeId) {
    target.storeId = undefined
    return
  }
  const storeExists = getVendorStoreOptions(vendorId).some(item => item.storeId === storeId)
  if (!storeExists) {
    target.storeId = undefined
  }
}

function handleQueryVendorChange(vendorId) {
  resetStoreSelection(queryParams.value, vendorId)
}

function handleCreateVendorChange(vendorId) {
  resetStoreSelection(createForm.value, vendorId)
}

function openCreateDialog() {
  createForm.value = createDefaultForm()
  if (queryParams.value.ticketId) {
    createForm.value.ticketId = queryParams.value.ticketId
  }
  if (queryParams.value.vendorId) {
    createForm.value.vendorId = queryParams.value.vendorId
  }
  if (queryParams.value.storeId) {
    createForm.value.storeId = queryParams.value.storeId
  }
  if (queryParams.value.posNo) {
    createForm.value.posNo = queryParams.value.posNo
  }
  createOpen.value = true
  loadTicketOptions()
}

function handleCreateTicketChange(ticketId) {
  if (!ticketId) {
    createForm.value.autoAiEnabled = false
    createForm.value.aiAgentCode = ''
  }
}

function resetCreateForm() {
  createForm.value = createDefaultForm()
  if (proxy.$refs.createRef) {
    proxy.resetForm('createRef')
  }
}

function submitCreateForm() {
  proxy.$refs.createRef.validate(valid => {
    if (!valid) return
    if (!createForm.value.modifyTime && !createForm.value.path) {
      proxy.$modal.msgWarning('modifyTime 和 path 至少需要填写一个')
      return
    }
    if (createForm.value.timeRangeMode === 'between') {
      const hasAnyDirectValue = Boolean(createForm.value.logBeginTime || createForm.value.logEndTime)
      if (hasAnyDirectValue) {
        if (!createForm.value.logBeginTime || !createForm.value.logEndTime) {
          proxy.$modal.msgWarning('开始时间和结束时间需要同时填写')
          return
        }
        const begin = new Date(createForm.value.logBeginTime)
        const end = new Date(createForm.value.logEndTime)
        if (begin > end) {
          proxy.$modal.msgWarning('开始时间不能晚于结束时间')
          return
        }
      }
    } else if (createForm.value.timeRangeMode === 'point') {
      if (!createForm.value.logPointTime) {
        proxy.$modal.msgWarning('时间点不能为空')
        return
      }
      const beforeMinutes = Number(createForm.value.rangeBeforeMinutes ?? 0)
      const afterMinutes = Number(createForm.value.rangeAfterMinutes ?? 0)
      if (beforeMinutes === 0 && afterMinutes === 0) {
        proxy.$modal.msgWarning('时间点前后范围至少需要一侧大于 0')
        return
      }
    }
    if (createForm.value.autoAiEnabled && !createForm.value.ticketId) {
      proxy.$modal.msgWarning('未关联工单时不能启用自动AI分析')
      return
    }
    if (createForm.value.autoAiEnabled && !String(createForm.value.aiAgentCode || '').trim()) {
      proxy.$modal.msgWarning('启用自动AI分析时必须选择Agent')
      return
    }

    submitting.value = true
    const payload = {
      ...createForm.value,
      ticketId: createForm.value.ticketId || null
    }
    if (!payload.autoAiEnabled) {
      payload.aiAgentCode = ''
    }
    createTicketLogPullRecord(payload).then(() => {
      proxy.$modal.msgSuccess('日志拉取任务已提交')
      createOpen.value = false
      handleQuery()
    }).finally(() => {
      submitting.value = false
    })
  })
}

function resetContentDialog() {
  selectedRecord.value = null
  contentDetail.value = null
  contentText.value = ''
  contentKeyword.value = ''
  contentWrapEnabled.value = false
  viewForm.value = createDefaultViewForm()
}

function buildContentQuery() {
  const query = {
    viewMode: viewForm.value.viewMode
  }
  if (viewForm.value.viewMode === 'archive') {
    if (viewForm.value.viewRangeMode === 'between' && viewForm.value.logBeginTime && viewForm.value.logEndTime) {
      query.logBeginTime = viewForm.value.logBeginTime
      query.logEndTime = viewForm.value.logEndTime
    } else if (viewForm.value.viewRangeMode === 'point' && viewForm.value.logPointTime) {
      query.logPointTime = viewForm.value.logPointTime
      query.rangeBeforeMinutes = viewForm.value.rangeBeforeMinutes
      query.rangeAfterMinutes = viewForm.value.rangeAfterMinutes
    }
  }
  return query
}

function openContentDialog(row) {
  selectedRecord.value = row
  contentOpen.value = true
  viewForm.value = createDefaultViewForm()
  const commandContent = row.commandContent || row.command_content || {}
  const timeRangeMode = String(commandContent.timeRangeMode || '').trim().toLowerCase()
  if (timeRangeMode === 'point') {
    viewForm.value.viewMode = 'archive'
    viewForm.value.viewRangeMode = 'point'
    viewForm.value.logPointTime = commandContent.logPointTime || row.logPointTime || ''
    viewForm.value.rangeBeforeMinutes = commandContent.rangeBeforeMinutes ?? row.rangeBeforeMinutes ?? 30
    viewForm.value.rangeAfterMinutes = commandContent.rangeAfterMinutes ?? row.rangeAfterMinutes ?? 30
  } else if (timeRangeMode === 'between') {
    viewForm.value.viewMode = 'archive'
    viewForm.value.viewRangeMode = 'between'
    viewForm.value.logBeginTime = commandContent.logBeginTime || row.logBeginTime || ''
    viewForm.value.logEndTime = commandContent.logEndTime || row.logEndTime || ''
  } else if (row.logBeginTime && row.logEndTime) {
    viewForm.value.viewMode = 'archive'
    viewForm.value.viewRangeMode = 'between'
    viewForm.value.logBeginTime = row.logBeginTime
    viewForm.value.logEndTime = row.logEndTime
  }
  loadContent()
}

function loadContent() {
  if (!selectedRecord.value?.id) {
    return
  }
  contentLoading.value = true
  getTicketLogPullContent(selectedRecord.value.id, buildContentQuery()).then(response => {
    contentDetail.value = response.data || {}
    contentText.value = response.data?.text || ''
  }).finally(() => {
    contentLoading.value = false
  })
}

const filteredContentText = computed(() => {
  const raw = String(contentText.value || '')
  if (!contentKeyword.value.trim()) {
    return raw || '暂无可展示日志内容'
  }
  const keyword = contentKeyword.value.trim().toLowerCase()
  const filtered = raw
    .split(/\r?\n/)
    .filter(line => line.toLowerCase().includes(keyword))
    .join('\n')
  return filtered || '未匹配到日志内容'
})

const canDownloadCurrent = computed(() => Boolean(selectedRecord.value?.commandResultUrl || selectedRecord.value?.storagePath))

function reloadContent() {
  loadContent()
}

function runAction(request, successMessage, refreshContent = false) {
  if (actionLoading.value) {
    return
  }
  actionLoading.value = true
  request.then(() => {
    proxy.$modal.msgSuccess(successMessage)
    handleQuery()
    if (refreshContent) {
      loadContent()
    }
  }).finally(() => {
    actionLoading.value = false
  })
}

function retryLogPull(row) {
  if (!row?.id) return
  runAction(retryTicketLogPull(row.id), '已重新提交拉取任务')
}

function redownloadLogPull(row) {
  if (!row?.id) return
  runAction(redownloadTicketLogPull(row.id), '日志压缩包已重新下载', true)
}

function reextractLogPull(row) {
  if (!row?.id) return
  runAction(reextractTicketLogPull(row.id, buildContentQuery()), '日志已重新截取', true)
}

function updateAutoRefresh() {
  if (logPullRefreshTimer.value) {
    window.clearTimeout(logPullRefreshTimer.value)
    logPullRefreshTimer.value = null
  }
  const hasRunningTask = recordList.value.some(item => activeLogPullStatuses.includes(item.status))
  if (!hasRunningTask) {
    return
  }
  logPullRefreshTimer.value = window.setTimeout(() => {
    if (createOpen.value || contentOpen.value) {
      return
    }
    getList()
  }, 5000)
}

onMounted(() => {
  loadTicketOptions()
  loadAgentOptions()
  loadVendorOptions()
  getList()
})

onBeforeUnmount(() => {
  if (logPullRefreshTimer.value) {
    window.clearTimeout(logPullRefreshTimer.value)
    logPullRefreshTimer.value = null
  }
})
</script>

<style scoped>
.mb16 {
  margin-bottom: 16px;
}

.ticket-title {
  font-weight: 600;
}

.ticket-subtitle {
  color: #8c8c8c;
  font-size: 12px;
}

.time-range-inline {
  display: flex;
  align-items: center;
  gap: 8px;
}

.time-range-inline :deep(.el-input-number) {
  width: 140px;
}

.content-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.content-keyword {
  width: 260px;
}

.log-view-time-picker {
  width: 100%;
}

.log-content-block {
  min-height: 340px;
  margin: 0;
  padding: 16px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
  font-family: Consolas, 'Courier New', monospace;
  white-space: pre-wrap;
  word-break: break-word;
  overflow: auto;
}

.log-content-wrap {
  white-space: pre-wrap;
}
</style>
