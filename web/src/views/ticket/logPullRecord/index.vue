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
      <el-col :span="1.5">
        <el-button type="success" plain icon="FolderOpened" @click="openStoreConfigDialog" v-hasPermi="['ticket:logpull:config']">
          门店配置
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
      <el-table-column label="拉取日期" width="120">
        <template #default="scope">{{ scope.row.modifyTime || '-' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="420" fixed="right">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="openContentDialog(scope.row)" v-hasPermi="['ticket:logpull:query']">
            查看日志
          </el-button>
          <el-button
            link
            type="success"
            icon="Download"
            @click="downloadLogPull(scope.row)"
            :disabled="actionLoading"
            v-hasPermi="['ticket:logpull:query']"
          >
            下载日志
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
          <el-button
            link
            type="danger"
            icon="Delete"
            @click="deleteLogPull(scope.row)"
            :disabled="actionLoading"
            v-hasPermi="['ticket:logpull:remove']"
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
          <LogPullConfigFields
            v-model="createForm"
            :vendor-options="vendorOptions"
            :agent-options="agentOptions"
            :provider-options="providerOptions"
            :data-type-options="logPullDataTypeOptions"
            :storage-mode-options="logPullStorageModeOptions"
            :show-auto-ai="false"
          />
          <LogPullNotifyConfigFields
            v-model="createForm.notifyConfig"
            :push-options="pushOptions"
          />
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

    <el-dialog
      v-model="storeConfigOpen"
      title="门店配置"
      width="88%"
      top="5vh"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetStoreConfigQuery"
    >
      <el-form :model="storeConfigQuery" :inline="true" class="mb16">
        <el-form-item label="集团编号">
          <el-input v-model="storeConfigQuery.groupNo" placeholder="group_no" clearable style="width: 180px" @keyup.enter="handleStoreConfigQuery" />
        </el-form-item>
        <el-form-item label="商户编号">
          <el-input v-model="storeConfigQuery.venderNo" placeholder="vender_no" clearable style="width: 180px" @keyup.enter="handleStoreConfigQuery" />
        </el-form-item>
        <el-form-item label="机构编号">
          <el-input v-model="storeConfigQuery.orgNo" placeholder="org_no" clearable style="width: 180px" @keyup.enter="handleStoreConfigQuery" />
        </el-form-item>
        <el-form-item label="SAP机构编号">
          <el-input v-model="storeConfigQuery.sapOrgNo" placeholder="sap_org_no" clearable style="width: 180px" @keyup.enter="handleStoreConfigQuery" />
        </el-form-item>
        <el-form-item label="关键字">
          <el-input v-model="storeConfigQuery.keyword" placeholder="门店名称/编号" clearable style="width: 220px" @keyup.enter="handleStoreConfigQuery" />
        </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleStoreConfigQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetStoreConfigQuery">重置</el-button>
        <el-button type="success" plain icon="Download" @click="downloadStoreConfigTemplate">下载模板</el-button>
        <el-button type="warning" plain icon="Upload" @click="storeConfigImportOpen = true">导入配置</el-button>
      </el-form-item>
      </el-form>

      <el-table v-loading="storeConfigLoading" :data="storeConfigList" row-key="id">
        <el-table-column label="ID" prop="id" width="110" />
        <el-table-column label="集团编号" prop="groupNo" width="120" show-overflow-tooltip />
        <el-table-column label="商户编号" prop="venderNo" width="140" show-overflow-tooltip />
        <el-table-column label="区域编号" prop="regionNo" width="120" show-overflow-tooltip />
        <el-table-column label="机构编号" prop="orgNo" width="140" show-overflow-tooltip />
        <el-table-column label="SAP机构编号" prop="sapOrgNo" width="150" show-overflow-tooltip />
        <el-table-column label="机构名称" prop="orgName" min-width="180" show-overflow-tooltip />
        <el-table-column label="会员渠道" prop="platformNo" width="110" show-overflow-tooltip />
        <el-table-column label="公司代码" prop="companyNo" width="120" show-overflow-tooltip />
        <el-table-column label="状态" prop="status" width="90" align="center" />
        <el-table-column label="修改时间" prop="modifid" width="170">
          <template #default="scope">{{ parseTime(scope.row.modifid) }}</template>
        </el-table-column>
      </el-table>

      <pagination
        v-show="storeConfigTotal > 0"
        :total="storeConfigTotal"
        v-model:page="storeConfigQuery.pageNum"
        v-model:limit="storeConfigQuery.pageSize"
        @pagination="loadStoreConfigList"
      />
    </el-dialog>

    <el-dialog
      v-model="storeConfigImportOpen"
      title="导入门店配置"
      width="560px"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetStoreConfigImportDialog"
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="增量导入会按 vender_no / org_no / sap_org_no 匹配，存在则覆盖；覆盖导入会先清空旧数据再导入。"
        class="mb16"
      />
      <el-form :model="storeConfigImportForm" label-width="100px">
        <el-form-item label="导入方式">
          <el-radio-group v-model="storeConfigImportMode">
            <el-radio value="incremental">增量导入</el-radio>
            <el-radio value="overwrite">覆盖导入</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="导入文件">
          <el-upload
            ref="storeConfigUploadRef"
            :auto-upload="false"
            :show-file-list="false"
            :limit="1"
            accept=".xlsx"
            :on-change="handleStoreConfigUploadChange"
          >
            <template #trigger>
              <el-button type="primary" plain icon="Upload">选择 xlsx 文件</el-button>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <el-alert
        v-if="storeConfigImportResult"
        type="success"
        :closable="false"
        show-icon
        class="mb16"
        :title="`导入完成：新增 ${storeConfigImportResult.insertedCount || 0} 条，更新 ${storeConfigImportResult.updatedCount || 0} 条，失败 ${storeConfigImportResult.failedRows?.length || 0} 条。`"
      />
      <el-table v-if="storeConfigImportResult?.failedRows?.length" :data="storeConfigImportResult.failedRows" size="small" border>
        <el-table-column label="行号" prop="row" width="90" />
        <el-table-column label="失败原因" prop="reason" min-width="280" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <el-button @click="storeConfigImportOpen = false">取消</el-button>
        <el-button type="primary" :loading="storeConfigImporting" @click="submitStoreConfigImport">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="TicketLogPullRecord">
