<template>
  <div class="app-container">
    <el-form ref="queryRef" :model="queryParams" :inline="true" v-show="showSearch" label-width="90px">
      <el-form-item label="模块编码" prop="moduleCode">
        <el-input
          v-model="queryParams.moduleCode"
          placeholder="请输入模块编码"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="关键字" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="编码/正文/备注"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="enabled">
        <el-select v-model="queryParams.enabled" placeholder="全部状态" clearable style="width: 140px">
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
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['hrm:moduleCommonPrompt:add']">
          新增
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
    </el-row>

    <el-table v-loading="loading" :data="promptList">
      <el-table-column label="ID" prop="promptId" width="180" align="center" />
      <el-table-column label="模块编码" prop="moduleCode" min-width="180" show-overflow-tooltip />
      <el-table-column label="关联模块数" prop="moduleCount" width="110" align="center" />
      <el-table-column label="影响项目数" prop="projectCount" width="110" align="center" />
      <el-table-column label="通用说明" prop="promptContent" min-width="360" show-overflow-tooltip />
      <el-table-column label="状态" width="90" align="center">
        <template #default="scope">
          <el-tag v-if="scope.row.enabled" type="success">启用</el-tag>
          <el-tag v-else type="info">停用</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" prop="updateTime" width="180" align="center">
        <template #default="scope">{{ parseTime(scope.row.updateTime) }}</template>
      </el-table-column>
      <el-table-column label="备注" prop="remark" min-width="160" show-overflow-tooltip />
      <el-table-column label="操作" width="150" fixed="right" align="center">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['hrm:moduleCommonPrompt:edit']">
            编辑
          </el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['hrm:moduleCommonPrompt:remove']">
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

    <el-dialog :title="dialogTitle" v-model="formOpen" width="800px" append-to-body @closed="resetForm">
      <el-alert
        title="修改模块通用说明会影响所有使用该模块编码的项目。"
        type="warning"
        :closable="false"
        show-icon
        class="mb16"
      />
      <el-form ref="promptRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="模块编码" prop="moduleCode">
          <el-select
            v-if="!form.promptId"
            v-model="form.moduleCode"
            filterable
            allow-create
            default-first-option
            clearable
            placeholder="选择或输入模块编码"
            style="width: 100%"
          >
            <el-option
              v-for="item in moduleCodeOptions"
              :key="item.moduleCode"
              :label="`${item.moduleCode}（${item.projectCount} 个项目）`"
              :value="item.moduleCode"
            />
          </el-select>
          <el-input v-else v-model="form.moduleCode" disabled />
          <div class="form-item-tip">同一编码只维护一份通用说明，项目差异请维护在对应项目模块信息中。</div>
        </el-form-item>
        <el-form-item label="通用说明" prop="promptContent">
          <el-input
            v-model="form.promptContent"
            type="textarea"
            :rows="12"
            maxlength="10000"
            show-word-limit
            placeholder="请输入适用于所有同编码模块的标准流程、依赖、异常判断、排查顺序等说明"
          />
        </el-form-item>
        <el-form-item label="启用状态" prop="enabled">
          <el-switch v-model="form.enabled" inline-prompt active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input v-model="form.remark" type="textarea" :rows="3" maxlength="500" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="submitForm">确定</el-button>
        <el-button @click="formOpen = false">取消</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="ModuleCommonPrompt">
import {
  addModuleCommonPrompt,
  delModuleCommonPrompt,
  getModuleCommonPrompt,
  listModuleCommonPrompt,
  listModuleCommonPromptOptions,
  updateModuleCommonPrompt
} from '@/api/hrm/moduleCommonPrompt'

const { proxy } = getCurrentInstance()
const promptList = ref([])
const moduleCodeOptions = ref([])
const loading = ref(false)
const showSearch = ref(true)
const total = ref(0)
const formOpen = ref(false)
const dialogTitle = ref('')

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyword: undefined,
    moduleCode: undefined,
    enabled: undefined
  },
  form: {},
  rules: {
    moduleCode: [{ required: true, message: '模块编码不能为空', trigger: 'change' }],
    promptContent: [{ required: true, message: '通用说明不能为空', trigger: 'blur' }]
  }
})
const { queryParams, form, rules } = toRefs(data)

function getList() {
  loading.value = true
  listModuleCommonPrompt(queryParams.value)
    .then(response => {
      promptList.value = response.rows || []
      total.value = response.total || 0
    })
    .finally(() => {
      loading.value = false
    })
}

function getModuleCodeOptions() {
  listModuleCommonPromptOptions().then(response => {
    moduleCodeOptions.value = response.data || []
  })
}

function resetForm() {
  form.value = {
    promptId: undefined,
    moduleCode: '',
    promptContent: '',
    enabled: true,
    remark: ''
  }
  proxy.resetForm('promptRef')
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
  getModuleCodeOptions()
  dialogTitle.value = '新增模块通用提示词'
  formOpen.value = true
}

function handleUpdate(row) {
  resetForm()
  getModuleCommonPrompt(row.promptId).then(response => {
    form.value = response.data || {}
    dialogTitle.value = '编辑模块通用提示词'
    formOpen.value = true
  })
}

function submitForm() {
  proxy.$refs.promptRef.validate(valid => {
    if (!valid) return
    const payload = { ...form.value }
    const action = payload.promptId ? updateModuleCommonPrompt(payload) : addModuleCommonPrompt(payload)
    action.then(() => {
      proxy.$modal.msgSuccess(payload.promptId ? '修改成功' : '新增成功')
      formOpen.value = false
      getList()
      getModuleCodeOptions()
    })
  })
}

function handleDelete(row) {
  proxy.$modal.confirm(`删除后将停止编码 ${row.moduleCode} 的通用说明，是否继续？`).then(() => {
    return delModuleCommonPrompt(row.promptId)
  }).then(() => {
    proxy.$modal.msgSuccess('删除成功')
    getList()
    getModuleCodeOptions()
  }).catch(() => {})
}

getList()
getModuleCodeOptions()
</script>
