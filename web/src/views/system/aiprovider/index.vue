<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="90px">
      <el-form-item label="关键字" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="编码/名称/模型/Agent"
          clearable
          style="width: 260px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="平台" prop="platformCode">
        <el-select v-model="queryParams.platformCode" placeholder="全部平台" clearable style="width: 180px">
          <el-option
            v-for="item in platformOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="状态" prop="enabled">
        <el-select v-model="queryParams.enabled" placeholder="全部状态" clearable style="width: 160px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['system:aiprovider:add']">
          新增
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
    </el-row>

    <el-table v-loading="loading" :data="providerList">
      <el-table-column label="ID" align="center" prop="providerId" width="90" />
      <el-table-column label="编码" align="center" prop="providerCode" min-width="150" :show-overflow-tooltip="true" />
      <el-table-column label="名称" align="center" prop="providerName" min-width="170" :show-overflow-tooltip="true" />
      <el-table-column label="平台" align="center" prop="platformCode" width="150">
        <template #default="scope">{{ formatPlatform(scope.row.platformCode) }}</template>
      </el-table-column>
      <el-table-column label="协议" align="center" prop="apiProtocol" min-width="180" :show-overflow-tooltip="true" />
      <el-table-column label="模型" align="center" prop="defaultModel" min-width="160" :show-overflow-tooltip="true" />
      <el-table-column label="首选Agent" align="center" prop="preferredAgentCode" min-width="140" :show-overflow-tooltip="true" />
      <el-table-column label="等级" align="center" prop="providerLevel" width="90" />
      <el-table-column label="Base URL" align="center" prop="baseUrl" min-width="220" :show-overflow-tooltip="true" />
      <el-table-column label="密钥" align="center" prop="apiKeyPrefix" min-width="180" :show-overflow-tooltip="true" />
      <el-table-column label="状态" align="center" width="100">
        <template #default="scope">
          <el-tag v-if="scope.row.enabled" type="success">启用</el-tag>
          <el-tag v-else type="info">停用</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" min-width="180">
        <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="备注" align="center" prop="remark" min-width="180" :show-overflow-tooltip="true" />
      <el-table-column label="操作" align="center" width="200" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="handleViewDetail(scope.row)" v-hasPermi="['system:aiprovider:query']">
            详情
          </el-button>
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['system:aiprovider:edit']">
            编辑
          </el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['system:aiprovider:remove']">
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

    <el-dialog :title="dialogTitle" v-model="formOpen" width="920px" append-to-body @closed="resetForm">
      <el-form ref="providerRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="Provider编码" prop="providerCode">
              <el-input v-model="form.providerCode" placeholder="例如 openai_main" :disabled="Boolean(form.providerId)" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Provider名称" prop="providerName">
              <el-input v-model="form.providerName" placeholder="例如 OpenAI主账号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属平台" prop="platformCode">
              <el-select v-model="form.platformCode" placeholder="请选择平台" style="width: 100%">
                <el-option
                  v-for="item in platformOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="API协议" prop="apiProtocol">
              <el-select v-model="form.apiProtocol" placeholder="请选择调用协议" style="width: 100%">
                <el-option v-for="item in protocolOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="默认模型" prop="defaultModel">
              <el-select v-model="form.defaultModel" filterable allow-create default-first-option placeholder="可手动输入或从目录选择" style="width: calc(100% - 96px)">
                <el-option v-for="item in modelOptions" :key="item.modelId" :label="item.displayName || item.modelId" :value="item.modelId" />
              </el-select>
              <el-button class="ml8" :loading="modelLoading" @click="refreshModelCatalog">更新模型</el-button>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="首选Agent" prop="preferredAgentCode">
              <el-input v-model="form.preferredAgentCode" placeholder="分析任务可选，留空使用系统默认Agent" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="等级" prop="providerLevel">
              <el-input-number v-model="form.providerLevel" :min="0" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="Base URL" prop="baseUrl">
              <el-input v-model="form.baseUrl" placeholder="例如 https://api.openai.com/v1" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="支持用途" prop="supportedUsages">
              <el-select v-model="form.supportedUsages" multiple placeholder="请选择用途" style="width: 100%">
                <el-option v-for="item in usageOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="兼容执行器" prop="supportedExecutors">
              <el-select v-model="form.supportedExecutors" multiple placeholder="请选择执行器" style="width: 100%">
                <el-option v-for="item in executorOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="协议配置" prop="connectionConfig">
              <el-input v-model="connectionConfigText" type="textarea" :rows="3" placeholder='JSON，例如 Azure: {"deployment":"xxx","apiVersion":"2024-10-21"}' />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="Worker环境" prop="workerEnv">
              <el-input v-model="workerEnvText" type="textarea" :rows="3" placeholder="JSON，仅工单AI分析 Worker 的环境变量覆盖项" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="Provider密钥" prop="apiKey">
              <el-input
                v-model="form.apiKey"
                type="password"
                show-password
                :placeholder="form.providerId ? '留空则保持当前密钥' : '请输入 Provider 密钥'"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用状态" prop="enabled">
              <el-switch v-model="form.enabled" inline-prompt active-text="启用" inactive-text="停用" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注" prop="remark">
              <el-input v-model="form.remark" type="textarea" :rows="4" placeholder="请输入备注" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="submitForm">确 定</el-button>
          <el-button @click="formOpen = false">取 消</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog title="AI Provider 详情" v-model="detailOpen" width="900px" append-to-body>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="ID">{{ detailData.providerId || '-' }}</el-descriptions-item>
        <el-descriptions-item label="编码">{{ detailData.providerCode || '-' }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ detailData.providerName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="平台">{{ formatPlatform(detailData.platformCode) }}</el-descriptions-item>
          <el-descriptions-item label="协议">{{ detailData.apiProtocol || '-' }}</el-descriptions-item>
          <el-descriptions-item label="默认模型">{{ detailData.defaultModel || '-' }}</el-descriptions-item>
          <el-descriptions-item label="首选Agent">{{ detailData.preferredAgentCode || '-' }}</el-descriptions-item>
        <el-descriptions-item label="等级">{{ detailData.providerLevel ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="Base URL">{{ detailData.baseUrl || '-' }}</el-descriptions-item>
        <el-descriptions-item label="密钥前缀">{{ detailData.apiKeyPrefix || '-' }}</el-descriptions-item>
          <el-descriptions-item label="支持用途">{{ formatOptionNames(detailData.supportedUsages, usageOptions) }}</el-descriptions-item>
          <el-descriptions-item label="兼容执行器">{{ formatOptionNames(detailData.supportedExecutors, executorOptions) }}</el-descriptions-item>
          <el-descriptions-item label="密钥状态">
          <el-tag v-if="detailData.hasSecret" type="success">已配置</el-tag>
          <el-tag v-else type="info">未配置</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag v-if="detailData.enabled" type="success">启用</el-tag>
          <el-tag v-else type="info">停用</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detailData.createTime ? parseTime(detailData.createTime) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ detailData.updateTime ? parseTime(detailData.updateTime) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ detailData.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <div class="dialog-footer">
          <el-button v-if="detailData.hasSecret" type="warning" @click="handleViewSecret(detailData)" v-hasPermi="['system:aiprovider:view-secret']">查看密钥</el-button>
          <el-button @click="detailOpen = false">关 闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="AiProvider">
import {
  addAiProvider,
  delAiProvider,
  getAiProvider,
  getAiProviderMetadataOptions,
  listAiProvider,
  listAiProviderModelCatalog,
  previewAiProviderModelCatalog,
  refreshAiProviderModelCatalog,
  updateAiProvider,
  viewAiProviderSecret
} from '@/api/system/aiprovider'

const { proxy } = getCurrentInstance()

const providerList = ref([])
const loading = ref(false)
const showSearch = ref(true)
const total = ref(0)
const formOpen = ref(false)
const detailOpen = ref(false)
const dialogTitle = ref('')
const detailData = ref({})
const platformOptions = ref([])
const protocolOptions = ref([])
const usageOptions = ref([])
const executorOptions = ref([])
const modelOptions = ref([])
const modelLoading = ref(false)
const connectionConfigText = ref('')
const workerEnvText = ref('')

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyword: undefined,
    platformCode: undefined,
    enabled: undefined
  },
  form: {},
  rules: {
    providerCode: [{ required: true, message: 'Provider编码不能为空', trigger: 'blur' }],
    providerName: [{ required: true, message: 'Provider名称不能为空', trigger: 'blur' }],
    platformCode: [{ required: true, message: '所属平台不能为空', trigger: 'change' }],
    apiProtocol: [{ required: true, message: 'API协议不能为空', trigger: 'change' }],
    defaultModel: [{ required: true, message: '默认模型不能为空', trigger: 'change' }],
    supportedUsages: [{ required: true, type: 'array', min: 1, message: '至少选择一个用途', trigger: 'change' }],
    supportedExecutors: [{ required: true, type: 'array', min: 1, message: '至少选择一个执行器', trigger: 'change' }]
  }
})

