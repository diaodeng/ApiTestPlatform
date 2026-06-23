<template>
  <div class="app-container ai-config-center-page" v-loading="loading">
    <section class="page-intro">
      <div class="page-intro__eyebrow">AI 配置中心</div>
      <h2 class="page-intro__title">集中管理工单 AI 相关配置</h2>
      <p class="page-intro__desc">
        轻量翻译、标题总结、工单分类、日志参数提取与知识提炼在工单链路中触发。Provider 和提示词正文统一维护，这里只负责选择和组合。
      </p>
    </section>

    <el-card class="config-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>轻量 AI 配置</span>
          <el-tag type="success" effect="plain">保存即生效</el-tag>
        </div>
      </template>

        <el-form ref="formRef" :model="form" :rules="rules" label-width="170px">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-divider content-position="left">工单翻译</el-divider>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="翻译总开关" prop="translateEnabled">
              <el-switch v-model="form.translateEnabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="翻译 Provider" prop="translateProviderCode">
              <el-select
                v-model="form.translateProviderCode"
                placeholder="请选择 Provider"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="item in providerOptions"
                  :key="item.providerId || item.providerCode"
                  :label="formatProviderLabel(item)"
                  :value="item.providerCode"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="翻译提示词" prop="translatePromptCode">
              <el-select
                v-model="form.translatePromptCode"
                placeholder="请选择提示词模板"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="item in promptOptions.translate"
                  :key="item.templateId || item.templateCode"
                  :label="formatPromptLabel(item)"
                  :value="item.templateCode"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="标题总结开关" prop="titleSummaryEnabled">
              <el-switch v-model="form.titleSummaryEnabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="标题总结 Provider" prop="titleSummaryProviderCode">
              <el-select
                v-model="form.titleSummaryProviderCode"
                placeholder="请选择 Provider"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="item in providerOptions"
                  :key="`title-summary-${item.providerId || item.providerCode}`"
                  :label="formatProviderLabel(item)"
                  :value="item.providerCode"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="标题总结提示词" prop="titleSummaryPromptCode">
              <el-select
                v-model="form.titleSummaryPromptCode"
                placeholder="请选择提示词模板"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="item in promptOptions.translate"
                  :key="`title-summary-${item.templateId || item.templateCode}`"
                  :label="formatPromptLabel(item)"
                  :value="item.templateCode"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="分类统计开关" prop="categoryClassifyEnabled">
              <el-switch v-model="form.categoryClassifyEnabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="分类统计 Provider" prop="categoryClassifyProviderCode">
              <el-select
                v-model="form.categoryClassifyProviderCode"
                placeholder="请选择 Provider"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="item in providerOptions"
                  :key="`category-${item.providerId || item.providerCode}`"
                  :label="formatProviderLabel(item)"
                  :value="item.providerCode"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="分类统计提示词" prop="categoryClassifyPromptCode">
              <el-select
                v-model="form.categoryClassifyPromptCode"
                placeholder="请选择提示词模板"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="item in promptOptions.common"
                  :key="`category-${item.templateId || item.templateCode}`"
                  :label="formatPromptLabel(item)"
                  :value="item.templateCode"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="日志参数提取开关" prop="logExtractEnabled">
              <el-switch v-model="form.logExtractEnabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="日志参数提取 Provider" prop="logExtractProviderCode">
              <el-select
                v-model="form.logExtractProviderCode"
                placeholder="请选择 Provider"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="item in providerOptions"
                  :key="`log-extract-${item.providerId || item.providerCode}`"
                  :label="formatProviderLabel(item)"
                  :value="item.providerCode"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="日志参数提取提示词" prop="logExtractPromptCode">
              <el-select
                v-model="form.logExtractPromptCode"
                placeholder="请选择提示词模板"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="item in promptOptions.common"
                  :key="`log-extract-${item.templateId || item.templateCode}`"
                  :label="formatPromptLabel(item)"
                  :value="item.templateCode"
                />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :span="24">
            <el-divider content-position="left">知识提炼</el-divider>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="知识提炼 Provider" prop="knowledgeProviderCode">
              <el-select
                v-model="form.knowledgeProviderCode"
                placeholder="请选择 Provider"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="item in providerOptions"
                  :key="`knowledge-${item.providerId || item.providerCode}`"
                  :label="formatProviderLabel(item)"
                  :value="item.providerCode"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="知识提炼提示词" prop="knowledgePromptCode">
              <el-select
                v-model="form.knowledgePromptCode"
                placeholder="请选择提示词模板"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="item in promptOptions.knowledge"
                  :key="`knowledge-${item.templateId || item.templateCode}`"
                  :label="formatPromptLabel(item)"
                  :value="item.templateCode"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card class="config-card mt16" shadow="never">
      <template #header>
        <div class="card-header">
          <span>AI 分析 Worker 配置</span>
          <el-tag type="warning" effect="plain">工单版本分析任务</el-tag>
        </div>
      </template>

      <el-form ref="workerFormRef" :model="form" :rules="rules" label-width="170px">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item label="Worker 命令" prop="analysisWorkerCommand">
              <el-input v-model="form.analysisWorkerCommand" placeholder="例如 codex exec" clearable />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="Worker 模型" prop="analysisWorkerModel">
              <el-input v-model="form.analysisWorkerModel" placeholder="例如 gpt-4.1-mini" clearable />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="Worker 沙箱" prop="analysisWorkerSandbox">
              <el-input v-model="form.analysisWorkerSandbox" placeholder="例如 workspace-write" clearable />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="超时秒数" prop="analysisWorkerTimeoutSec">
              <el-input-number v-model="form.analysisWorkerTimeoutSec" :min="60" :step="60" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="Agent 编码" prop="analysisAgentCode">
              <el-input v-model="form.analysisAgentCode" placeholder="留空则自动选择在线 Agent" clearable />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="日志分析模式" prop="analysisLogMode">
              <el-select v-model="form.analysisLogMode" placeholder="请选择日志分析模式">
                <el-option label="生成摘要" value="digest" />
                <el-option label="完整目录" value="full_directory" />
                <el-option label="摘要 + 完整目录" value="hybrid" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="窗口缺失策略" prop="analysisLogWindowMissingStrategy">
              <el-select v-model="form.analysisLogWindowMissingStrategy" placeholder="请选择窗口缺失策略">
                <el-option label="Agent 本地截取" value="agent_extract" />
                <el-option label="服务端实时截取" value="server_extract" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="工作区根目录" prop="analysisWorkspaceRoot">
              <el-input v-model="form.analysisWorkspaceRoot" placeholder="例如 D:/xj/api-test-platform/logs/ticket_ai_analysis" clearable />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-row :gutter="16" class="mt16">
      <el-col :xs="24" :lg="12">
        <el-card class="config-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>快捷入口</span>
              <el-tag effect="plain">跳转管理页</el-tag>
            </div>
          </template>

          <div class="quick-links">
            <div v-for="item in quickLinks" :key="item.path" class="quick-link-item">
              <div class="quick-link-title">{{ item.label }}</div>
              <div class="quick-link-desc">{{ item.description }}</div>
              <el-button type="primary" plain size="small" @click="goToPath(item.path)">打开</el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="12">
        <el-card class="config-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>配置清单</span>
              <el-tag effect="plain">当前值 / 默认值</el-tag>
            </div>
          </template>

          <el-table :data="configRows" border size="small" style="width: 100%">
            <el-table-column label="配置项" prop="configName" min-width="160" show-overflow-tooltip />
            <el-table-column label="键名" prop="configKey" min-width="200" show-overflow-tooltip />
            <el-table-column label="当前值" prop="currentValue" min-width="180" show-overflow-tooltip />
            <el-table-column label="默认值" prop="defaultValue" min-width="180" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <div class="action-bar">
      <el-button type="primary" :loading="saving" @click="handleSave" v-hasPermi="['system:aiconfig:edit']">保存配置</el-button>
      <el-button @click="loadSummary">刷新数据</el-button>
    </div>
  </div>
