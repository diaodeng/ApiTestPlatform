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
      <el-form-item label="类型" prop="providerType">
        <el-select v-model="queryParams.providerType" placeholder="全部类型" clearable style="width: 180px">
          <el-option
            v-for="item in providerTypeOptions"
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
      <el-table-column label="类型" align="center" prop="providerType" width="140">
        <template #default="scope">{{ formatProviderType(scope.row.providerType) }}</template>
      </el-table-column>
      <el-table-column label="模型" align="center" prop="modelName" min-width="160" :show-overflow-tooltip="true" />
      <el-table-column label="Agent" align="center" prop="agentCode" min-width="140" :show-overflow-tooltip="true" />
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

    <el-dialog :title="dialogTitle" v-model="formOpen" width="820px" append-to-body @closed="resetForm">
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
            <el-form-item label="Provider类型" prop="providerType">
              <el-select v-model="form.providerType" placeholder="请选择类型" style="width: 100%">
                <el-option
                  v-for="item in providerTypeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="默认模型" prop="modelName">
              <el-input v-model="form.modelName" placeholder="例如 gpt-4.1" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="绑定Agent" prop="agentCode">
              <el-input v-model="form.agentCode" placeholder="可选，留空则使用系统默认Agent" />
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
        <el-descriptions-item label="类型">{{ formatProviderType(detailData.providerType) }}</el-descriptions-item>
        <el-descriptions-item label="默认模型">{{ detailData.modelName || '-' }}</el-descriptions-item>
        <el-descriptions-item label="绑定Agent">{{ detailData.agentCode || '-' }}</el-descriptions-item>
        <el-descriptions-item label="等级">{{ detailData.providerLevel ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="Base URL">{{ detailData.baseUrl || '-' }}</el-descriptions-item>
        <el-descriptions-item label="密钥前缀">{{ detailData.apiKeyPrefix || '-' }}</el-descriptions-item>
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
          <el-button @click="detailOpen = false">关 闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="AiProvider">
import { addAiProvider, delAiProvider, getAiProvider, listAiProvider, updateAiProvider } from '@/api/system/aiprovider'

const { proxy } = getCurrentInstance()

const providerTypeOptions = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'LLM', value: 'llm' },
  { label: 'Azure OpenAI', value: 'azure_openai' },
  { label: 'Ollama', value: 'ollama' },
  { label: '自定义', value: 'custom' }
]

const providerList = ref([])
const loading = ref(false)
const showSearch = ref(true)
const total = ref(0)
const formOpen = ref(false)
const detailOpen = ref(false)
const dialogTitle = ref('')
const detailData = ref({})

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyword: undefined,
    providerType: undefined,
    enabled: undefined
  },
  form: {},
  rules: {
    providerCode: [{ required: true, message: 'Provider编码不能为空', trigger: 'blur' }],
    providerName: [{ required: true, message: 'Provider名称不能为空', trigger: 'blur' }],
    providerType: [{ required: true, message: 'Provider类型不能为空', trigger: 'change' }],
    modelName: [{ required: true, message: '默认模型不能为空', trigger: 'blur' }]
  }
})

const { queryParams, form, rules } = toRefs(data)

function formatProviderType(providerType) {
  const item = providerTypeOptions.find(row => row.value === providerType)
  return item ? item.label : providerType || '-'
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
    providerType: 'openai',
    modelName: '',
    agentCode: '',
    providerLevel: 0,
    baseUrl: '',
    apiKey: '',
    enabled: true,
    remark: ''
  }
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
    dialogTitle.value = '编辑 AI Provider'
    formOpen.value = true
  })
}

function submitForm() {
  proxy.$refs.providerRef.validate(valid => {
    if (!valid) return
    const payload = {
      ...form.value,
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

function handleViewDetail(row) {
  getAiProvider(row.providerId).then(response => {
    detailData.value = response.data || {}
    detailOpen.value = true
  })
}

function handleDelete(row) {
  proxy.$modal.confirm(`是否确认删除 AI Provider "${row.providerName || row.providerCode}"？`).then(() => delAiProvider(row.providerId)).then(() => {
    proxy.$modal.msgSuccess('删除成功')
    getList()
  }).catch(() => {})
}

getList()
</script>