const { queryParams, form, rules } = toRefs(data)

function formatPlatform(platformCode) {
  const item = platformOptions.value.find(row => row.value === platformCode)
  return item ? item.label : platformCode || '-'
}

function formatOptionNames(values, options) {
  const selected = Array.isArray(values) ? values : []
  const optionRows = Array.isArray(options) ? options : options.value
  return selected.map(value => optionRows.find(item => item.value === value)?.label || value).join('、') || '-'
}

function parseJsonConfig(text, label) {
  const rawText = String(text || '').trim()
  if (!rawText) return undefined
  try {
    const result = JSON.parse(rawText)
    if (!result || Array.isArray(result) || typeof result !== 'object') throw new Error()
    return result
  } catch {
    proxy.$modal.msgWarning(`${label}必须是JSON对象`)
    return null
  }
}

function applyModelOptions(rows) {
  modelOptions.value = Array.isArray(rows) ? rows : []
}

function loadMetadataOptions() {
  return getAiProviderMetadataOptions().then(response => {
    const data = response.data || {}
    platformOptions.value = data.platforms || []
    protocolOptions.value = data.protocols || []
    usageOptions.value = data.usages || []
    executorOptions.value = data.executors || []
  })
}

function getList() {
  loading.value = true
  listAiProvider(queryParams.value)
    .then(response => {
      providerList.value = response.rows || []
      total.value = response.total || 0
    })
    .finally(() => {
      loading.value = false
    })
}

