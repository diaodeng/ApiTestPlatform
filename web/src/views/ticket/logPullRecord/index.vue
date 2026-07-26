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
      <el-form-item label="环境" prop="environment">
        <el-select v-model="queryParams.environment" placeholder="全部环境" clearable style="width: 160px">
          <el-option v-for="item in environmentOptions" :key="item" :label="item" :value="item" />
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
          allow-create
          default-first-option
          style="width: 220px"
          @change="handleQueryVendorChange"
        >
          <el-option
            v-for="item in vendorOptions"
            :key="item.venderNo"
            :label="item.label"
            :value="item.venderNo"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="门店" prop="storeId">
        <el-select
          v-model="queryParams.storeId"
          placeholder="先选择商家"
          clearable
          filterable
          allow-create
          default-first-option
          :disabled="!queryParams.vendorId"
          :loading="queryStoreLoading"
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

    <el-table
      v-loading="loading"
      :data="recordList"
      row-key="id"
      class="log-pull-record-table"
      scrollbar-always-on
    >
      <el-table-column label="记录ID" prop="id" width="180" show-overflow-tooltip />
      <el-table-column label="环境" width="100" align="center">
        <template #default="scope">{{ scope.row.environment || '-' }}</template>
      </el-table-column>
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
      <el-table-column label="拉取参数" min-width="180" show-overflow-tooltip>
        <template #default="scope">{{ formatLogPullParameter(scope.row) }}</template>
      </el-table-column>
      <el-table-column label="归档地址" min-width="220" show-overflow-tooltip>
        <template #default="scope">
          <el-link
            v-if="getLogPullArchiveDownloadUrl(scope.row)"
            type="primary"
            :href="getLogPullArchiveDownloadUrl(scope.row)"
            target="_blank"
            @click.prevent="downloadLogPullArchive(scope.row)"
            @contextmenu.prevent="copyLogPullArchiveDownloadUrl(scope.row)"
          >
            {{ getLogPullArchiveDisplayText(scope.row) }}
          </el-link>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="原始压缩包" min-width="220" show-overflow-tooltip>
        <template #default="scope">
          <el-link
            v-if="getLogPullOriginalDownloadUrl(scope.row)"
            type="primary"
            :href="getLogPullOriginalDownloadUrl(scope.row)"
            target="_blank"
            @click.prevent="downloadLogPullOriginal(scope.row)"
            @contextmenu.prevent="copyLogPullOriginalDownloadUrl(scope.row)"
          >
            {{ getLogPullOriginalDownloadUrl(scope.row) }}
          </el-link>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="摘要/异常" min-width="240" prop="contentSummary" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.errorMessage || scope.row.contentSummary || '-' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="340">
        <template #default="scope">
          <el-tooltip
            v-if="getContentDownloadProgress(scope.row)"
            :content="getContentDownloadProgress(scope.row).message"
            placement="top"
          >
            <el-progress
              class="log-view-download-progress"
              type="circle"
              :percentage="getContentDownloadProgress(scope.row).percentage"
              :width="26"
              :stroke-width="3"
            />
          </el-tooltip>
          <el-button v-else link type="primary" icon="View" @click="openLogViewer(scope.row)" v-hasPermi="['ticket:logpull:query']">
            查看日志
          </el-button>
          <el-button link type="primary" icon="CopyDocument" @click="handleCopyLogPull(scope.row)" :disabled="actionLoading || activeLogPullStatuses.includes(scope.row.status)" v-hasPermi="['ticket:logpull:add']">
            复制
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
            :environment-options="environmentOptions"
            :parameter-examples="parameterExamples"
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

    <LogViewerDialog v-model="viewerVisible" :record="viewerRecord" />

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
  getTicketLogPullVendorStoreOptions,
  listTicket,
  listTicketLogPullStoreConfigs,
  listTicketLogPullRecords,
  importTicketLogPullStoreConfigs,
  redownloadTicketLogPull,
  retryTicketLogPull
} from '@/api/ticket/ticket'
import { all as listAllAgents } from '@/api/hrm/agent'
import { allPushConfig as listAllPushConfig } from '@/api/hrm/push'
import { listAiProviderOptions } from '@/api/system/aiprovider'
import { saveAs } from 'file-saver'
import LogPullConfigFields from '@/components/ticket/LogPullConfigFields.vue'
import LogPullNotifyConfigFields from '@/components/ticket/LogPullNotifyConfigFields.vue'
import LogViewerDialog from '@/components/ticket/LogViewerDialog.vue'
import { getLogPullStatusTagType, getOptionLabel, logPullDataTypeOptions, logPullStatusOptions, logPullStorageModeOptions } from '../constants'
import {
  applyLogPullRecordToForm,
  buildOptionalLogPullTimeRangePayload,
  createDefaultLogPullNotifyConfig,
  formatLogPullParameter,
  getOptionalLogPullTimeRangeError,
  normalizeLogPullNotifyConfig,
  resolveLogPullArchiveLink,
  resolveLogPullOriginalLink,
  isHttpDownloadUrl
} from '../logPull.shared'
import { useLogPrepareProgress } from '../hooks/useLogPrepareProgress'
import { blobValidate } from '@/utils/ruoyi'

