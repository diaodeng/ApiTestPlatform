<template>
  <el-dialog v-model="visible" :title="form.credentialId ? '编辑凭证' : '新增凭证'" width="880px" append-to-body destroy-on-close>
    <el-form :model="form" label-width="126px">
      <el-divider content-position="left">基本信息</el-divider>
      <el-form-item label="凭证名称" required><el-input v-model="form.credentialName" /></el-form-item>
      <el-row :gutter="16">
        <el-col :span="12"><el-form-item label="凭证类型"><el-select v-model="form.credentialType" style="width:100%"><el-option v-for="item in credentialTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="更新方式"><el-select v-model="form.authMode" style="width:100%"><el-option v-for="item in authModes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
      </el-row>

      <el-divider content-position="left">凭证内容</el-divider>
      <el-alert type="info" :closable="false" show-icon class="section-alert">
        <template #title>敏感字段只在保存时提交并加密，编辑时留空会保留原值。</template>
      </el-alert>
      <template v-if="form.credentialType === 'http_cookie'">
        <el-form-item label="Cookie"><el-input v-model="sensitive.cookie" type="textarea" :rows="3" placeholder="例如 SESSION=xxx; tenant=prod" /></el-form-item>
      </template>
      <template v-else-if="form.credentialType === 'http_header' || form.credentialType === 'http_api_key'">
        <el-row :gutter="16">
          <el-col :span="10"><el-form-item label="Header 名称"><el-input v-model="sensitive.headerName" placeholder="例如 X-API-Key" /></el-form-item></el-col>
          <el-col :span="14"><el-form-item label="Header 值"><el-input v-model="sensitive.headerValue" type="password" show-password autocomplete="new-password" /></el-form-item></el-col>
        </el-row>
      </template>
      <template v-else-if="form.credentialType === 'http_token'">
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="Header 名称"><el-input v-model="sensitive.headerName" placeholder="Authorization" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="值前缀"><el-input v-model="sensitive.valuePrefix" placeholder="Bearer " /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="Token"><el-input v-model="sensitive.token" type="password" show-password autocomplete="new-password" /></el-form-item></el-col>
        </el-row>
      </template>
      <el-form-item v-else label="storageState"><el-input v-model="storageStateText" type="textarea" :rows="5" placeholder='Playwright storageState，例如 {"cookies":[],"origins":[]}' /></el-form-item>
      <el-form-item v-if="form.credentialType !== 'browser_storage'" label="其他敏感字段 JSON">
        <el-input v-model="advancedSecretText" type="textarea" :rows="3" placeholder='可选，例如 {"refreshToken":"...","headers":{"X-Tenant":"..."}}；固定敏感值会加密保存' />
      </el-form-item>

      <template v-if="form.authMode === 'http_login'">
        <el-divider content-position="left">登录账号</el-divider>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="用户名"><el-input v-model="sensitive.username" autocomplete="off" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="密码"><el-input v-model="sensitive.password" type="password" show-password autocomplete="new-password" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="OTP 类型"><el-select v-model="form.authConfig.otpType" style="width:100%"><el-option v-for="item in otpTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item></el-col>
          <el-col v-if="form.authConfig.otpType === 'totp'" :span="12"><el-form-item label="TOTP 密钥"><el-input v-model="sensitive.otpSecret" type="password" show-password autocomplete="new-password" /></el-form-item></el-col>
        </el-row>
      </template>

      <template v-if="isHttpMode">
        <el-divider content-position="left">{{ form.authMode === 'http_login' ? '登录接口' : '刷新接口' }}</el-divider>
        <el-alert v-if="form.authMode === 'http_refresh'" type="success" :closable="false" show-icon class="section-alert" title="刷新请求会自动携带当前 Cookie/Header；响应含 Set-Cookie 时无需额外映射即可更新 Cookie。" />
        <el-row :gutter="16">
          <el-col :span="7"><el-form-item label="请求方法"><el-select v-model="activeRequest.method" style="width:100%"><el-option v-for="method in requestMethods" :key="method" :value="method" /></el-select></el-form-item></el-col>
          <el-col :span="17"><el-form-item label="接口地址" required><el-input v-model="activeRequest.url" placeholder="https://example.com/api/login" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="请求 Header"><el-input v-model="activeRequest.headersText" type="textarea" :rows="2" placeholder='JSON，例如 {"Content-Type":"application/json"}' /></el-form-item>
        <el-form-item label="查询参数"><el-input v-model="activeRequest.queryText" type="textarea" :rows="2" placeholder='JSON，例如 {"tenant":"prod"}' /></el-form-item>
        <el-form-item label="JSON 请求体"><el-input v-model="activeRequest.bodyText" type="textarea" :rows="4" :placeholder="requestBodyPlaceholder" /></el-form-item>
        <el-form-item label="表单请求体"><el-input v-model="activeRequest.dataText" type="textarea" :rows="3" placeholder='仅 application/x-www-form-urlencoded 使用，例如 {"username":"${secret.username}"}' /></el-form-item>

        <el-divider content-position="left">响应提取</el-divider>
        <el-alert type="info" :closable="false" show-icon class="section-alert" title="把响应中的新值写回凭证字段。来源支持 json:data.token、header:X-Auth-Token、cookie:SESSION、cookies。" />
        <div v-for="(item, index) in activeRequest.mappings" :key="index" class="mapping-row">
          <el-input v-model="item.target" placeholder="凭证字段，例如 token" />
          <el-input v-model="item.source" placeholder="来源，例如 json:data.accessToken" />
          <el-button :icon="Delete" circle plain type="danger" title="删除映射" @click="activeRequest.mappings.splice(index, 1)" />
        </div>
        <el-button :icon="Plus" plain @click="activeRequest.mappings.push({ target: '', source: '' })">添加提取规则</el-button>
      </template>

      <el-divider content-position="left">刷新与状态</el-divider>
      <el-form-item label="自动刷新"><el-switch v-model="form.autoRefreshEnabled" :disabled="!supportsAutoRefresh" /><el-input-number v-if="form.autoRefreshEnabled" v-model="form.refreshIntervalSec" :min="60" class="ml8" /><span v-if="form.autoRefreshEnabled" class="ml8 unit-text">秒</span></el-form-item>
      <el-form-item label="并发策略"><el-select v-model="form.sharingMode" style="width:100%"><el-option v-for="item in sharingModes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
      <el-form-item label="允许域名"><el-input v-model="targetHostsText" placeholder="多个域名用英文逗号分隔，例如 *.example.com" /></el-form-item>
      <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      <el-form-item label="备注"><el-input v-model="form.remark" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
  </el-dialog>
