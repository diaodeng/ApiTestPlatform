<template>
  <div class="app-container ai-config-center-page" v-loading="loading">
    <el-alert
      title="这里集中管理工单 AI 相关配置"
      type="info"
      show-icon
      :closable="false"
      class="mb16"
    >
      <template #default>
        轻量翻译与知识提炼在工单保存/关闭时触发，AI 分析 Worker 配置用于版本仓库分析任务。保存后会自动刷新系统缓存。
      </template>
    </el-alert>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
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
              <el-col :span="12">
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
              <el-col :span="12">
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

              <el-col :span="24">
                <el-divider content-position="left">知识提炼</el-divider>
              </el-col>
              <el-col :span="12">
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
              <el-col :span="12">
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
              <el-col :span="12">
                <el-form-item label="Worker 模型" prop="analysisWorkerModel">
                  <el-input v-model="form.analysisWorkerModel" placeholder="例如 gpt-4.1-mini" clearable />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Worker 沙箱" prop="analysisWorkerSandbox">
                  <el-input v-model="form.analysisWorkerSandbox" placeholder="例如 workspace-write" clearable />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="超时秒数" prop="analysisWorkerTimeoutSec">
                  <el-input-number v-model="form.analysisWorkerTimeoutSec" :min="60" :step="60" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Agent 编码" prop="analysisAgentCode">
                  <el-input v-model="form.analysisAgentCode" placeholder="留空则自动选择在线 Agent" clearable />
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

        <div class="action-bar">
          <el-button type="primary" :loading="saving" @click="handleSave" v-hasPermi="['system:aiconfig:edit']">保存配置</el-button>
          <el-button @click="loadSummary">刷新数据</el-button>
        </div>
      </el-col>

      <el-col :xs="24" :lg="10">
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

        <el-card class="config-card mt16" shadow="never">
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
  common: [],
})

const defaultForm = () => ({
  translateProviderCode: '',
  translatePromptCode: '',
  knowledgeProviderCode: '',
  knowledgePromptCode: '',
  analysisWorkerCommand: '',
  analysisWorkerModel: '',
  analysisWorkerSandbox: '',
  analysisWorkerTimeoutSec: 3600,
  analysisWorkspaceRoot: '',
  analysisAgentCode: '',
})

const form = reactive(defaultForm())

const rules = {
  analysisWorkerTimeoutSec: [{ required: true, message: '超时秒数不能为空', trigger: 'change' }],
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
  form.translateProviderCode = payload.translateProviderCode ?? payload.translate_provider_code ?? ''
  form.translatePromptCode = payload.translatePromptCode ?? payload.translate_prompt_code ?? ''
  form.knowledgeProviderCode = payload.knowledgeProviderCode ?? payload.knowledge_provider_code ?? ''
  form.knowledgePromptCode = payload.knowledgePromptCode ?? payload.knowledge_prompt_code ?? ''
  form.analysisWorkerCommand = payload.analysisWorkerCommand ?? payload.analysis_worker_command ?? ''
  form.analysisWorkerModel = payload.analysisWorkerModel ?? payload.analysis_worker_model ?? ''
  form.analysisWorkerSandbox = payload.analysisWorkerSandbox ?? payload.analysis_worker_sandbox ?? ''
  const timeoutValue = payload.analysisWorkerTimeoutSec ?? payload.analysis_worker_timeout_sec ?? 3600
  form.analysisWorkerTimeoutSec = Number(timeoutValue) || 3600
  form.analysisWorkspaceRoot = payload.analysisWorkspaceRoot ?? payload.analysis_workspace_root ?? ''
  form.analysisAgentCode = payload.analysisAgentCode ?? payload.analysis_agent_code ?? ''

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
    validateElForm('workerFormRef'),
  ])
  if (!basicValid || !workerValid) {
    return
  }
  saving.value = true
  updateAiConfig({ ...form })
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
}

.config-card {
  border-radius: 12px;
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
