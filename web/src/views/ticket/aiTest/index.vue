<template>
  <div class="app-container ticket-ai-test-page">
    <el-card shadow="never" class="test-card">
      <template #header>
        <div class="card-header">
          <span>轻量AI测试工作台</span>
          <span class="header-tip">试运行信息提取、分类统计、翻译、标题总结和知识提炼；不回写工单数据，审计任务类型带 _test 后缀</span>
        </div>
      </template>

      <el-form :model="form" label-width="110px" v-loading="loading">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="任务类型" required>
              <el-select v-model="form.taskType" placeholder="请选择任务类型" style="width: 100%" @change="handleTaskTypeChange">
                <el-option v-for="item in options.taskTypes" :key="item.value" :label="item.label" :value="item.value">
                  <span>{{ item.label }}</span>
                  <span class="option-desc">{{ item.description }}</span>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="工单" required>
              <el-select
                v-model="form.ticketNo"
                placeholder="输入工单号或标题关键字搜索"
                filterable
                remote
                :remote-method="searchTickets"
                :loading="ticketSearching"
                style="width: 100%"
                @change="handleTicketChange"
              >
                <el-option
                  v-for="item in ticketOptions"
                  :key="item.ticketNo"
                  :label="`${item.ticketNo} ${item.title.slice(0, 30)}`"
                  :value="item.ticketNo"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="Provider" required>
              <el-select
                v-model="form.providerCode"
                placeholder="请选择 Provider"
                filterable
                style="width: 100%"
                @change="handleProviderChange"
              >
                <el-option
                  v-for="item in options.providers"
                  :key="item.providerCode"
                  :label="formatProviderLabel(item)"
                  :value="item.providerCode"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="模型">
              <el-select
                v-model="form.modelName"
                placeholder="留空使用 Provider 默认模型"
                filterable
                clearable
                style="width: 100%"
                :disabled="!form.providerCode"
              >
                <el-option
                  v-for="item in providerModels"
                  :key="item.modelId"
                  :label="item.displayName || item.modelId"
                  :value="item.modelId"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="提示词模板">
              <el-select v-model="form.promptCode" placeholder="按任务类型自动匹配" filterable style="width: 100%" @change="handlePromptChange">
                <el-option
                  v-for="item in filteredPromptTemplates"
                  :key="item.templateCode"
                  :label="`${item.templateName} [${item.templateCode}]${item.isDefault ? ' 默认' : ''}`"
                  :value="item.templateCode"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="form.taskType === 'sync_extract'" :span="8">
            <el-form-item label="提取输入">
              <el-radio-group v-model="form.useTicketDescriptionOnly">
                <el-radio :value="false">含原始入参</el-radio>
                <el-radio :value="true">仅标题+描述</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="提示词">
          <div class="prompt-editor-wrapper">
            <el-input
              v-model="form.promptOverride"
              type="textarea"
              :rows="12"
              placeholder="选择提示词模板后自动回填，可在此临时编辑；留空时使用模板原文。编辑内容仅本次测试生效，不会保存到模板。"
            />
            <div class="prompt-editor-toolbar">
              <el-button size="small" :disabled="!form.promptCode" @click="fillPromptTemplate">回填模板原文</el-button>
              <el-button size="small" :disabled="!form.promptOverride" @click="form.promptOverride = ''">清空编辑（用模板原文）</el-button>
              <span class="prompt-source-tip">{{ promptSourceTip }}</span>
            </div>
          </div>
        </el-form-item>

        <el-form-item v-if="ticketContext.title || ticketContext.description" label="工单内容">
          <el-collapse class="context-collapse">
            <el-collapse-item :title="`标题与描述（标题 ${ticketContext.title.length} 字 / 描述 ${ticketContext.description.length} 字）`">
              <div class="context-block">
                <div class="context-label">工单标题</div>
                <div class="context-text">{{ ticketContext.title || '-' }}</div>
                <div class="context-label">工单描述</div>
                <pre class="context-pre">{{ ticketContext.description || '-' }}</pre>
                <div v-if="ticketContext.rawPayload" class="context-label">原始入参（信息提取测试将随请求发送）</div>
                <pre v-if="ticketContext.rawPayload" class="context-pre">{{ formatJson(ticketContext.rawPayload) }}</pre>
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="running" :disabled="!canRun" @click="handleRun">
            {{ running ? '执行中…' : '执行测试' }}
          </el-button>
          <span v-if="result" class="run-meta">
            耗时 {{ result.elapsedMs }}ms
            <template v-if="tokenSummary"> · Token {{ tokenSummary }}</template>
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="result" shadow="never" class="test-card">
      <template #header>
        <div class="card-header">
          <span>测试结果</span>
          <el-tag :type="result.success ? 'success' : 'danger'" size="small">
            {{ result.success ? '成功' : '失败' }}
          </el-tag>
          <span class="header-tip">{{ result.providerCode }} / {{ result.modelName }} · 提示词：{{ promptSourceText(result) }}</span>
        </div>
      </template>

      <el-alert v-if="!result.success" :title="`执行失败：${result.errorMessage}`" type="error" :closable="false" show-icon class="result-alert" />
      <el-alert
        v-for="(warning, index) in allWarnings"
        :key="`w-${index}`"
        :title="warning"
        type="warning"
        :closable="false"
        show-icon
        class="result-alert"
      />

      <el-tabs>
        <el-tab-pane label="归一化结果" v-if="hasNormalized">
          <pre class="result-pre">{{ formatJson(result.normalized) }}</pre>
        </el-tab-pane>
        <el-tab-pane label="解析 JSON" v-if="result.parsed && Object.keys(result.parsed).length">
          <pre class="result-pre">{{ formatJson(result.parsed) }}</pre>
        </el-tab-pane>
        <el-tab-pane label="模型原始输出" v-if="result.rawText">
          <pre class="result-pre">{{ result.rawText }}</pre>
        </el-tab-pane>
        <el-tab-pane label="实际请求提示词">
          <div class="context-block">
            <div class="context-label">系统提示词</div>
            <pre class="context-pre">{{ result.systemPrompt || '-' }}</pre>
            <div class="context-label">用户提示词</div>
            <pre class="context-pre">{{ result.userPrompt || '-' }}</pre>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup name="TicketAiTest">
