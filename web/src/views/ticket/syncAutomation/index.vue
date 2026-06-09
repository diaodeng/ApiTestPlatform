<template>
  <div class="app-container ticket-sync-automation-page" v-loading="loading">
    <section class="page-intro">
      <div class="page-intro__eyebrow">工单同步自动化</div>
      <h2 class="page-intro__title">这里配置外部同步入库后的自动化行为</h2>
      <p class="page-intro__desc">
        这里只管三方直推和内网定时拉取两条外部同步链路。手动新增、编辑后的自动翻译，以及创建后拉日志，走工单页本身的开关，不在这里配置。
      </p>
    </section>

    <el-card shadow="never" class="config-card">
      <template #header>
        <div class="card-header">
          <span>外部同步基础开关</span>
          <el-tag type="success" effect="plain">保存后立即生效</el-tag>
        </div>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="同步后自动执行" prop="autoRunOnSync">
              <el-switch v-model="form.autoRunOnSync" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="同步后自动翻译" prop="autoTranslateOnSync">
              <el-switch v-model="form.autoTranslateOnSync" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="默认拉取数量" prop="defaultPullLimit">
              <el-input-number v-model="form.defaultPullLimit" :min="1" :max="200" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="远端来源系统" prop="remoteSync.sourceSystem">
              <el-input v-model="form.remoteSync.sourceSystem" placeholder="例如 public / hrm / partner" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>远端同步链接</span>
          <el-tag type="warning" effect="plain">这里只配置拉取地址，不会自动启动任务</el-tag>
        </div>
      </template>

      <el-form ref="remoteFormRef" :model="form.remoteSync" :rules="remoteRules" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="启用远端同步" prop="enabled">
              <el-switch v-model="form.remoteSync.enabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="抓取超时(秒)" prop="timeoutSec">
              <el-input-number v-model="form.remoteSync.timeoutSec" :min="10" :max="300" :step="5" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="拉取地址" prop="pullUrl">
              <el-input v-model="form.remoteSync.pullUrl" placeholder="https://example.com/api/tickets/pending" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="回写地址" prop="ackUrl">
              <el-input v-model="form.remoteSync.ackUrl" placeholder="https://example.com/api/tickets/ack" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="消费者标识" prop="consumer">
              <el-input v-model="form.remoteSync.consumer" placeholder="例如 public-ticket-sync" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="每次拉取数量" prop="limit">
              <el-input-number v-model="form.remoteSync.limit" :min="1" :max="200" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="包含已关闭" prop="includeClosed">
              <el-switch v-model="form.remoteSync.includeClosed" inline-prompt active-text="是" inactive-text="否" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="拉取后自动翻译" prop="autoTranslateOnPull">
              <el-switch v-model="form.remoteSync.autoTranslateOnPull" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>识别规则</span>
          <el-tag effect="plain">按文本匹配，找不到则保留原值</el-tag>
        </div>
      </template>

      <el-form ref="patternFormRef" :model="form" label-width="150px">
        <el-form-item label="POS 正则规则">
          <el-input v-model="posPatternsText" type="textarea" :rows="6" placeholder='请输入 JSON 数组，例如 ["A", "B"]' />
        </el-form-item>
        <el-form-item label="SCO 正则规则">
          <el-input v-model="scoPatternsText" type="textarea" :rows="6" placeholder='请输入 JSON 数组，例如 ["A", "B"]' />
        </el-form-item>
        <el-form-item label="版本号正则规则">
          <el-input v-model="versionPatternsText" type="textarea" :rows="6" placeholder='请输入 JSON 数组，例如 ["A", "B"]' />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>映射配置</span>
          <el-tag effect="plain">给三方直推和内网拉取共用</el-tag>
        </div>
      </template>

      <div class="mapping-blocks">
        <div v-for="item in mappingSections" :key="item.key" class="mapping-section">
          <div class="mapping-title">{{ item.label }}</div>
          <div class="mapping-desc">{{ item.description }}</div>
          <el-input
            v-model="mappingTexts[item.key]"
            type="textarea"
            :rows="item.rows"
            placeholder='请输入 JSON 数组，例如 [{"source":"A","target":"B"}]'
          />
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>拉日志默认值</span>
          <el-tag type="info" effect="plain">同步后自动拉日志可复用</el-tag>
        </div>
      </template>

      <el-form ref="pullFormRef" :model="form.logPullDefaults" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="命令类型">
              <el-input-number v-model="form.logPullDefaults.commandDataType" :min="1" :max="10" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="文件上限(MB)">
              <el-input-number v-model="form.logPullDefaults.fileMaxSize" :min="1" :max="2000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="压缩包上限(MB)">
              <el-input-number v-model="form.logPullDefaults.zipMaxSize" :min="1" :max="2000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="存储方式">
              <el-select v-model="form.logPullDefaults.storageMode" placeholder="请选择" style="width: 100%">
                <el-option label="本地" value="local" />
                <el-option label="FTP" value="ftp" />
                <el-option label="对象存储" value="oss" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="前置分钟数">
              <el-input-number v-model="form.logPullDefaults.rangeBeforeMinutes" :min="0" :max="120" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="后置分钟数">
              <el-input-number v-model="form.logPullDefaults.rangeAfterMinutes" :min="0" :max="120" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="自动 AI 分析">
              <el-switch v-model="form.logPullDefaults.autoAiEnabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="Agent 编码">
              <el-input v-model="form.logPullDefaults.aiAgentCode" placeholder="留空则走默认 Agent" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="Provider 编码">
              <el-input v-model="form.logPullDefaults.aiProviderCode" placeholder="留空则走默认 Provider" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>提示词模板</span>
          <el-tag effect="plain">后续扩展 AI 识别时复用</el-tag>
        </div>
      </template>

      <el-form label-width="150px">
        <el-form-item label="分类提示词">
          <el-input
            v-model="form.promptTemplates.classificationHint"
            type="textarea"
            :rows="10"
            placeholder="用于项目、模块、状态、处理人等识别场景"
          />
        </el-form-item>
      </el-form>
    </el-card>

    <div class="action-bar">
      <el-button type="primary" :loading="saving" @click="handleSave" v-hasPermi="['ticket:sync:config:edit']">保存配置</el-button>
      <el-button @click="loadConfig">刷新数据</el-button>
    </div>
  </div>