</template>

<script setup name="AiConfigCenter">
import { getAiConfigSummary, updateAiConfig } from '@/api/system/aiconfig'

const { proxy } = getCurrentInstance()

const loading = ref(false)
const saving = ref(false)
const configRows = ref([])
const providerOptions = ref([])
const quickLinks = ref([])
const promptOptions = reactive({
  translate: [],
  knowledge: [],
  analysis: [],
  common: []
})

const defaultForm = () => ({
  translateEnabled: true,
  translateProviderCode: '',
  translatePromptCode: '',
  titleSummaryEnabled: false,
  titleSummaryProviderCode: '',
  titleSummaryPromptCode: '',
  categoryClassifyEnabled: false,
  categoryClassifyProviderCode: '',
  categoryClassifyPromptCode: '',
  logExtractEnabled: false,
  logExtractProviderCode: '',
  logExtractPromptCode: '',
  knowledgeProviderCode: '',
  knowledgePromptCode: '',
  analysisWorkerCommand: '',
  analysisWorkerModel: '',
  analysisWorkerSandbox: '',
  analysisWorkerTimeoutSec: 3600,
  analysisWorkspaceRoot: '',
  analysisAgentCode: '',
  analysisLogMode: 'digest',
  analysisLogWindowMissingStrategy: 'agent_extract'
})

