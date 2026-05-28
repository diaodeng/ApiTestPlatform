<template>
  <div class="app-container ticket-ai-repo-mapping-page">
    <el-form ref="queryRef" :model="queryParams" :inline="true" label-width="90px" class="mb16">
      <el-form-item label="项目" prop="projectId">
        <el-select v-model="queryParams.projectId" placeholder="请选择项目" clearable filterable style="width: 220px">
          <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
        </el-select>
      </el-form-item>
      <el-form-item label="版本号" prop="versionKey">
        <el-input v-model="queryParams.versionKey" placeholder="版本标识" clearable style="width: 220px" />
      </el-form-item>
      <el-form-item label="关键字" prop="keyword">
        <el-input v-model="queryParams.keyword" placeholder="项目、版本、仓库或分支" clearable style="width: 220px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['ticket:ai:mapping:add']">新增映射</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="mappingList" row-key="mappingId">
      <el-table-column label="项目" prop="projectName" min-width="180" show-overflow-tooltip />
      <el-table-column label="版本号" prop="versionKey" width="150" show-overflow-tooltip />
      <el-table-column label="仓库地址" prop="repoUrl" min-width="240" show-overflow-tooltip />
      <el-table-column label="分支" prop="branchName" width="180" show-overflow-tooltip />
      <el-table-column label="本地仓库" prop="localRepoPath" min-width="180" show-overflow-tooltip />
      <el-table-column label="默认" width="90" align="center">
        <template #default="scope">
          <el-tag v-if="scope.row.isDefault" type="success">默认</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="scope">
          <el-tag :type="scope.row.enabled ? 'success' : 'info'">{{ scope.row.enabled ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="备注" prop="remark" min-width="180" show-overflow-tooltip />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" @click="handleEdit(scope.row)" v-hasPermi="['ticket:ai:mapping:edit']">
            修改
          </el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['ticket:ai:mapping:remove']">
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
      v-model="open"
      :title="dialogTitle"
      width="760px"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="项目" prop="projectId">
              <el-select v-model="form.projectId" placeholder="请选择项目" filterable style="width: 100%" @change="handleProjectChange">
                <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目名称" prop="projectName">
              <el-input v-model="form.projectName" placeholder="默认自动回填" disabled />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="版本号" prop="versionKey">
              <el-input v-model="form.versionKey" placeholder="例如 release/2.1.3" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分支名称" prop="branchName">
              <el-input v-model="form.branchName" placeholder="例如 release/2.1.3" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="仓库地址" prop="repoUrl">
              <el-input v-model="form.repoUrl" placeholder="git@gitlab.xxx/project.git" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="本地仓库" prop="localRepoPath">
              <el-input v-model="form.localRepoPath" placeholder="留空则使用 Agent 本地配置" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工作区根目录">
              <el-input v-model="form.workspaceRoot" placeholder="留空则使用 Agent 本地配置" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Worker命令">
              <el-input v-model="form.workerCommand" placeholder="留空则使用系统默认 codex exec" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="默认映射">
              <el-switch v-model="form.isDefault" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用状态">
              <el-switch v-model="form.enabled" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="3" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="open = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="TicketAiRepoMapping">
import {
  addTicketAiRepoMapping,
  delTicketAiRepoMapping,
  listTicketAiRepoMappings,
  listTicketProjectOptions,
  updateTicketAiRepoMapping
} from '@/api/ticket/ticket'

const { proxy } = getCurrentInstance()

const loading = ref(false)
const submitting = ref(false)
const open = ref(false)
const isEdit = ref(false)
const mappingList = ref([])
const total = ref(0)
const projectOptions = ref([])

const queryParams = ref({
  pageNum: 1,
  pageSize: 10,
  projectId: undefined,
  versionKey: '',
  keyword: ''
})

const form = ref(createDefaultForm())

const rules = {
  projectId: [{ required: true, message: '请选择项目', trigger: 'change' }],
  versionKey: [{ required: true, message: '版本号不能为空', trigger: 'blur' }],
  repoUrl: [{ required: true, message: '仓库地址不能为空', trigger: 'blur' }],
  branchName: [{ required: true, message: '分支名称不能为空', trigger: 'blur' }]
}

const dialogTitle = computed(() => (isEdit.value ? '修改仓库映射' : '新增仓库映射'))

function createDefaultForm() {
  return {
    mappingId: undefined,
    projectId: undefined,
    projectName: '',
    versionKey: '',
    repoUrl: '',
    branchName: '',
    localRepoPath: '',
    workspaceRoot: '',
    workerCommand: '',
    isDefault: false,
    enabled: true,
    remark: ''
  }
}

function loadProjectOptions() {
  return listTicketProjectOptions().then(response => {
    projectOptions.value = response.data || []
  })
}

function getList() {
  loading.value = true
  listTicketAiRepoMappings(queryParams.value).then(response => {
    mappingList.value = response.rows || []
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
    projectId: undefined,
    versionKey: '',
    keyword: ''
  }
  handleQuery()
}

function resetForm() {
  form.value = createDefaultForm()
  isEdit.value = false
  if (proxy.$refs.formRef) {
    proxy.resetForm('formRef')
  }
}

function handleAdd() {
  resetForm()
  open.value = true
}

function handleProjectChange(projectId) {
  const project = projectOptions.value.find(item => item.projectId === projectId)
  form.value.projectName = project?.projectName || ''
}

function handleEdit(row) {
  form.value = {
    mappingId: row.mappingId,
    projectId: row.projectId,
    projectName: row.projectName || '',
    versionKey: row.versionKey || '',
    repoUrl: row.repoUrl || '',
    branchName: row.branchName || '',
    localRepoPath: row.localRepoPath || '',
    workspaceRoot: row.workspaceRoot || '',
    workerCommand: row.workerCommand || '',
    isDefault: Boolean(row.isDefault),
    enabled: row.enabled !== false,
    remark: row.remark || ''
  }
  isEdit.value = true
  open.value = true
}

function submitForm() {
  proxy.$refs.formRef.validate(valid => {
    if (!valid) return
    submitting.value = true
    const payload = { ...form.value }
    const request = payload.mappingId ? updateTicketAiRepoMapping(payload) : addTicketAiRepoMapping(payload)
    request.then(() => {
      proxy.$modal.msgSuccess(payload.mappingId ? '映射更新成功' : '映射新增成功')
      open.value = false
      getList()
    }).finally(() => {
      submitting.value = false
    })
  })
}

function handleDelete(row) {
  if (!row?.mappingId) {
    return
  }
  proxy.$modal.confirm(`是否确认删除版本映射 "${row.versionKey}"？`).then(() => {
    loading.value = true
    return delTicketAiRepoMapping(row.mappingId)
  }).then(() => {
    proxy.$modal.msgSuccess('删除成功')
    getList()
  }).catch(() => {}).finally(() => {
    loading.value = false
  })
}

loadProjectOptions()
getList()
</script>

<style scoped>
.mb16 {
  margin-bottom: 16px;
}
</style>