import { computed, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import {
  getTicketAiTestOptions,
  getTicketAiTestContext,
  getTicketAiTestPromptContent,
  runTicketAiTest,
  searchTicketAiTestTickets,
} from '@/api/ticket/aiTest';

// 任务类型默认提示词映射，与后端 TASK_DEFAULT_PROMPT_CODES 保持一致
const TASK_DEFAULT_PROMPTS = {
  sync_extract: 'ticket_sync_extract_default',
  classification: 'ticket_stat_classify_default',
  translate: 'ticket_translate_default',
  title_summary: 'ticket_title_summary_default',
  knowledge: 'ticket_knowledge_extract_default',
};

const loading = ref(false);
const running = ref(false);
const ticketSearching = ref(false);
const ticketOptions = ref([]);
const options = reactive({ taskTypes: [], providers: [], providerModels: {}, promptTemplates: [] });
const ticketContext = reactive({ title: '', description: '', rawPayload: null });
const result = ref(null);

const form = reactive({
  taskType: 'sync_extract',
  ticketNo: '',
  providerCode: '',
  modelName: '',
  promptCode: '',
  promptOverride: '',
  useTicketDescriptionOnly: false,
});

const canRun = computed(() => form.taskType && form.ticketNo && form.providerCode);
const providerModels = computed(() => options.providerModels[form.providerCode] || []);
const filteredPromptTemplates = computed(() => {
  // 默认只展示与当前任务类型相关的模板；无匹配时展示全部
  const matched = options.promptTemplates.filter((item) => (item.taskTypes || []).includes(form.taskType));
  return matched.length ? matched : options.promptTemplates;
});
const hasNormalized = computed(() => result.value && result.value.normalized && Object.keys(result.value.normalized).length);
const allWarnings = computed(() => {
  if (!result.value) return [];
  return [...(result.value.machineNumberWarnings || []), ...(result.value.warnings || [])];
});
const tokenSummary = computed(() => {
  if (!result.value || !result.value.tokenUsage) return '';
  const usage = result.value.tokenUsage;
  const parts = [];
  if (usage.input_tokens != null) parts.push(`输入 ${usage.input_tokens}`);
  if (usage.output_tokens != null) parts.push(`输出 ${usage.output_tokens}`);
  if (usage.total_tokens != null) parts.push(`总计 ${usage.total_tokens}`);
  return parts.join(' / ');
});
const promptSourceTip = computed(() => {
  if (!form.promptOverride || !form.promptOverride.trim()) return '当前将使用模板原文';
  return '当前将使用临时编辑内容（仅本次测试生效）';
});

function formatProviderLabel(item) {
  const code = item.providerCode || '';
  const name = item.providerName || code || '-';
  const modelName = item.defaultModel || '';
  return `${name}${code && name !== code ? ` [${code}]` : ''}${modelName ? ` - ${modelName}` : ''}`;
}

function promptSourceText(runResult) {
  if (!runResult) return '';
  const code = runResult.promptCode || '-';
  return runResult.promptSource === 'override' ? `${code}（临时编辑）` : `${code}（模板原文）`;
}

function formatJson(value) {
  return JSON.stringify(value, null, 2);
}

async function loadOptions() {
  loading.value = true;
  try {
    const res = await getTicketAiTestOptions();
    const data = res.data || {};
    options.taskTypes = data.taskTypes || [];
    options.providers = data.providers || [];
    options.providerModels = data.providerModels || {};
    options.promptTemplates = data.promptTemplates || [];
  } catch (e) {
    console.error('加载测试选项失败', e);
  } finally {
    loading.value = false;
  }
}

async function searchTickets(keyword) {
  const normalized = String(keyword || '').trim();
  if (!normalized) {
    ticketOptions.value = [];
    return;
  }
  ticketSearching.value = true;
  try {
    const res = await searchTicketAiTestTickets(normalized);
    ticketOptions.value = (res.data && res.data.rows) || [];
  } catch (e) {
    console.error('搜索工单失败', e);
  } finally {
    ticketSearching.value = false;
  }
}

async function handleTicketChange(ticketNo) {
  result.value = null;
  ticketContext.title = '';
  ticketContext.description = '';
  ticketContext.rawPayload = null;
  if (!ticketNo) return;
  loading.value = true;
  try {
    const res = await getTicketAiTestContext(ticketNo);
    const data = res.data || {};
    ticketContext.title = data.title || '';
    ticketContext.description = data.description || '';
    ticketContext.rawPayload = data.rawPayload || null;
  } catch (e) {
    console.error('加载工单上下文失败', e);
    ElMessage.error('加载工单上下文失败');
  } finally {
    loading.value = false;
  }
}

function handleTaskTypeChange() {
  // 切换任务类型时重置为该类型默认提示词
  form.promptCode = TASK_DEFAULT_PROMPTS[form.taskType] || '';
  fillPromptTemplate();
}

function handleProviderChange() {
  form.modelName = '';
}

function fillPromptTemplate() {
  if (!form.promptCode) return;
  const template = options.promptTemplates.find((item) => item.templateCode === form.promptCode);
  if (!template) {
    ElMessage.warning('未找到模板内容，请刷新选项');
    return;
  }
  loadTemplateContent(form.promptCode);
}

async function loadTemplateContent(templateCode) {
  loading.value = true;
  try {
    const res = await getTicketAiTestPromptContent(templateCode);
    form.promptOverride = (res.data && res.data.promptContent) || '';
  } catch (e) {
    console.error('回填提示词模板失败', e);
    ElMessage.error('回填提示词模板失败');
  } finally {
    loading.value = false;
  }
}

async function handlePromptChange() {
  if (!form.promptCode) {
    form.promptOverride = '';
    return;
  }
  await fillPromptTemplate();
}

async function handleRun() {
  if (!canRun.value) {
    ElMessage.warning('请先选择任务类型、工单和 Provider');
    return;
  }
  running.value = true;
  result.value = null;
  try {
    const res = await runTicketAiTest({
      taskType: form.taskType,
      ticketNo: form.ticketNo,
      providerCode: form.providerCode,
      modelName: form.modelName || '',
      promptCode: form.promptCode || '',
      promptOverride: form.promptOverride || '',
      useTicketDescriptionOnly: form.useTicketDescriptionOnly,
    });
    result.value = res.data || { success: false, errorMessage: '空响应' };
  } catch (e) {
    console.error('执行测试失败', e);
    ElMessage.error(e.msg || '执行测试失败');
  } finally {
    running.value = false;
  }
}

loadOptions();
</script>

<style scoped>
/* 对齐项目其他长页面：覆盖全局 .app-container 的 flex 列布局，
   让内容按文档流自然撑开，超出部分由 app-main 滚动。 */
.ticket-ai-test-page {
  display: block;
  width: 100%;
  align-self: stretch;
  box-sizing: border-box;
}

.test-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-tip {
  font-size: 12px;
  color: #909399;
}
.option-desc {
  float: right;
  margin-left: 12px;
  font-size: 12px;
  color: #909399;
}
.prompt-editor-wrapper {
  width: 100%;
}
.prompt-editor-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.prompt-source-tip {
  font-size: 12px;
  color: #909399;
}
.context-collapse {
  width: 100%;
}
.context-block {
  width: 100%;
}
.context-label {
  margin: 8px 0 4px;
  font-weight: 600;
  color: #606266;
}
.context-pre,
.result-pre {
  margin: 0;
  padding: 12px;
  max-height: 420px;
  overflow: auto;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.result-alert {
  margin-bottom: 8px;
}
.run-meta {
  margin-left: 12px;
  font-size: 12px;
  color: #909399;
}
</style>