const form = reactive(defaultForm())

const rules = {
  analysisWorkerTimeoutSec: [{ required: true, message: '超时秒数不能为空', trigger: 'change' }]
}

function normalizePayload(payload) {
  return payload || {}
}

function formatProviderLabel(item) {
  const code = item.providerCode || item.provider_code || '-'
  const name = item.providerName || item.provider_name || code
  const model = item.modelName || item.model_name || '-'
  return `${name} / ${code} / ${model}`
}

function formatPromptLabel(item) {
  const code = item.templateCode || item.template_code || '-'
  const name = item.templateName || item.template_name || code
  const category = item.templateCategory || item.template_category || '-'
  return `${name} / ${code} / ${category}`
}

function applyFormData(payload) {
  form.translateEnabled = payload.translateEnabled ?? payload.translate_enabled ?? true
  form.translateProviderCode = payload.translateProviderCode ?? payload.translate_provider_code ?? ''
  form.translatePromptCode = payload.translatePromptCode ?? payload.translate_prompt_code ?? ''
  form.titleSummaryEnabled = payload.titleSummaryEnabled ?? payload.title_summary_enabled ?? false
  form.titleSummaryProviderCode = payload.titleSummaryProviderCode ?? payload.title_summary_provider_code ?? ''
  form.titleSummaryPromptCode = payload.titleSummaryPromptCode ?? payload.title_summary_prompt_code ?? ''
  form.categoryClassifyEnabled = payload.categoryClassifyEnabled ?? payload.category_classify_enabled ?? false
  form.categoryClassifyProviderCode = payload.categoryClassifyProviderCode ?? payload.category_classify_provider_code ?? ''
  const classifyPromptCode = payload.categoryClassifyPromptCode ?? payload.category_classify_prompt_code ?? ''
  form.categoryClassifyPromptCode = classifyPromptCode === 'ticket_category_classify_default'
    ? 'ticket_stat_classify_default'
    : classifyPromptCode
  form.logExtractEnabled = payload.logExtractEnabled ?? payload.log_extract_enabled ?? false
  form.logExtractProviderCode = payload.logExtractProviderCode ?? payload.log_extract_provider_code ?? ''
  form.logExtractPromptCode = payload.logExtractPromptCode ?? payload.log_extract_prompt_code ?? ''
  form.knowledgeProviderCode = payload.knowledgeProviderCode ?? payload.knowledge_provider_code ?? ''
  form.knowledgePromptCode = payload.knowledgePromptCode ?? payload.knowledge_prompt_code ?? ''
  form.analysisWorkerCommand = payload.analysisWorkerCommand ?? payload.analysis_worker_command ?? ''
  form.analysisWorkerModel = payload.analysisWorkerModel ?? payload.analysis_worker_model ?? ''
  form.analysisWorkerSandbox = payload.analysisWorkerSandbox ?? payload.analysis_worker_sandbox ?? ''
  const timeoutValue = payload.analysisWorkerTimeoutSec ?? payload.analysis_worker_timeout_sec ?? 3600
  form.analysisWorkerTimeoutSec = Number(timeoutValue) || 3600
  form.analysisWorkspaceRoot = payload.analysisWorkspaceRoot ?? payload.analysis_workspace_root ?? ''
  form.analysisAgentCode = payload.analysisAgentCode ?? payload.analysis_agent_code ?? ''
  form.analysisLogMode = payload.analysisLogMode ?? payload.analysis_log_mode ?? 'digest'
  form.analysisLogWindowMissingStrategy = payload.analysisLogWindowMissingStrategy
    ?? payload.analysis_log_window_missing_strategy
    ?? 'agent_extract'

  configRows.value = payload.configRows ?? payload.config_rows ?? []
  providerOptions.value = payload.providerOptions ?? payload.provider_options ?? []
  quickLinks.value = payload.quickLinks ?? payload.quick_links ?? []

  const options = payload.promptOptions ?? payload.prompt_options ?? {}
  promptOptions.translate = options.translate || []
  promptOptions.knowledge = options.knowledge || []
  promptOptions.analysis = options.analysis || []
  promptOptions.common = options.common || []
}