</template>

<script setup>
import { Delete, Plus } from '@element-plus/icons-vue'
import { addCredential, updateCredential } from '@/api/system/credential'

const emit = defineEmits(['saved'])
const { proxy } = getCurrentInstance()
const visible = ref(false)
const saving = ref(false)
const storageStateText = ref('')
const advancedSecretText = ref('')
const targetHostsText = ref('')
const sensitive = reactive({ cookie: '', headerName: '', headerValue: '', valuePrefix: 'Bearer ', token: '', username: '', password: '', otpSecret: '' })
const requestMethods = ['GET', 'POST', 'PUT', 'PATCH']
const credentialTypes = [{ value:'browser_storage',label:'浏览器状态'},{value:'http_cookie',label:'HTTP Cookie'},{value:'http_token',label:'HTTP Token'},{value:'http_api_key',label:'API Key'},{value:'http_header',label:'HTTP Header'}]
const authModes = [{value:'manual',label:'手工录入，不自动更新'},{value:'http_login',label:'HTTP 登录重新获取'},{value:'http_refresh',label:'携带现有凭证刷新'},{value:'browser_login',label:'浏览器人工登录'},{value:'browser_refresh',label:'浏览器刷新'}]
const otpTypes = [{value:'none',label:'不需要'},{value:'totp',label:'TOTP 自动生成'},{value:'sms',label:'短信验证码（需人工/外部服务）'},{value:'email',label:'邮箱验证码（需人工/外部服务）'},{value:'manual',label:'人工确认'}]
const sharingModes = [{value:'shared_read',label:'共享读取'},{value:'exclusive_refresh',label:'刷新时独占'},{value:'exclusive_use',label:'使用期间独占'}]
const emptyRequest = () => ({ url:'', method:'POST', headersText:'{}', queryText:'{}', bodyText:'{}', dataText:'{}', mappings:[] })
const loginRequest = reactive(emptyRequest())
const refreshRequest = reactive(emptyRequest())
const emptyForm = () => ({ credentialName:'', credentialType:'http_cookie', authMode:'manual', enabled:true, autoRefreshEnabled:false, refreshIntervalSec:0, sharingMode:'shared_read', authConfig:{ otpType:'none', targetHostPatterns:[] }, remark:'' })
const form = reactive(emptyForm())
const isHttpMode = computed(() => ['http_login','http_refresh'].includes(form.authMode))
const supportsAutoRefresh = computed(() => ['http_login','http_refresh'].includes(form.authMode))
const activeRequest = computed(() => form.authMode === 'http_login' ? loginRequest : refreshRequest)
const requestBodyPlaceholder = computed(() => form.authMode === 'http_login' ? '{"username":"${secret.username}","password":"${secret.password}"}' : '{}，刷新时当前 Cookie/Header 会自动携带')

watch(() => form.authMode, mode => {
  if (mode === 'http_login' && loginRequest.bodyText.trim() === '{}') {
    loginRequest.bodyText = jsonText({ username:'${secret.username}', password:'${secret.password}' })
  }
  if (!supportsAutoRefresh.value) form.autoRefreshEnabled = false
})
watch(() => form.authConfig.otpType, otpType => {
  if (form.authMode !== 'http_login' || otpType !== 'totp') return
  try {
    const body = parseObject(loginRequest.bodyText, 'JSON 请求体')
    if (!Object.values(body).includes('${secret.otp}')) loginRequest.bodyText = jsonText({ ...body, otp:'${secret.otp}' })
  } catch (_) { /* 用户正在编辑 JSON 时不覆盖输入。 */ }
})