import {
  delTicketLogPull,
  createTicketLogPullRecord,
  downloadTicketLogPull,
  downloadTicketLogPullStoreConfigTemplate,
  getTicket,
  getTicketLogPullContent,
  getTicketLogPullVendorStoreOptions,
  listTicket,
  listTicketLogPullStoreConfigs,
  listTicketLogPullRecords,
  importTicketLogPullStoreConfigs,
  redownloadTicketLogPull,
  reextractTicketLogPull,
  retryTicketLogPull
} from '@/api/ticket/ticket'
import { all as listAllAgents } from '@/api/hrm/agent'
import { allPushConfig as listAllPushConfig } from '@/api/hrm/push'
import { listAiProviderOptions } from '@/api/system/aiprovider'
import { saveAs } from 'file-saver'
import LogPullConfigFields from '@/components/ticket/LogPullConfigFields.vue'
import LogPullNotifyConfigFields from '@/components/ticket/LogPullNotifyConfigFields.vue'
import { getLogPullStatusTagType, getOptionLabel, logPullDataTypeOptions, logPullStatusOptions, logPullStorageModeOptions } from '../constants'
import {
  buildOptionalLogPullTimeRangePayload,
  createDefaultLogPullNotifyConfig,
  getOptionalLogPullTimeRangeError,
  normalizeLogPullNotifyConfig
} from '../logPull.shared'
import { blobValidate } from '@/utils/ruoyi'

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
const providerOptions = ref([])
const vendorOptions = ref([])
const pushOptions = ref([])
const selectedRecord = ref(null)
const contentDetail = ref(null)
const contentText = ref('')
const contentKeyword = ref('')
const contentWrapEnabled = ref(false)
const logPullRefreshTimer = ref(null)
const storeConfigOpen = ref(false)
const storeConfigLoading = ref(false)
const storeConfigList = ref([])
const storeConfigTotal = ref(0)
const storeConfigImportOpen = ref(false)
const storeConfigImporting = ref(false)
const storeConfigImportResult = ref(null)
const storeConfigImportMode = ref('incremental')
const storeConfigImportForm = ref({})
const storeConfigUploadRef = ref()

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

