<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="90px">
      <el-form-item label="关键字" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="编码/名称/分类/Provider"
          clearable
          style="width: 260px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="分类" prop="templateCategory">
        <el-select v-model="queryParams.templateCategory" placeholder="全部分类" clearable style="width: 180px">
          <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
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
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['system:aiprompt:add']">
          新增
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
    </el-row>

    <el-table v-loading="loading" :data="templateList">
      <el-table-column label="ID" align="center" prop="templateId" width="90" />
      <el-table-column label="编码" align="center" prop="templateCode" min-width="170" :show-overflow-tooltip="true" />
      <el-table-column label="名称" align="center" prop="templateName" min-width="170" :show-overflow-tooltip="true" />
      <el-table-column label="分类" align="center" prop="templateCategory" width="140">
        <template #default="scope">{{ formatCategory(scope.row.templateCategory) }}</template>
      </el-table-column>
      <el-table-column label="Provider" align="center" prop="providerCode" min-width="140" :show-overflow-tooltip="true" />
      <el-table-column label="模型" align="center" prop="modelName" min-width="140" :show-overflow-tooltip="true" />
      <el-table-column label="排序" align="center" prop="sort" width="90" />
      <el-table-column label="状态" align="center" width="100">
        <template #default="scope">
          <el-tag v-if="scope.row.enabled" type="success">启用</el-tag>
          <el-tag v-else type="info">停用</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="提示词内容" align="left" prop="promptContent" min-width="320" show-overflow-tooltip />
      <el-table-column label="创建时间" align="center" prop="createTime" min-width="180">
        <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="备注" align="center" prop="remark" min-width="180" :show-overflow-tooltip="true" />
      <el-table-column label="操作" align="center" width="160" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['system:aiprompt:edit']">
            编辑
          </el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['system:aiprompt:remove']">
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

    <el-dialog :title="dialogTitle" v-model="formOpen" width="860px" append-to-body @closed="resetForm">
      <el-form ref="templateRef" :model="form" :rules="rules" label-width="120px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="模板编码" prop="templateCode">
              <el-input v-model="form.templateCode" placeholder="例如 ticket_translate_default" :disabled="Boolean(form.templateId)" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模板名称" prop="templateName">
              <el-input v-model="form.templateName" placeholder="请输入模板名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模板分类" prop="templateCategory">
              <el-select v-model="form.templateCategory" placeholder="请选择分类" style="width: 100%">
                <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="默认Provider" prop="providerCode">
              <el-select v-model="form.providerCode" placeholder="可选，按模板分类过滤" filterable clearable style="width: 100%">
                <el-option v-for="item in promptProviderOptions" :key="item.providerCode" :label="`${item.providerName || item.providerCode} [${item.defaultModel || '-'}]`" :value="item.providerCode" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="默认模型" prop="modelName">
              <el-input v-model="form.modelName" placeholder="可选" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="排序" prop="sort">
              <el-input-number v-model="form.sort" :min="0" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="提示词内容" prop="promptContent">
              <el-input v-model="form.promptContent" type="textarea" :rows="10" placeholder="请输入提示词内容，可使用 {{content}} 等变量" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用状态" prop="enabled">
              <el-switch v-model="form.enabled" inline-prompt active-text="启用" inactive-text="停用" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注" prop="remark">
              <el-input v-model="form.remark" type="textarea" :rows="3" placeholder="请输入备注" />
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
  </div>
</template>

<script setup name="AiPromptTemplate">
import { addAiPromptTemplate, delAiPromptTemplate, getAiPromptTemplate, listAiPromptTemplate, updateAiPromptTemplate } from '@/api/system/aiprompt'
import { listAiProviderOptions } from '@/api/system/aiprovider'

const { proxy } = getCurrentInstance()

const categoryOptions = [
  { label: '翻译', value: 'translate' },
  { label: '版本提取', value: 'version_extract' },
  { label: '分析', value: 'analysis' },
  { label: '通用', value: 'common' },
  { label: '知识沉淀', value: 'knowledge' }
]

const templateList = ref([])
const loading = ref(false)
const showSearch = ref(true)
const total = ref(0)
const formOpen = ref(false)
const dialogTitle = ref('')
const promptProviderOptions = ref([])

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyword: undefined,
    templateCategory: undefined,
    enabled: undefined
  },
  form: {},
  rules: {
    templateCode: [{ required: true, message: '模板编码不能为空', trigger: 'blur' }],
    templateName: [{ required: true, message: '模板名称不能为空', trigger: 'blur' }],
    templateCategory: [{ required: true, message: '模板分类不能为空', trigger: 'change' }],
    promptContent: [{ required: true, message: '提示词内容不能为空', trigger: 'blur' }]
  }
})

const { queryParams, form, rules } = toRefs(data)

function formatCategory(category) {
  const item = categoryOptions.find(row => row.value === category)
  return item ? item.label : category || '-'
}

function getList() {
  loading.value = true
  listAiPromptTemplate(queryParams.value)
    .then(response => {
      templateList.value = response.rows || []
      total.value = response.total || 0
    })
    .finally(() => {
      loading.value = false
    })
}

function resetForm() {
  form.value = {
    templateId: undefined,
    templateCode: '',
    templateName: '',
    templateCategory: 'analysis',
    providerCode: '',
    modelName: '',
    promptContent: '',
    enabled: true,
    sort: 0,
    remark: ''
  }
  proxy.resetForm('templateRef')
}

function getPromptProviderUsage(category) {
  return ['analysis', 'common'].includes(String(category || '').trim())
    ? { usage: 'ticket_analysis_worker', executor: 'codex' }
    : { usage: 'ticket_light_text', executor: 'direct_http' }
}

function loadPromptProviderOptions(category) {
  return listAiProviderOptions(getPromptProviderUsage(category)).then(response => {
    promptProviderOptions.value = Array.isArray(response.data) ? response.data : []
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

function handleAdd() {
  resetForm()
  loadPromptProviderOptions(form.value.templateCategory)
  dialogTitle.value = '新增 AI 提示词模板'
  formOpen.value = true
}

function handleUpdate(row) {
  resetForm()
  getAiPromptTemplate(row.templateId).then(response => {
    form.value = {
      ...form.value,
      ...(response.data || {})
    }
    loadPromptProviderOptions(form.value.templateCategory)
    dialogTitle.value = '编辑 AI 提示词模板'
    formOpen.value = true
  })
}

function submitForm() {
  proxy.$refs.templateRef.validate(valid => {
    if (!valid) return
    const payload = {
      ...form.value,
      sort: Number(form.value.sort || 0)
    }
    const request = payload.templateId ? updateAiPromptTemplate(payload) : addAiPromptTemplate(payload)
    request.then(() => {
      proxy.$modal.msgSuccess(payload.templateId ? '修改成功' : '新增成功')
      formOpen.value = false
      getList()
    })
  })
}

function handleDelete(row) {
  proxy.$modal.confirm(`是否确认删除提示词模板 "${row.templateName || row.templateCode}"？`).then(() => delAiPromptTemplate(row.templateId)).then(() => {
    proxy.$modal.msgSuccess('删除成功')
    getList()
  }).catch(() => {})
}

watch(() => form.value.templateCategory, category => {
  if (formOpen.value) loadPromptProviderOptions(category)
})

getList()
</script>