</template>

<script setup name="TicketSyncAutomation">
import { getTicketSyncAutomationConfig, saveTicketSyncAutomationConfig } from '@/api/ticket/ticket'

const { proxy } = getCurrentInstance()

const loading = ref(false)
const saving = ref(false)

const form = reactive(createDefaultForm())
const mappingTexts = reactive({
  projectMappings: '[]',
  moduleMappings: '[]',
  vendorMappings: '[]',
  storeMappings: '[]',
  statusMappings: '[]',
  assigneeMappings: '[]'
})
const posPatternsText = ref('[]')
const scoPatternsText = ref('[]')
const versionPatternsText = ref('[]')

const mappingSections = [
  { key: 'projectMappings', label: '项目映射', description: '示例：[{"keywords":["支付中心","pay-center"],"projectId":1001,"projectName":"支付平台"}]', rows: 6 },
  { key: 'moduleMappings', label: '模块映射', description: '示例：[{"keywords":["订单服务","order-service"],"moduleId":2001,"moduleName":"订单模块"}]', rows: 6 },
  { key: 'vendorMappings', label: '商家映射', description: '示例：[{"keywords":["京东","jd"],"vendorId":3001,"vendorName":"京东商户"}]', rows: 6 },
  { key: 'storeMappings', label: '门店映射', description: '示例：[{"keywords":["北京一店","bj-01"],"storeId":4001,"storeName":"北京一店"}]', rows: 6 },
  { key: 'statusMappings', label: '状态映射', description: '示例：[{"keywords":["处理中","processing"],"status":"PROCESSING"}]', rows: 6 },
  { key: 'assigneeMappings', label: '处理人映射', description: '示例：[{"keywords":["张三","zhangsan"],"userId":5001,"userName":"张三"}]', rows: 6 }
]

const rules = {
  defaultPullLimit: [{ required: true, message: '默认拉取数量不能为空', trigger: 'change' }]
}

const remoteRules = {
  pullUrl: [{ required: true, message: '拉取地址不能为空', trigger: 'blur' }],
  ackUrl: [{ required: true, message: '回写地址不能为空', trigger: 'blur' }],
  consumer: [{ required: true, message: '消费者标识不能为空', trigger: 'blur' }],
  limit: [{ required: true, message: '每次拉取数量不能为空', trigger: 'change' }],
  timeoutSec: [{ required: true, message: '抓取超时不能为空', trigger: 'change' }]
}