function resetForm() {
  form.value = {
    providerId: undefined,
    providerCode: '',
    providerName: '',
    platformCode: 'openai_compatible',
    apiProtocol: 'openai_chat_completions',
    supportedUsages: ['ticket_light_text', 'provider_model_discovery'],
    supportedExecutors: ['direct_http'],
    defaultModel: '',
    preferredAgentCode: '',
    providerLevel: 0,
    baseUrl: '',
    apiKey: '',
    enabled: true,
    remark: ''
  }
  modelOptions.value = []
  connectionConfigText.value = ''
  workerEnvText.value = ''
  proxy.resetForm('providerRef')
}

function handleQuery() {
  queryParams.value.pageNum = 1
  getList()
}

function resetQuery() {
  proxy.resetForm('queryRef')
  handleQuery()
}

function handleAdd() {
  resetForm()
  dialogTitle.value = '新增 AI Provider'
  formOpen.value = true
}

function handleUpdate(row) {
  resetForm()
  getAiProvider(row.providerId).then(response => {
    form.value = {
      ...form.value,
      ...(response.data || {}),
      apiKey: ''
    }
    connectionConfigText.value = form.value.connectionConfig ? JSON.stringify(form.value.connectionConfig, null, 2) : ''
    workerEnvText.value = form.value.workerEnv ? JSON.stringify(form.value.workerEnv, null, 2) : ''
    listAiProviderModelCatalog(row.providerId).then(catalogResponse => applyModelOptions(catalogResponse.data))
    dialogTitle.value = '编辑 AI Provider'
    formOpen.value = true
  })
}

function submitForm() {
  proxy.$refs.providerRef.validate(valid => {
    if (!valid) return
    const connectionConfig = parseJsonConfig(connectionConfigText.value, '协议配置')
    const workerEnv = parseJsonConfig(workerEnvText.value, 'Worker环境')
    if (connectionConfig === null || workerEnv === null) return
    const payload = {
      ...form.value,
      connectionConfig,
      workerEnv,
      providerLevel: Number(form.value.providerLevel || 0)
    }
    if (!payload.providerId && !String(payload.apiKey || '').trim()) {
      proxy.$modal.msgWarning('新增 Provider 时请填写密钥')
      return
    }
    if (!payload.providerId && !String(payload.providerCode || '').trim()) {
      proxy.$modal.msgWarning('Provider编码不能为空')
      return
    }
    const request = payload.providerId ? updateAiProvider(payload) : addAiProvider(payload)
    request.then(() => {
      proxy.$modal.msgSuccess(payload.providerId ? '修改成功' : '新增成功')
      formOpen.value = false
      getList()
    })
  })
}

function refreshModelCatalog() {
  const connectionConfig = parseJsonConfig(connectionConfigText.value, '协议配置')
  if (connectionConfig === null) return
  if (!form.value.platformCode || !form.value.apiProtocol || !form.value.baseUrl) {
    proxy.$modal.msgWarning('请先填写平台、API协议和Base URL')
    return
  }
  modelLoading.value = true
  const request = form.value.providerId && !String(form.value.apiKey || '').trim()
    ? refreshAiProviderModelCatalog(form.value.providerId)
    : previewAiProviderModelCatalog({ ...form.value, connectionConfig, apiKey: form.value.apiKey })
  request.then(response => {
    applyModelOptions(response.data)
    proxy.$modal.msgSuccess(`已获取 ${modelOptions.value.length} 个模型`)
  }).finally(() => {
    modelLoading.value = false
  })
}

function handleViewDetail(row) {
  getAiProvider(row.providerId).then(response => {
    detailData.value = response.data || {}
    detailOpen.value = true
  })
}

function handleViewSecret(row) {
  proxy.$prompt('请输入当前登录密码以查看Provider密钥', '二次验证', {
    inputType: 'password',
    inputPattern: /\S+/,
    inputErrorMessage: '密码不能为空',
    confirmButtonText: '验证并查看',
    cancelButtonText: '取消'
  }).then(({ value }) => viewAiProviderSecret(row.providerId, { password: value })).then(response => {
    proxy.$alert(response.data?.apiKey || '', 'Provider密钥', { confirmButtonText: '关闭' })
  }).catch(() => {})
}

function handleDelete(row) {
  proxy.$modal.confirm(`是否确认删除 AI Provider "${row.providerName || row.providerCode}"？`).then(() => delAiProvider(row.providerId)).then(() => {
    proxy.$modal.msgSuccess('删除成功')
    getList()
  }).catch(() => {})
}

loadMetadataOptions().then(getList)
</script>
