<template>
  <div class="app-container">
    <el-alert
      title="工作流变更会影响后续工单状态流转；删除状态时，已被工单、历史或流转规则引用的状态会被后端拒绝。"
      type="warning"
      show-icon
      class="mb16"
    />

    <el-row :gutter="16">
      <el-col :span="10">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>状态节点</span>
              <div>
                <el-button type="primary" link icon="Plus" @click="openStatusDialog()" v-hasPermi="['ticket:workflow:edit']">
                  新增
                </el-button>
                <el-button type="primary" link icon="Refresh" @click="getWorkflow">刷新</el-button>
              </div>
            </div>
          </template>
          <el-table v-loading="loading" :data="workflow.statuses || []" row-key="id">
            <el-table-column label="编码" prop="code" min-width="150" show-overflow-tooltip />
            <el-table-column label="名称" prop="name" width="120" />
            <el-table-column label="开始" prop="isStart" width="70" align="center">
              <template #default="scope">
                <el-tag v-if="scope.row.isStart" type="success">是</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="结束" prop="isEnd" width="70" align="center">
              <template #default="scope">
                <el-tag v-if="scope.row.isEnd" type="info">是</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="135" fixed="right">
              <template #default="scope">
                <el-button link type="primary" icon="Edit" @click="openStatusDialog(scope.row)" v-hasPermi="['ticket:workflow:edit']">
                  编辑
                </el-button>
                <el-button
                  link
                  type="danger"
                  icon="Delete"
                  @click="handleDeleteStatus(scope.row)"
                  v-hasPermi="['ticket:workflow:remove']"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>流转规则</span>
              <el-button type="primary" link icon="Plus" @click="openTransitionDialog()" v-hasPermi="['ticket:workflow:edit']">
                新增
              </el-button>
            </div>
          </template>
          <el-table v-loading="loading" :data="workflow.transitions || []" row-key="id">
            <el-table-column label="原状态" prop="fromStatus" min-width="150">
              <template #default="scope">{{ statusName(scope.row.fromStatus) }}</template>
            </el-table-column>
            <el-table-column label="目标状态" prop="toStatus" min-width="150">
              <template #default="scope">{{ statusName(scope.row.toStatus) }}</template>
            </el-table-column>
            <el-table-column label="需要说明" prop="needComment" width="95" align="center">
              <template #default="scope">
                <el-tag :type="scope.row.needComment ? 'warning' : 'info'">
                  {{ scope.row.needComment ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="需要方案" prop="needResolution" width="95" align="center">
              <template #default="scope">
                <el-tag :type="scope.row.needResolution ? 'warning' : 'info'">
                  {{ scope.row.needResolution ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="135" fixed="right">
              <template #default="scope">
                <el-button link type="primary" icon="Edit" @click="openTransitionDialog(scope.row)" v-hasPermi="['ticket:workflow:edit']">
                  编辑
                </el-button>
                <el-button
                  link
                  type="danger"
                  icon="Delete"
                  @click="handleDeleteTransition(scope.row)"
                  v-hasPermi="['ticket:workflow:remove']"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog :title="statusTitle" v-model="statusOpen" width="560px" append-to-body>
      <el-form ref="statusRef" :model="statusForm" :rules="statusRules" label-width="100px">
        <el-form-item label="状态编码" prop="code">
          <el-input v-model="statusForm.code" placeholder="如 pending/custom_review" />
        </el-form-item>
        <el-form-item label="状态名称" prop="name">
          <el-input v-model="statusForm.name" placeholder="请输入状态名称" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="statusForm.orderNum" :min="0" controls-position="right" />
        </el-form-item>
        <el-form-item label="状态标记">
          <el-checkbox v-model="statusForm.isStart">开始状态</el-checkbox>
          <el-checkbox v-model="statusForm.isEnd">结束状态</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="submitStatus">确 定</el-button>
        <el-button @click="statusOpen = false">取 消</el-button>
      </template>
    </el-dialog>

    <el-dialog :title="transitionTitle" v-model="transitionOpen" width="640px" append-to-body>
      <el-form ref="transitionRef" :model="transitionForm" :rules="transitionRules" label-width="110px">
        <el-form-item label="原状态" prop="fromStatus">
          <el-select v-model="transitionForm.fromStatus" placeholder="请选择原状态" filterable>
            <el-option v-for="item in workflow.statuses" :key="item.code" :label="statusName(item.code)" :value="item.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标状态" prop="toStatus">
          <el-select v-model="transitionForm.toStatus" placeholder="请选择目标状态" filterable>
            <el-option v-for="item in workflow.statuses" :key="item.code" :label="statusName(item.code)" :value="item.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="允许角色">
          <el-input v-model="allowedRolesText" placeholder="逗号分隔角色编码，留空表示不限制" />
        </el-form-item>
        <el-form-item label="流转要求">
          <el-checkbox v-model="transitionForm.needComment">需要说明</el-checkbox>
          <el-checkbox v-model="transitionForm.needResolution">需要解决方案</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="submitTransition">确 定</el-button>
        <el-button @click="transitionOpen = false">取 消</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="TicketWorkflow">
import {
  delWorkflowStatus,
  delWorkflowTransition,
  getTicketWorkflow,
  saveWorkflowStatus,
  saveWorkflowTransition
} from '@/api/ticket/ticket'

const { proxy } = getCurrentInstance()

const loading = ref(false)
const statusOpen = ref(false)
const transitionOpen = ref(false)
const statusTitle = ref('')
const transitionTitle = ref('')
const allowedRolesText = ref('')

const workflow = ref({
  statuses: [],
  transitions: []
})

const data = reactive({
  statusForm: {},
  transitionForm: {},
  statusRules: {
    code: [{ required: true, message: '状态编码不能为空', trigger: 'blur' }],
    name: [{ required: true, message: '状态名称不能为空', trigger: 'blur' }]
  },
  transitionRules: {
    fromStatus: [{ required: true, message: '原状态不能为空', trigger: 'change' }],
    toStatus: [{ required: true, message: '目标状态不能为空', trigger: 'change' }]
  }
})

const { statusForm, transitionForm, statusRules, transitionRules } = toRefs(data)

function getWorkflow() {
  loading.value = true
  getTicketWorkflow().then(response => {
    workflow.value = response.data || { statuses: [], transitions: [] }
  }).finally(() => {
    loading.value = false
  })
}

function statusName(status) {
  const item = (workflow.value.statuses || []).find(row => row.code === status)
  return item ? `${item.name}（${item.code}）` : status
}

function openStatusDialog(row) {
  statusForm.value = row ? { ...row } : {
    id: undefined,
    code: '',
    name: '',
    isStart: false,
    isEnd: false,
    orderNum: 0
  }
  statusTitle.value = row ? '编辑状态节点' : '新增状态节点'
  statusOpen.value = true
}

function submitStatus() {
  proxy.$refs.statusRef.validate(valid => {
    if (!valid) return
    saveWorkflowStatus(statusForm.value).then(() => {
      proxy.$modal.msgSuccess(statusForm.value.id ? '更新成功' : '新增成功')
      statusOpen.value = false
      getWorkflow()
    })
  })
}

function handleDeleteStatus(row) {
  proxy.$modal.confirm(`是否确认删除状态 "${row.name}"？`).then(() => delWorkflowStatus(row.id)).then(() => {
    proxy.$modal.msgSuccess('删除成功')
    getWorkflow()
  }).catch(() => {})
}

function openTransitionDialog(row) {
  transitionForm.value = row ? { ...row } : {
    id: undefined,
    fromStatus: '',
    toStatus: '',
    allowedRoles: [],
    needComment: false,
    needResolution: false
  }
  allowedRolesText.value = Array.isArray(transitionForm.value.allowedRoles)
    ? transitionForm.value.allowedRoles.join(',')
    : ''
  transitionTitle.value = row ? '编辑流转规则' : '新增流转规则'
  transitionOpen.value = true
}

function submitTransition() {
  proxy.$refs.transitionRef.validate(valid => {
    if (!valid) return
    const payload = {
      ...transitionForm.value,
      allowedRoles: allowedRolesText.value ? allowedRolesText.value.split(',').map(item => item.trim()).filter(Boolean) : []
    }
    saveWorkflowTransition(payload).then(() => {
      proxy.$modal.msgSuccess(payload.id ? '更新成功' : '新增成功')
      transitionOpen.value = false
      getWorkflow()
    })
  })
}

function handleDeleteTransition(row) {
  proxy.$modal.confirm(`是否确认删除流转 "${statusName(row.fromStatus)} -> ${statusName(row.toStatus)}"？`).then(() => {
    return delWorkflowTransition(row.id)
  }).then(() => {
    proxy.$modal.msgSuccess('删除成功')
    getWorkflow()
  }).catch(() => {})
}

getWorkflow()
</script>

<style scoped>
.mb16 {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