const { proxy } = getCurrentInstance()
const { prepareWithDownloadProgress, getDownloadProgress } = useLogPrepareProgress()

const loading = ref(false)
const submitting = ref(false)
const actionLoading = ref(false)
const createOpen = ref(false)
const viewerVisible = ref(false)
const viewerRecord = ref(null)
const showSearch = ref(true)
const recordList = ref([])
const total = ref(0)
const ticketLoading = ref(false)
const ticketOptions = ref([])
const agentOptions = ref([])
const providerOptions = ref([])
const vendorOptions = ref([])
const queryStoreOptions = ref([])
const queryStoreLoading = ref(false)
const parameterExamples = ref([])
const environmentOptions = ref([])
const pushOptions = ref([])
const selectedRecord = ref(null)
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
  environment: '',
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

const createRules = {
  vendorId: [{ required: true, message: 'vendorId 不能为空', trigger: 'change' }],
  storeId: [{ required: true, message: 'storeId 不能为空', trigger: 'change' }],
  posNo: [{ required: true, message: 'posNo 不能为空', trigger: 'blur' }]
}

function createDefaultForm() {
  return {
    ticketId: undefined,
    environment: '',
    vendorId: undefined,
    storeId: undefined,
    posNo: undefined,
    commandDataType: 1,
    pullMethod: 'time',
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

function openLogViewer(row) {
  viewerRecord.value = row
  viewerVisible.value = true
}

function getList() {
  loading.value = true
  listTicketLogPullRecords(queryParams.value).then(response => {
    recordList.value = response.rows || []
    total.value = response.total || 0
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
    environment: '',
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
    venderNo: String(item.venderNo || '').trim(),
    vendorName: String(item.vendorName || '').trim(),
    label: buildVendorOptionLabel(item),
  })).filter(item => item.venderNo && item.vendorName)
}

function buildVendorOptionLabel(vendor) {
  const venderNo = String(vendor.venderNo || '').trim()
  const name = String(vendor.vendorName || '').trim()
  return [venderNo, name].filter(Boolean).join(' - ')
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
    environmentOptions.value = Array.isArray(response.data?.environments)
      ? response.data.environments
      : []
    parameterExamples.value = Array.isArray(response.data?.parameterExamples)
      ? response.data.parameterExamples
      : []
  })
}

function loadQueryStoreOptions(venderNo) {
  const resolvedVenderNo = String(venderNo || '').trim()
  queryStoreOptions.value = []
  if (!resolvedVenderNo) {
    return Promise.resolve()
  }
  queryStoreLoading.value = true
  return getTicketLogPullVendorStoreOptions(resolvedVenderNo).then(response => {
    const rows = Array.isArray(response.data?.stores) ? response.data.stores : []
    queryStoreOptions.value = rows.map(store => ({
      storeId: String(store.storeId || '').trim(),
      storeCode: String(store.storeCode || '').trim(),
      sapOrgNo: String(store.sapOrgNo || '').trim(),
      storeName: String(store.storeName || store.storeId || '').trim(),
      label: buildStoreOptionLabel(store)
    })).filter(store => store.storeId)
  }).finally(() => {
    queryStoreLoading.value = false
  })
}