function createDefaultForm() {
  return {
    autoRunOnSync: false,
    autoTranslateOnSync: true,
    defaultPullLimit: 50,
    remoteSync: {
      enabled: false,
      pullUrl: '',
      ackUrl: '',
      consumer: '',
      sourceSystem: 'public',
      limit: 50,
      includeClosed: true,
      autoTranslateOnPull: true,
      timeoutSec: 30,
      headers: {
        cookie: '',
        authorization: '',
        origin: ''
      }
    },
    projectMappings: [],
    moduleMappings: [],
    vendorMappings: [],
    storeMappings: [],
    statusMappings: [],
    assigneeMappings: [],
    posPatterns: [],
    scoPatterns: [],
    versionPatterns: [],
    logPullDefaults: {
      commandDataType: 1,
      fileMaxSize: 500,
      zipMaxSize: 500,
      storageMode: 'local',
      rangeBeforeMinutes: 10,
      rangeAfterMinutes: 10,
      autoAiEnabled: false,
      aiAgentCode: '',
      aiProviderCode: ''
    },
    promptTemplates: {
      classificationHint: ''
    }
  }
}

function normalizeArray(value, fallback = []) {
  if (Array.isArray(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim()) {
    try {
      const parsed = JSON.parse(value)
      return Array.isArray(parsed) ? parsed : fallback
    } catch (error) {
      return fallback
    }
  }
  return fallback
}

function applyConfig(payload) {
  form.autoRunOnSync = Boolean(payload.autoRunOnSync)
  form.autoTranslateOnSync = payload.autoTranslateOnSync !== false
  form.defaultPullLimit = Number(payload.defaultPullLimit || 50)

  const remoteSync = payload.remoteSync || {}
  form.remoteSync = {
    enabled: Boolean(remoteSync.enabled),
    pullUrl: remoteSync.pullUrl || '',
    ackUrl: remoteSync.ackUrl || '',
    consumer: remoteSync.consumer || '',
    sourceSystem: remoteSync.sourceSystem || 'public',
    limit: Number(remoteSync.limit || 50),
    includeClosed: remoteSync.includeClosed !== false,
    autoTranslateOnPull: remoteSync.autoTranslateOnPull !== false,
    timeoutSec: Number(remoteSync.timeoutSec || 30),
    headers: {
      cookie: remoteSync.headers && remoteSync.headers.cookie ? remoteSync.headers.cookie : '',
      authorization: remoteSync.headers && remoteSync.headers.authorization ? remoteSync.headers.authorization : '',
      origin: remoteSync.headers && remoteSync.headers.origin ? remoteSync.headers.origin : ''
    }
  }

  form.projectMappings = normalizeArray(payload.projectMappings)
  form.moduleMappings = normalizeArray(payload.moduleMappings)
  form.vendorMappings = normalizeArray(payload.vendorMappings)
  form.storeMappings = normalizeArray(payload.storeMappings)
  form.statusMappings = normalizeArray(payload.statusMappings)
  form.assigneeMappings = normalizeArray(payload.assigneeMappings)
  form.posPatterns = normalizeArray(payload.posPatterns)
  form.scoPatterns = normalizeArray(payload.scoPatterns)
  form.versionPatterns = normalizeArray(payload.versionPatterns)

  mappingSections.forEach(item => {
    mappingTexts[item.key] = JSON.stringify(form[item.key], null, 2)
  })
  posPatternsText.value = JSON.stringify(form.posPatterns, null, 2)
  scoPatternsText.value = JSON.stringify(form.scoPatterns, null, 2)
  versionPatternsText.value = JSON.stringify(form.versionPatterns, null, 2)

  const logPullDefaults = payload.logPullDefaults || {}
  form.logPullDefaults = {
    commandDataType: Number(logPullDefaults.commandDataType || 1),
    fileMaxSize: Number(logPullDefaults.fileMaxSize || 500),
    zipMaxSize: Number(logPullDefaults.zipMaxSize || 500),
    storageMode: logPullDefaults.storageMode || 'local',
    rangeBeforeMinutes: Number(logPullDefaults.rangeBeforeMinutes || 10),
    rangeAfterMinutes: Number(logPullDefaults.rangeAfterMinutes || 10),
    autoAiEnabled: Boolean(logPullDefaults.autoAiEnabled),
    aiAgentCode: logPullDefaults.aiAgentCode || '',
    aiProviderCode: logPullDefaults.aiProviderCode || ''
  }

  form.promptTemplates = {
    classificationHint: payload.promptTemplates?.classificationHint || ''
  }
}

function parseJsonArray(text, fallback = []) {
  if (!String(text || '').trim()) {
    return fallback
  }
  try {
    const parsed = JSON.parse(text)
    return Array.isArray(parsed) ? parsed : fallback
  } catch (error) {
    throw new Error('请检查 JSON 数组格式是否正确')
  }
}

function loadConfig() {
  loading.value = true
  getTicketSyncAutomationConfig()
    .then(response => {
      applyConfig(response.data?.configValue || response.data || {})
    })
    .finally(() => {
      loading.value = false
    })
}

function validateElForm(refName) {
  return new Promise(resolve => {
    const formRef = proxy.$refs[refName]
    if (!formRef || typeof formRef.validate !== 'function') {
      resolve(true)
      return
    }
    formRef.validate(valid => resolve(valid))
  })
}

async function handleSave() {
  const [basicValid, remoteValid] = await Promise.all([
    validateElForm('formRef'),
    validateElForm('remoteFormRef')
  ])
  if (!basicValid || !remoteValid) {
    return
  }

  saving.value = true
  try {
    const payload = JSON.parse(JSON.stringify(form))
    mappingSections.forEach(item => {
      payload[item.key] = parseJsonArray(mappingTexts[item.key])
    })
    payload.posPatterns = parseJsonArray(posPatternsText.value)
    payload.scoPatterns = parseJsonArray(scoPatternsText.value)
    payload.versionPatterns = parseJsonArray(versionPatternsText.value)
    await saveTicketSyncAutomationConfig(payload)
    proxy.$modal.msgSuccess('保存成功')
    loadConfig()
  } catch (error) {
    proxy.$modal.msgError(error?.message || '保存失败，请检查配置内容')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.ticket-sync-automation-page {
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.96), rgba(255, 255, 255, 1));
  padding-bottom: 96px;
  display: block;
  width: 100%;
  align-self: stretch;
  box-sizing: border-box;
}

.ticket-sync-automation-page :deep(.el-form),
.ticket-sync-automation-page :deep(.el-row),
.ticket-sync-automation-page :deep(.el-col),
.ticket-sync-automation-page :deep(.el-card),
.ticket-sync-automation-page :deep(.el-card__body) {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.ticket-sync-automation-page :deep(.el-form-item) {
  width: 100%;
  margin-bottom: 18px;
}

.ticket-sync-automation-page :deep(.el-form-item__content) {
  min-width: 0;
  width: 100%;
}

.ticket-sync-automation-page :deep(.el-input),
.ticket-sync-automation-page :deep(.el-select),
.ticket-sync-automation-page :deep(.el-input-number),
.ticket-sync-automation-page :deep(.el-date-editor),
.ticket-sync-automation-page :deep(.el-textarea) {
  width: 100%;
}

.page-intro {
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(241, 245, 249, 0.92));
  padding: 18px 20px;
  margin-bottom: 16px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
}

.page-intro__eyebrow {
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--el-color-primary);
  margin-bottom: 8px;
  font-weight: 700;
}

.page-intro__title {
  margin: 0;
  font-size: 22px;
  line-height: 1.35;
  color: var(--el-text-color-primary);
}

.page-intro__desc {
  margin: 10px 0 0;
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-secondary);
  max-width: 100%;
}

.config-card {
  border-radius: 12px;
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-weight: 600;
}

.mapping-blocks {
  display: grid;
  gap: 12px;
}

.mapping-section {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  padding: 14px;
  background: #fff;
}

.mapping-title {
  font-weight: 600;
  margin-bottom: 6px;
}

.mapping-desc {
  color: var(--el-text-color-secondary);
  margin-bottom: 10px;
  line-height: 1.5;
}

.action-bar {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 16px;
  position: sticky;
  bottom: 0;
  z-index: 20;
  padding: 14px 0 4px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0.96));
  backdrop-filter: blur(8px);
}

.mt16 {
  margin-top: 16px;
}
</style>