function loadSummary() {
  loading.value = true
  getAiConfigSummary()
    .then(response => {
      applyFormData(normalizePayload(response.data))
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
    formRef.validate(valid => {
      resolve(valid)
    })
  })
}

function goToPath(path) {
  if (!path) {
    return
  }
  proxy.$router.push(path)
}

async function handleSave() {
  const [basicValid, workerValid] = await Promise.all([
    validateElForm('formRef'),
    validateElForm('workerFormRef')
  ])
  if (!basicValid || !workerValid) {
    return
  }
  saving.value = true
  const payload = { ...form }
  if (!payload.categoryClassifyPromptCode || payload.categoryClassifyPromptCode === 'ticket_category_classify_default') {
    payload.categoryClassifyPromptCode = 'ticket_stat_classify_default'
  }
  updateAiConfig(payload)
    .then(() => {
      proxy.$modal.msgSuccess('保存成功')
      loadSummary()
    })
    .finally(() => {
      saving.value = false
    })
}

onMounted(() => {
  loadSummary()
})
</script>

<style scoped>
.ai-config-center-page {
  background: linear-gradient(180deg, rgba(245, 247, 250, 0.96), rgba(255, 255, 255, 1));
  display: block;
  width: 100%;
  align-self: stretch;
  box-sizing: border-box;
}

.ai-config-center-page :deep(.el-form),
.ai-config-center-page :deep(.el-row),
.ai-config-center-page :deep(.el-col),
.ai-config-center-page :deep(.el-card),
.ai-config-center-page :deep(.el-card__body) {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.ai-config-center-page :deep(.el-form-item) {
  width: 100%;
  margin-bottom: 18px;
}

.ai-config-center-page :deep(.el-form-item__content) {
  min-width: 0;
  width: 100%;
}

.ai-config-center-page :deep(.el-input),
.ai-config-center-page :deep(.el-select),
.ai-config-center-page :deep(.el-input-number),
.ai-config-center-page :deep(.el-date-editor),
.ai-config-center-page :deep(.el-textarea) {
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
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 600;
}

.action-bar {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 16px;
}

.quick-links {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.quick-link-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  padding: 14px 16px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.92), rgba(255, 255, 255, 1));
}

.quick-link-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.quick-link-desc {
  margin: 8px 0 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.mt16 {
  margin-top: 16px;
}
</style>