function handleQueryVendorChange(venderNo) {
  queryParams.value.storeId = undefined
  loadQueryStoreOptions(venderNo)
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
    ]),
    modifyTime: pickFirstFilledValue([
      logPullHints.modifyTime,
      logPullHints.modify_time,
      logPullHints.logDate,
      logPullHints.log_date,
      source.modifyTime,
      source.modify_time,
      source.logDate,
      source.log_date,
      automationLogPullConfig.modifyTime,
      automationLogPullConfig.modify_time,
      directLogPullConfig.modifyTime,
      directLogPullConfig.modify_time
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
  const modifyTime = String(source.modifyTime || '').trim()
  if (modifyTime) {
    createForm.value.modifyTime = modifyTime.slice(0, 10)
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
    if (createForm.value.pullMethod === 'path' && !createForm.value.path) {
      proxy.$modal.msgWarning('拉取方式为路径时，path 不能为空')
      return
    }
    if (createForm.value.pullMethod !== 'path' && !createForm.value.modifyTime) {
      proxy.$modal.msgWarning('拉取方式为时间时，modifyTime 不能为空')
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
    if (payload.pullMethod === 'path') {
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

/**
 * 获取管理列表行当前可展示的日志远程下载进度。
 * @param {object} row 日志拉取记录行数据。
 * @returns {object|null} 正在下载时返回进度信息，否则返回 null。
 */
function getContentDownloadProgress(row) {
  return getDownloadProgress(row?.ticketId || row?.ticket_id, row?.id)
}

function handleCopyLogPull(row) {
  if (!row) return
  if (activeLogPullStatuses.includes(row.status)) {
    proxy.$modal.msgWarning('当前日志拉取任务仍在执行中，不能复制')
    return
  }
  createForm.value = createDefaultForm()
  createForm.value.ticketId = row.ticketId || undefined
  applyLogPullRecordToForm(createForm.value, row)
  createOpen.value = true
}

function runAction(request, successMessage) {
  if (actionLoading.value) {
    return
  }
  actionLoading.value = true
  request.then(() => {
    proxy.$modal.msgSuccess(successMessage)
    handleQuery()
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

function openBrowserDownload(url) {
  const targetUrl = String(url || '').trim()
  if (!targetUrl) {
    return false
  }
  window.open(targetUrl, '_blank', 'noopener')
  return true
}

function getLogPullArchiveDownloadUrl(row) {
  return resolveLogPullArchiveLink(row, 'service').url
}

function getLogPullArchiveDisplayText(row) {
  const link = resolveLogPullArchiveLink(row, 'service')
  return link.text || link.url
}

function getLogPullOriginalDownloadUrl(row) {
  return resolveLogPullOriginalLink(row).url
}

/**
 * 复制文本到系统剪贴板，优先使用 Clipboard API，不支持时回退到临时输入框。
 * @param {string} text 需要复制的文本
 * @returns {Promise<boolean>} 是否复制成功
 */
async function copyTextToClipboard(text) {
  const copyText = String(text || '').trim()
  if (!copyText) {
    return false
  }
  if (navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(copyText)
    return true
  }
  const textarea = document.createElement('textarea')
  textarea.value = copyText
  textarea.setAttribute('readonly', 'readonly')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  document.body.removeChild(textarea)
  return copied
}

async function copyResolvedLogPullUrl(link, emptyMessage) {
  if (!link?.url) {
    proxy.$modal.msgWarning(emptyMessage)
    return
  }
  try {
    const copied = await copyTextToClipboard(link.url)
    if (!copied) {
      proxy.$modal.msgError('复制失败，请手动复制链接')
      return
    }
    proxy.$modal.msgSuccess(link.needLogin ? '下载链接已复制，访问时需要当前系统登录态' : '下载链接已复制')
  } catch (error) {
    console.error(error)
    proxy.$modal.msgError('复制失败，请手动复制链接')
  }
}

function copyLogPullArchiveDownloadUrl(row) {
  return copyResolvedLogPullUrl(resolveLogPullArchiveLink(row, 'service'), '当前记录缺少本服务归档地址')
}

function copyLogPullOriginalDownloadUrl(row) {
  return copyResolvedLogPullUrl(resolveLogPullOriginalLink(row), '当前记录缺少原始压缩包地址')
}

function downloadLogPullArchive(row) {
  if (!row?.storagePath) {
    proxy.$modal.msgWarning('当前记录缺少本服务归档地址')
    return
  }
  if (isHttpDownloadUrl(row.storagePath)) {
    openBrowserDownload(row.storagePath)
    return
  }
  downloadLogPull(row)
}

function downloadLogPullOriginal(row) {
  if (!row?.commandResultUrl) {
    proxy.$modal.msgWarning('当前记录缺少原始压缩包地址')
    return
  }
  openBrowserDownload(row.commandResultUrl)
}

async function downloadLogPull(row) {
  if (!row?.id) {
    return
  }
  if (!row.commandResultUrl && !row.storagePath) {
    proxy.$modal.msgWarning('当前记录缺少可下载的归档文件')
    return
  }
  if (!row.storagePath && row.commandResultUrl) {
    openBrowserDownload(row.commandResultUrl)
    return
  }
  if (isHttpDownloadUrl(row.storagePath)) {
    openBrowserDownload(row.storagePath)
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
  runAction(redownloadTicketLogPull(row.id), '日志压缩包已重新下载')
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
      viewerVisible.value = false
      selectedRecord.value = null
    }
    return getList()
  }).catch(() => {}).finally(() => {
    actionLoading.value = false
  })
}

onMounted(() => {
  loadTicketOptions()
  loadAgentOptions()
  loadProviderOptions()
  loadVendorOptions()
  loadPushOptions()
  getList()
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

.log-view-download-progress {
  display: inline-flex;
  width: 26px;
  height: 26px;
  margin: 0 7px;
  pointer-events: none;
  vertical-align: middle;
}

.log-view-download-progress :deep(.el-progress__text) {
  font-size: 8px !important;
}

.log-pull-record-table :deep(.el-scrollbar__bar.is-horizontal) {
  height: 12px;
}

.log-pull-record-table :deep(.el-scrollbar__bar.is-horizontal .el-scrollbar__thumb) {
  min-width: 48px;
}
</style>