function jsonText(value) { return JSON.stringify(value || {}, null, 2) }
function restoreRedacted(value) {
  if (Array.isArray(value)) return value.map(restoreRedacted)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, item === '******' ? `\${secret.${key}}` : restoreRedacted(item)]))
}
function mappingRows(mapping) { return Object.entries(mapping || {}).map(([target, source]) => ({ target, source })) }
function resetRequest(target, config, prefix) {
  const template = restoreRedacted(config?.[`${prefix}RequestTemplate`] || {})
  Object.assign(target, emptyRequest(), {
    url: config?.[`${prefix}Url`] || '', method: config?.[`${prefix}Method`] || config?.requestMethod || 'POST',
    headersText: jsonText(template.headers), queryText: jsonText(template.query || template.params),
    bodyText: jsonText(template.body), dataText: jsonText(template.data),
    mappings: mappingRows(config?.[`${prefix}ResponseMapping`] || config?.responseMapping),
  })
}
function open(row) {
  Object.assign(form, emptyForm(), row || {}, { authConfig: { ...emptyForm().authConfig, ...(row?.authConfig || {}) } })
  Object.keys(sensitive).forEach(key => { sensitive[key] = key === 'valuePrefix' ? 'Bearer ' : '' })
  storageStateText.value = ''
  advancedSecretText.value = ''
  targetHostsText.value = (form.authConfig.targetHostPatterns || []).join(', ')
  resetRequest(loginRequest, form.authConfig, 'login')
  resetRequest(refreshRequest, form.authConfig, 'refresh')
  visible.value = true
}
function parseObject(text, label) {
  const value = JSON.parse(text || '{}')
  if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error(`${label}必须是 JSON 对象`)
  return value
}
function buildRequest(request) {
  return { headers:parseObject(request.headersText,'请求 Header'), query:parseObject(request.queryText,'查询参数'), body:parseObject(request.bodyText,'JSON 请求体'), data:parseObject(request.dataText,'表单请求体') }
}
function buildMapping(request) {
  return Object.fromEntries(request.mappings.filter(item => item.target.trim() && item.source.trim()).map(item => [item.target.trim(), item.source.trim()]))
}
function buildSecret() {
  const secret = {}
  if (form.credentialType === 'http_cookie' && sensitive.cookie.trim()) secret.cookie = sensitive.cookie.trim()
  if (['http_header','http_api_key'].includes(form.credentialType)) {
    if (sensitive.headerName.trim()) secret.headerName = sensitive.headerName.trim()
    if (sensitive.headerValue) secret.headerValue = sensitive.headerValue
  }
  if (form.credentialType === 'http_token') {
    if (sensitive.headerName.trim()) secret.headerName = sensitive.headerName.trim()
    if (sensitive.valuePrefix) secret.valuePrefix = sensitive.valuePrefix
    if (sensitive.token) secret.token = sensitive.token
  }
  if (storageStateText.value.trim()) secret.storageState = parseObject(storageStateText.value, 'storageState')
  if (advancedSecretText.value.trim()) Object.assign(secret, parseObject(advancedSecretText.value, '其他敏感字段'))
  for (const key of ['username','password','otpSecret']) if (sensitive[key]) secret[key] = sensitive[key]
  return secret
}
async function save() {
  try {
    if (!form.credentialName.trim()) return proxy.$modal.msgError('请填写凭证名称')
    if (form.autoRefreshEnabled && !supportsAutoRefresh.value) return proxy.$modal.msgError('当前更新方式不支持自动刷新')
    const authConfig = { ...form.authConfig, targetHostPatterns:targetHostsText.value.split(',').map(v=>v.trim()).filter(Boolean), loginUrl:loginRequest.url, refreshUrl:refreshRequest.url, loginMethod:loginRequest.method, refreshMethod:refreshRequest.method, loginRequestTemplate:buildRequest(loginRequest), refreshRequestTemplate:buildRequest(refreshRequest), loginResponseMapping:buildMapping(loginRequest), refreshResponseMapping:buildMapping(refreshRequest) }
    const data = { ...form, secret:buildSecret(), authConfig }
    saving.value = true
    const request = form.credentialId ? updateCredential(form.credentialId, { ...data, expectedRevision:form.revision }) : addCredential(data)
    await request
    proxy.$modal.msgSuccess('保存成功')
    visible.value = false
    emit('saved')
  } catch (error) {
    proxy.$modal.msgError(error?.message || '配置格式错误')
  } finally { saving.value = false }
}

defineExpose({ open })
</script>

<style scoped>
.section-alert { margin-bottom: 16px; }
.mapping-row { display:grid; grid-template-columns: 1fr 1.4fr 32px; gap:8px; margin-bottom:8px; align-items:center; }
.unit-text { color:var(--el-text-color-secondary); font-size:13px; }
</style>