const storeConfigQuery = ref({
  pageNum: 1,
  pageSize: 10,
  groupNo: '',
  venderNo: '',
  orgNo: '',
  sapOrgNo: '',
  keyword: ''
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
    cutLogEnabled: false,
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
    aiAgentCode: '',
    aiProviderCode: '',
    notifyConfig: createDefaultLogPullNotifyConfig()
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

function openStoreConfigDialog() {
  storeConfigOpen.value = true
  loadStoreConfigList()
}

function loadStoreConfigList() {
  storeConfigLoading.value = true
  return listTicketLogPullStoreConfigs(storeConfigQuery.value).then(response => {
    const pageData = response.data || response
    storeConfigList.value = Array.isArray(pageData)
      ? pageData
      : (Array.isArray(pageData?.rows) ? pageData.rows : [])
    storeConfigTotal.value = pageData?.total || 0
  }).finally(() => {
    storeConfigLoading.value = false
  })
}

function handleStoreConfigQuery() {
  storeConfigQuery.value.pageNum = 1
  loadStoreConfigList()
}

function resetStoreConfigQuery() {
  storeConfigQuery.value = {
    pageNum: 1,
    pageSize: 10,
    groupNo: '',
    venderNo: '',
    orgNo: '',
    sapOrgNo: '',
    keyword: ''
  }
  loadStoreConfigList()
}

function resetStoreConfigImportDialog() {
  storeConfigImportForm.value = {}
  storeConfigImportResult.value = null
  storeConfigImportMode.value = 'incremental'
  if (storeConfigUploadRef.value) {
    storeConfigUploadRef.value.clearFiles?.()
  }
}

function downloadStoreConfigTemplate() {
  downloadTicketLogPullStoreConfigTemplate().then(async blob => {
    if (!blobValidate(blob)) {
      try {
        const text = await blob.text()
        const payload = JSON.parse(text)
        proxy.$modal.msgError(payload.msg || '模板下载失败')
      } catch (error) {
        proxy.$modal.msgError('模板下载失败')
      }
      return
    }
    saveAs(blob, '门店配置导入模板.xlsx')
  }).catch(() => {
    proxy.$modal.msgError('模板下载失败')
  })
}

function handleStoreConfigUploadChange(uploadFile) {
  const rawFile = uploadFile?.raw
  if (!rawFile) {
    return
  }
  if (!rawFile.name?.toLowerCase().endsWith('.xlsx')) {
    proxy.$modal.msgWarning('仅支持 xlsx 文件')
    return
  }
  storeConfigImportForm.value = {
    file: rawFile
  }
  storeConfigImportOpen.value = true
}

function submitStoreConfigImport() {
  const rawFile = storeConfigImportForm.value?.file
  if (!rawFile) {
    proxy.$modal.msgWarning('请先选择 xlsx 文件')
    return
  }
  const formData = new FormData()
  formData.append('file', rawFile)
  formData.append('import_mode', storeConfigImportMode.value)
  storeConfigImporting.value = true
  importTicketLogPullStoreConfigs(formData).then(response => {
    storeConfigImportResult.value = response.data || null
    proxy.$modal.msgSuccess('门店配置导入完成')
    loadStoreConfigList()
  }).catch(() => {
    proxy.$modal.msgError('门店配置导入失败')
  }).finally(() => {
    storeConfigImporting.value = false
  })
}

function loadProviderOptions() {
  return listAiProviderOptions().then(response => {
    providerOptions.value = response.data || []
  })
}

function loadPushOptions() {
  return listAllPushConfig({ pageNum: 1, pageSize: 500 }).then(response => {
    const rows = response.data || []
    pushOptions.value = Array.isArray(rows) ? rows : []
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
        storeId: String(store.storeId || '').trim(),
        storeCode: String(store.storeCode || '').trim(),
        sapOrgNo: String(store.sapOrgNo || '').trim(),
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
  const code = String(store.storeCode || store.storeId || '').trim()
  const sapOrgNo = String(store.sapOrgNo || '').trim()
  return [name, code ? `[${code}]` : '', sapOrgNo ? `(${sapOrgNo})` : ''].filter(Boolean).join(' ')
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

function resetStoreSelection(target, vendorId) {
  const storeId = String(target.storeId || '').trim()
  if (!storeId) {
    target.storeId = undefined
    return
  }
  const storeOptions = getVendorStoreOptions(vendorId)
  if (storeOptions.length && !storeOptions.some(item => String(item.storeId || '').trim() === storeId)) {
    target.storeId = storeId
  }
}

function handleQueryVendorChange(vendorId) {
  resetStoreSelection(queryParams.value, vendorId)
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
  if (createForm.value.ticketId) {
    handleCreateTicketChange(createForm.value.ticketId)
  }
}

function pickFirstFilledValue(candidates = []) {
  for (const candidate of candidates) {
    if (candidate === null || candidate === undefined) {
      continue
    }
    if (typeof candidate === 'string' && !candidate.trim()) {
      continue
    }
    return candidate
  }
  return undefined
}

function resolveTicketSyncSource(detail) {
  const payload = detail || {}
  const extraData = payload.extraData || payload.extra_data || {}
  const externalSync = extraData.externalSync || extraData.external_sync || {}
  const source = externalSync.source || {}
  const logPullHints = extraData.logPullHints || extraData.log_pull_hints || {}
  const ticketAutomation = extraData.ticketAutomation || extraData.ticket_automation || {}
  const automationLogPullConfig = ticketAutomation.logPullConfig || ticketAutomation.log_pull_config || {}
  const latestLogPull = payload.latestLogPull || payload.latest_log_pull || {}
  const directLogPullConfig = payload.logPullConfig || payload.log_pull_config || {}
  return {
    vendorId: pickFirstFilledValue([
      source.vendorId,
      source.vendor_id,
      logPullHints.vendorId,
      logPullHints.vendor_id,
      latestLogPull.vendorId,
      latestLogPull.vendor_id,
      automationLogPullConfig.vendorId,
      automationLogPullConfig.vendor_id,
      directLogPullConfig.vendorId,
      directLogPullConfig.vendor_id
    ]),
    storeId: pickFirstFilledValue([
      source.storeId,
      source.store_id,
      logPullHints.storeId,
      logPullHints.store_id,
      latestLogPull.storeId,
      latestLogPull.store_id,
      automationLogPullConfig.storeId,
      automationLogPullConfig.store_id,
      directLogPullConfig.storeId,
      directLogPullConfig.store_id
    ]),
    posNo: pickFirstFilledValue([
      source.posNo,
      source.pos_no,
      source.posId,
      source.pos_id,
      source.scoNo,
      source.sco_no,
      logPullHints.posNo,
      logPullHints.pos_no,
      latestLogPull.posNo,
      latestLogPull.pos_no,
      automationLogPullConfig.posNo,
      automationLogPullConfig.pos_no,
      automationLogPullConfig.posId,
      automationLogPullConfig.pos_id,
      automationLogPullConfig.scoNo,
      automationLogPullConfig.sco_no,
      directLogPullConfig.posNo,
      directLogPullConfig.pos_no,
      directLogPullConfig.posId,
      directLogPullConfig.pos_id,
      directLogPullConfig.scoNo,
      directLogPullConfig.sco_no
    ])
  }
}

function applyTicketLogPullPrefill(ticketDetail) {
  const source = resolveTicketSyncSource(ticketDetail)
  const vendorId = Number(source.vendorId)
  if (Number.isFinite(vendorId) && vendorId > 0) {
    createForm.value.vendorId = vendorId
  }
  const storeId = String(source.storeId || '').trim()
  if (storeId) {
    createForm.value.storeId = storeId
  }
  const posNo = Number(source.posNo)
  if (Number.isFinite(posNo) && posNo > 0) {
    createForm.value.posNo = posNo
  }
}

function handleCreateTicketChange(ticketId) {
  if (!ticketId) {
    createForm.value.autoAiEnabled = false
    createForm.value.aiAgentCode = ''
    createForm.value.aiProviderCode = ''
    return
  }
  getTicket(ticketId).then(response => {
    applyTicketLogPullPrefill(response.data || {})
  }).catch(() => {})
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
    if (Number(createForm.value.commandDataType) === 2 && !createForm.value.path) {
      proxy.$modal.msgWarning('数据类型为数据库时，path 不能为空')
      return
    }
    if (Number(createForm.value.commandDataType) !== 2 && !createForm.value.modifyTime) {
      proxy.$modal.msgWarning('数据类型为日志时，modifyTime 不能为空')
      return
    }
    const timeRangeError = getOptionalLogPullTimeRangeError(createForm.value)
    if (timeRangeError) {
      proxy.$modal.msgWarning(timeRangeError)
      return
    }
    if (createForm.value.autoAiEnabled && !createForm.value.ticketId) {
      proxy.$modal.msgWarning('未关联工单时不能启用自动AI分析')
      return
    }
    if (
      createForm.value.autoAiEnabled
      && !String(createForm.value.aiAgentCode || '').trim()
      && !String(createForm.value.aiProviderCode || '').trim()
    ) {
      proxy.$modal.msgWarning('启用自动AI分析时必须选择Provider或Agent')
      return
    }

    submitting.value = true
    const payload = {
      ...createForm.value,
      ticketId: createForm.value.ticketId || null,
      notifyConfig: normalizeLogPullNotifyConfig(createForm.value.notifyConfig)
    }
    if (Number(payload.commandDataType) === 2) {
      delete payload.modifyTime
    } else {
      delete payload.path
    }
    delete payload.cutLogEnabled
    const timeRangePayload = buildOptionalLogPullTimeRangePayload(createForm.value)
    Object.assign(payload, timeRangePayload)
    if (!timeRangePayload.timeRangeMode) {
      delete payload.timeRangeMode
      delete payload.logBeginTime
      delete payload.logEndTime
      delete payload.logPointTime
      delete payload.rangeBeforeMinutes
      delete payload.rangeAfterMinutes
    } else if (timeRangePayload.timeRangeMode === 'between') {
      delete payload.logPointTime
      delete payload.rangeBeforeMinutes
      delete payload.rangeAfterMinutes
    } else {
      delete payload.logBeginTime
      delete payload.logEndTime
    }
    if (!payload.autoAiEnabled) {
      payload.aiAgentCode = ''
      payload.aiProviderCode = ''
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

function resolveDownloadFileName(row) {
  let remoteName = ''
  if (row?.commandResultUrl) {
    try {
      remoteName = new URL(String(row.commandResultUrl)).pathname.split('/').pop() || ''
    } catch (error) {
      remoteName = String(row.commandResultUrl).split('/').pop() || ''
    }
  }
  const candidates = [
    row?.downloadFileName,
    row?.storagePath ? String(row.storagePath).split(/[\\/]/).pop() : '',
    remoteName,
    `ticket_log_pull_${row?.id || Date.now()}.zip`
  ]
  for (const candidate of candidates) {
    const text = String(candidate || '').trim()
    if (text) {
      return text
    }
  }
  return `ticket_log_pull_${row?.id || Date.now()}.zip`
}

async function downloadLogPull(row) {
  if (!row?.id) {
    return
  }
  if (!row.commandResultUrl && !row.storagePath) {
    proxy.$modal.msgWarning('当前记录缺少可下载的归档文件')
    return
  }
  try {
    actionLoading.value = true
    const blob = await downloadTicketLogPull(row.id, 'auto')
    if (!blobValidate(blob)) {
      try {
        const text = await blob.text()
        const payload = JSON.parse(text)
        proxy.$modal.msgError(payload.msg || '下载失败')
      } catch (error) {
        proxy.$modal.msgError('下载失败')
      }
      return
    }
    saveAs(blob, resolveDownloadFileName(row))
  } catch (error) {
    console.error(error)
    proxy.$modal.msgError('下载失败')
  } finally {
    actionLoading.value = false
  }
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

function deleteLogPull(row) {
  if (!row?.id) {
    return
  }
  proxy.$modal.confirm(`是否确认删除日志拉取记录 #${row.id}？删除后会同步清理关联文件数据。`).then(() => {
    actionLoading.value = true
    return delTicketLogPull(row.id)
  }).then(() => {
    proxy.$modal.msgSuccess('日志拉取记录已删除')
    if (selectedRecord.value?.id === row.id) {
      contentOpen.value = false
      selectedRecord.value = null
      contentDetail.value = null
      contentText.value = ''
    }
    return getList()
  }).catch(() => {}).finally(() => {
    actionLoading.value = false
  })
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
  loadProviderOptions()
  loadVendorOptions()
  loadPushOptions()
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
