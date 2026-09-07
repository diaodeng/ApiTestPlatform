<template>
  <div class="app-container credential-page">
    <el-tabs v-model="activeTab" class="credential-tabs">
      <el-tab-pane name="credentials">
        <template #label><span>凭证</span></template>
        <div class="table-toolbar">
          <el-button v-hasPermi="['system:credential:add']" type="primary" icon="Plus" @click="openCredential()">新增凭证</el-button>
        </div>
        <el-table v-loading="credentialLoading" :data="credentials" border>
          <el-table-column prop="credentialId" label="ID" width="100" />
          <el-table-column prop="credentialName" label="凭证名称" min-width="180" show-overflow-tooltip />
          <el-table-column label="类型" width="150"><template #default="{ row }">{{ credentialTypeLabel(row.credentialType) }}</template></el-table-column>
          <el-table-column label="认证方式" width="150"><template #default="{ row }">{{ authModeLabel(row.authMode) }}</template></el-table-column>
          <el-table-column prop="secretMask" label="敏感字段" min-width="180" show-overflow-tooltip />
          <el-table-column label="刷新状态" width="150">
            <template #default="{ row }">
              <el-tag :type="row.lastRefreshStatus === 'success' ? 'success' : 'info'">{{ refreshStatusLabel(row.lastRefreshStatus) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="自动刷新" width="190">
            <template #default="{ row }">
              <el-tag v-if="row.autoRefreshEnabled" type="success">每 {{ row.refreshIntervalSec }} 秒</el-tag>
              <el-tag v-else :type="supportsAutoRefreshMode(row.authMode) ? 'warning' : 'info'">{{ supportsAutoRefreshMode(row.authMode) ? '未开启' : '不支持' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="最近刷新" width="160">
            <template #default="{ row }">
              <span v-if="row.lastRefreshTime" :title="row.lastRefreshMessage">{{ formatTime(row.lastRefreshTime) }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="80"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag></template></el-table-column>
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openCredential(row)">编辑</el-button>
              <el-button v-if="row.authMode.startsWith('http_')" link type="primary" @click="refresh(row)">刷新</el-button>
              <el-button link type="danger" @click="removeCredential(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane name="bindings" lazy>
        <template #label><span>业务绑定</span></template>
        <div class="table-toolbar">
          <el-button v-hasPermi="['system:credential:add']" type="primary" icon="Plus" @click="openBinding()">新增绑定</el-button>
        </div>
        <el-table v-loading="bindingLoading" :data="bindings" border>
          <el-table-column prop="bindingId" label="ID" width="100" />
          <el-table-column prop="bindingName" label="绑定名称" min-width="180" show-overflow-tooltip />
          <el-table-column label="业务场景" width="140"><template #default="{ row }">{{ businessTypeLabel(row.businessType) }}</template></el-table-column>
          <el-table-column prop="credentialName" label="凭证" min-width="180" show-overflow-tooltip />
          <el-table-column label="投影方式" width="150"><template #default="{ row }">{{ projectionTypeLabel(row.projectionType) }}</template></el-table-column>
          <el-table-column label="回写" width="80"><template #default="{ row }"><el-tag :type="row.writebackEnabled ? 'warning' : 'info'">{{ row.writebackEnabled ? '允许' : '关闭' }}</el-tag></template></el-table-column>
          <el-table-column label="启用" width="80"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag></template></el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openBinding(row)">编辑</el-button>
              <el-button link type="danger" @click="removeBinding(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <CredentialDialog ref="credentialDialogRef" @saved="loadAll" />

    <el-dialog v-model="bindingOpen" :title="bindingForm.bindingId ? '编辑绑定' : '新增绑定'" width="680px" append-to-body>
      <el-form :model="bindingForm" label-width="120px">
        <el-form-item label="绑定名称" required><el-input v-model="bindingForm.bindingName" /></el-form-item>
        <el-form-item label="凭证" required><el-select v-model="bindingForm.credentialId" filterable style="width: 100%"><el-option v-for="item in credentials" :key="item.credentialId" :label="`${item.credentialName}（${credentialTypeLabel(item.credentialType)}）`" :value="item.credentialId" /></el-select></el-form-item>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="业务场景"><el-select v-model="bindingForm.businessType" style="width: 100%" @change="resetProjection"><el-option v-for="item in businessTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="投影方式"><el-select v-model="bindingForm.projectionType" style="width: 100%"><el-option v-for="item in bindingProjections" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
        </el-row>
        <el-form-item label="目标地址"><el-input v-model="bindingForm.targetUrl" /></el-form-item>
        <el-form-item label="允许域名"><el-input v-model="targetHostPatternsText" placeholder="多个域名使用英文逗号分隔，例如 *.example.com" /></el-form-item>
        <el-form-item label="并发策略"><el-select v-model="bindingForm.sharingMode" style="width: 100%"><el-option v-for="item in sharingModes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
        <el-form-item v-if="bindingForm.businessType === 'web_case'" label="允许回写"><el-switch v-model="bindingForm.writebackEnabled" /><span class="ml8 unit-text">需同时启用本地浏览器状态缓存</span></el-form-item>
        <el-form-item label="启用"><el-switch v-model="bindingForm.enabled" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="bindingForm.remark" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="bindingOpen = false">取消</el-button><el-button type="primary" @click="saveBinding">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup name="Credential">
import {
  addCredentialBinding,
  delCredential,
  delCredentialBinding,
  listCredentialBindings,
  listCredentials,
  refreshCredential,
  updateCredentialBinding,
} from '@/api/system/credential'
import CredentialDialog from './components/CredentialDialog.vue'

const { proxy } = getCurrentInstance()
const activeTab = ref('credentials')
const credentialLoading = ref(false)
const bindingLoading = ref(false)
const credentials = ref([])
const bindings = ref([])
const credentialDialogRef = ref()
const bindingOpen = ref(false)
const targetHostPatternsText = ref('')

const credentialTypes = [
  { value: 'browser_storage', label: '浏览器状态' }, { value: 'http_cookie', label: 'HTTP Cookie' },
  { value: 'http_token', label: 'HTTP Token' }, { value: 'http_api_key', label: 'API Key' }, { value: 'http_header', label: 'HTTP Header' },
]
const authModes = [
  { value: 'manual', label: '手工录入' }, { value: 'http_login', label: 'HTTP 登录' }, { value: 'http_refresh', label: 'HTTP 刷新' },
  { value: 'browser_login', label: '浏览器登录' }, { value: 'browser_refresh', label: '浏览器刷新' },
]
const sharingModes = [
  { value: 'shared_read', label: '共享读取' }, { value: 'exclusive_refresh', label: '独占刷新' }, { value: 'exclusive_use', label: '独占使用' },
]
const businessTypes = [
  { value: 'ticket_remote_sync', label: '远端工单同步' }, { value: 'ticket_log_pull', label: '工单日志拉取' }, { value: 'web_case', label: 'Web 用例' },
]
const bindingProjections = computed(() => bindingForm.businessType === 'web_case'
  ? [{ value: 'playwright_storage', label: 'Playwright storageState' }]
  : [{ value: 'http_header', label: 'HTTP Header' }, { value: 'http_cookie', label: 'HTTP Cookie' }])
const emptyBinding = () => ({ bindingId: '', bindingName: '', credentialId: '', businessType: 'ticket_remote_sync', projectionType: 'http_header', targetUrl: '', targetHostPatterns: [], sharingMode: 'shared_read', writebackEnabled: false, enabled: true, remark: '' })
const bindingForm = reactive(emptyBinding())

const credentialTypeLabel = value => credentialTypes.find(item => item.value === value)?.label || value || '-'
const authModeLabel = value => authModes.find(item => item.value === value)?.label || value || '-'
const businessTypeLabel = value => businessTypes.find(item => item.value === value)?.label || value || '-'
const projectionTypeLabel = value => ({ playwright_storage: 'Playwright storageState', http_header: 'HTTP Header', http_cookie: 'HTTP Cookie' })[value] || value || '-'
const refreshStatusLabel = value => ({ never: '未刷新', success: '成功', failed: '失败', conflict: '版本冲突' })[value] || value || '-'
const supportsAutoRefreshMode = mode => ['http_login', 'http_refresh'].includes(mode)
function formatTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 19)
}

function loadCredentials() {
  credentialLoading.value = true
  return listCredentials().then(response => { credentials.value = response.data || [] }).finally(() => { credentialLoading.value = false })
}
function loadBindings() {
  bindingLoading.value = true
  return listCredentialBindings().then(response => { bindings.value = response.data || [] }).finally(() => { bindingLoading.value = false })
}
function loadAll() { return Promise.all([loadCredentials(), loadBindings()]) }
function openCredential(row) {
  credentialDialogRef.value?.open(row)
}
function removeCredential(row) {
  proxy.$modal.confirm(`确认删除凭证「${row.credentialName}」？`).then(() => delCredential(row.credentialId)).then(() => { proxy.$modal.msgSuccess('删除成功'); loadAll() }).catch(() => {})
}
function refresh(row) {
  const otpType = row.authConfig?.otpType || 'none'
  if (row.authMode === 'http_login' && ['sms', 'email', 'manual'].includes(otpType)) {
    proxy.$prompt(otpType === 'manual' ? '请输入人工确认值' : '请输入本次 OTP 验证码', '手工刷新凭证', {
      confirmButtonText: '刷新', cancelButtonText: '取消', inputPattern: /^.{1,32}$/, inputErrorMessage: '请输入 1-32 位内容',
    }).then(({ value }) => refreshCredential(row.credentialId, { expectedRevision: row.revision, otpCode: value }))
      .then(() => { proxy.$modal.msgSuccess('刷新完成'); loadCredentials() }).catch(() => {})
    return
  }
  refreshCredential(row.credentialId, { expectedRevision: row.revision }).then(() => { proxy.$modal.msgSuccess('刷新完成'); loadCredentials() })
}
function openBinding(row) {
  Object.assign(bindingForm, emptyBinding(), row || {})
  targetHostPatternsText.value = (bindingForm.targetHostPatterns || []).join(', ')
  bindingOpen.value = true
}
function resetProjection() {
  bindingForm.projectionType = bindingForm.businessType === 'web_case' ? 'playwright_storage' : 'http_header'
  if (bindingForm.businessType !== 'web_case') bindingForm.writebackEnabled = false
}
function saveBinding() {
  const data = { ...bindingForm, targetHostPatterns: targetHostPatternsText.value.split(',').map(item => item.trim()).filter(Boolean) }
  const request = bindingForm.bindingId ? updateCredentialBinding(bindingForm.bindingId, data) : addCredentialBinding(data)
  request.then(() => { proxy.$modal.msgSuccess('保存成功'); bindingOpen.value = false; loadBindings() })
}
function removeBinding(row) {
  proxy.$modal.confirm(`确认删除绑定「${row.bindingName}」？`).then(() => delCredentialBinding(row.bindingId)).then(() => { proxy.$modal.msgSuccess('删除成功'); loadBindings() }).catch(() => {})
}

loadAll()
</script>

<style scoped>
.table-toolbar { display: flex; justify-content: flex-end; margin-bottom: 12px; }
.credential-tabs :deep(.el-tabs__header) { margin-bottom: 16px; }
.unit-text { color: var(--el-text-color-secondary); font-size: 13px; }
</style>
