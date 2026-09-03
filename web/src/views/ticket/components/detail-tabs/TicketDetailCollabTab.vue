<script setup name="TicketDetailCollabTab">
  import { computed, ref, watch } from 'vue';
  import { getCurrentInstance } from 'vue';
  import { Operation, Setting } from '@element-plus/icons-vue';
  import {
    addTicketMessage,
    addTicketSnapshot,
    extractTicketKnowledge,
    getTicketMessagesPage,
    getTicketSnapshotsPage,
    getTicketSummary,
  } from '@/api/ticket/ticket';
  import {
    buildTicketAiPreferenceDefaults,
    saveTicketAiPreferencePatch,
  } from '../../hooks/useTicketAiPreference';
  import { useAiProviderModelOptions } from '../../hooks/useAiProviderModelOptions';
  import { useOptions } from '../../hooks/useOptions';

  const props = defineProps({
    ticketId: {
      type: [Number, String],
      default: undefined,
    },
    active: {
      type: Boolean,
      default: false,
    },
    detail: {
      type: Object,
      default: null,
    },
    showAiHistory: {
      type: Boolean,
      default: true,
    },
    // 只读模式：隐藏追问发送、快照生成、知识库生成等写入口，仅保留记录查看
    readOnly: {
      type: Boolean,
      default: false,
    },
  });

  const emit = defineEmits(['changed', 'open-ai-history']);
  const { proxy } = getCurrentInstance();

  const {
    agentOptions,
    providerOptions,
    detailVersionOptions,
    loadAgentOptions,
    loadProviderOptions,
    loadDetailVersionOptions,
    resolveAiAnalysisProviderAgent,
    resolveDefaultAiPromptTemplateCodesFromDetail,
  } = useOptions();

  const detail = ref({});
  const loading = ref(false);
  const messageDataText = ref('');
  const messageForm = ref(createDefaultMessageForm());
  // 高级配置区域默认收起，展开后才能填写附件JSON。
  const advancedCollapse = ref([]);
  // AI 结果详情弹窗状态。
  const detailDialogVisible = ref(false);
  const detailDialogTitle = ref('');
  const detailDialogContent = ref('');
  const messageSubmitting = ref(false);
  const snapshotSaving = ref(false);
  const knowledgeGenerating = ref(false);
  const {
    modelOptions: messageModelOptions,
    loadModelOptions: loadMessageModelOptions,
  } = useAiProviderModelOptions();
  const hasExternalDetail = computed(() =>
    Boolean(props.detail?.ticketId || props.detail?.ticket_id)
  );
  const resolvedTicketId = computed(() => {
    const ticketId = Number(props.ticketId || props.detail?.ticketId || props.detail?.ticket_id);
    return Number.isFinite(ticketId) && ticketId > 0 ? ticketId : undefined;
  });

  const ticketMessages = ref([]);
  const ticketSnapshots = ref([]);
  const latestSnapshot = computed(
    () => ticketSnapshots.value[0] || detail.value.latestSnapshot || null
  );
  const latestSnapshotSummary = computed(
    () => latestSnapshot.value?.summary || detail.value.rootCause || detail.value.description || ''
  );
  const messageItems = computed(() =>
    (ticketMessages.value || [])
      // 消息流只展示 AI 分析链路相关消息：用户提问、AI 分析结论、结论等；
      // 快照、同步导入、事件动作等系统类消息不在本区域重复展示。
      .filter(
        (item) =>
          (item.role === 'user' && item.messageType === 'question') ||
          (item.role === 'ai' && ['analysis', 'conclusion'].includes(item.messageType))
      )
      .map((item) => ({
        ...item,
        roleLabel: item.role || 'user',
        typeLabel: item.messageType || 'question',
      }))
  );

  /**
   * 创建协同消息默认表单。
   * @returns {object} 默认消息表单。
   */
  function createDefaultMessageForm() {
    return {
      role: 'user',
      messageType: 'question',
      content: '',
      // 提交消息默认触发AI追问分析（后端 runAi）。
      runAi: true,
      versionId: undefined,
      agentCode: '',
      aiProviderCode: '',
      aiModelName: '',
    };
  }

  /**
   * 使用当前详情和用户偏好重置协同消息表单。
   * @returns {void}
   */
  function resetMessageForm() {
    const aiDefaults = buildTicketAiPreferenceDefaults(
      detail.value,
      resolveDefaultAiPromptTemplateCodesFromDetail(detail.value)
    );
    messageForm.value = {
      ...createDefaultMessageForm(),
      versionId: resolveDefaultMessageId(),
      agentCode: aiDefaults.agentCode,
      aiProviderCode: aiDefaults.aiProviderCode,
      aiModelName: aiDefaults.aiModelName || '',
    };
    loadMessageModelOptions(messageForm.value.aiProviderCode);
    if (!aiDefaults.hasManualAgentCode) {
      applyMessageProviderAgent(messageForm.value.aiProviderCode);
    }
    messageDataText.value = '';
  }

  /**
   * 解析协同消息的默认版本号。
   * 优先使用工单自身版本号，其次使用当前项目已加载的第一个版本选项。
   * @returns {string} 默认版本号。
   */
  function resolveDefaultMessageId() {
    return detail.value.affectedVersionId || detailVersionOptions.value[0]?.value || undefined;
  }

  /**
   * 先加载当前项目的版本选项，再重置协同消息表单。
   * @returns {Promise<void>} 加载和重置完成 Promise。
   */
  function reloadDetailVersionsAndResetMessageForm() {
    return loadDetailVersionOptions(detail.value.projectId)
      .catch(() => {
        detailVersionOptions.value = [];
      })
      .then(() => {
        resetMessageForm();
      });
  }

  /**
   * 根据 Provider 绑定关系回填协同消息 Agent。
   * @param {string} providerCode Provider 编码。
   * @returns {void}
   */
  function applyMessageProviderAgent(providerCode) {
    const providerAgentCode = resolveAiAnalysisProviderAgent(providerCode);
    if (providerAgentCode) {
      messageForm.value.agentCode = providerAgentCode;
    }
  }

  /**
   * 记录用户手动选择的 Agent。
   * @param {string} agentCode Agent 编码。
   * @returns {void}
   */
  function handleMessageAgentChange(agentCode) {
    saveTicketAiPreferencePatch({ agentCode });
  }

  /**
   * 处理 Provider 变更并保存偏好。
   * @param {string} providerCode Provider 编码。
   * @returns {void}
   */
  function handleMessageProviderChange(providerCode) {
    applyMessageProviderAgent(providerCode);
    saveTicketAiPreferencePatch({
      aiProviderCode: providerCode,
      aiModelName: '',
      agentCode: messageForm.value.agentCode,
    });
    // Provider切换后清理旧模型，再加载新Provider的启用模型。
    messageForm.value.aiModelName = '';
    loadMessageModelOptions(providerCode);
  }

  function handleMessageModelChange(aiModelName) {
    saveTicketAiPreferencePatch({ aiModelName });
  }

  /**
   * 刷新协同 tab 需要的详情数据。
   * @returns {Promise<void>} 加载完成 Promise。
   */
  function refreshDetail() {
    if (hasExternalDetail.value) {
      detail.value = props.detail || {};
      return Promise.all([
        getTicketMessagesPage(resolvedTicketId.value, { limit: 20 }),
        getTicketSnapshotsPage(resolvedTicketId.value, { limit: 10 }),
      ]).then(([messagesResponse, snapshotsResponse]) => {
        ticketMessages.value = messagesResponse?.data?.items || [];
        ticketSnapshots.value = snapshotsResponse?.data?.items || [];
        return reloadDetailVersionsAndResetMessageForm();
      });
    }
    if (!resolvedTicketId.value) return Promise.resolve();
    loading.value = true;
    return getTicketSummary(resolvedTicketId.value)
      .then((response) => {
        detail.value = response.data || {};
        return reloadDetailVersionsAndResetMessageForm();
      })
      .finally(() => {
        loading.value = false;
      });
  }

  /**
   * 数据变更后刷新协同 tab，外部已提供详情时交给详情父组件刷新。
   * @returns {Promise<void>} 刷新完成 Promise。
   */
  function refreshAfterChanged() {
    if (hasExternalDetail.value) {
      emit('changed');
      return Promise.resolve();
    }
    return refreshDetail().then(() => {
      emit('changed');
    });
  }

  /**
   * 格式化 JSON 展示内容。
   * @param {unknown} value 待格式化对象。
   * @returns {string} 缩进后的 JSON 字符串。
   */
  function formatJson(value) {
    return JSON.stringify(value, null, 2);
  }

  /**
   * 打开消息详情弹窗，展示消息附件中的 JSON 原始数据。
   * @param {object} item 消息对象。
   * @returns {void}
   */
  function openMessageDetail(item) {
    detailDialogTitle.value = `消息详情 · ${item.roleLabel} · ${item.typeLabel}`;
    detailDialogContent.value = item.attachments ? formatJson(item.attachments) : item.content || '-';
    detailDialogVisible.value = true;
  }

  /**
   * 解析协同消息附件 JSON。
   * @returns {object|undefined|null} 合法附件对象、空值或错误标记。
   */
  function parseMessageAttachments() {
    if (!messageDataText.value) return undefined;
    try {
      return JSON.parse(messageDataText.value);
    } catch (error) {
      proxy.$modal.msgError('消息附件必须是合法 JSON');
      return null;
    }
  }

  /**
   * 提交协同消息，可按表单设置触发 AI 追问。
   * @returns {void}
   */
  function submitMessage() {
    if (messageSubmitting.value) return;
    if (!resolvedTicketId.value) {
      proxy.$modal.msgWarning('工单ID无效，无法提交消息');
      return;
    }
    const content = String(messageForm.value.content || '').trim();
    if (!content) {
      proxy.$modal.msgWarning('请填写消息内容');
      return;
    }
    messageForm.value.versionId = detail.value.affectedVersionId || messageForm.value.versionId;
    const attachments = parseMessageAttachments();
    if (attachments === null) return;
    saveTicketAiPreferencePatch({ aiModelName: messageForm.value.aiModelName || '' });
    messageSubmitting.value = true;
    addTicketMessage(resolvedTicketId.value, {
      ...messageForm.value,
      role: 'user',
      messageType: 'question',
      runAi: true,
      content,
      attachments,
    }).then((response) => {
      const payload = response.data || response || {};
      const aiResult = payload.result || {};
      if (!aiResult.aiSuccess) {
        proxy.$modal.msgWarning(
          aiResult.aiMessage || payload.message || '消息已保存，但AI追问未发起'
        );
      } else {
        proxy.$modal.msgSuccess(payload.message || '已发送，AI分析任务已提交');
      }
      resetMessageForm();
      refreshAfterChanged();
    }).finally(() => {
      messageSubmitting.value = false;
    });
  }

  /**
   * 基于当前详情生成快照。
   * @returns {Promise<void>} 保存完成 Promise。
   */
  function saveSnapshotFromCurrentState() {
    if (snapshotSaving.value) return Promise.resolve();
    if (!resolvedTicketId.value) {
      proxy.$modal.msgWarning('工单ID无效，无法保存快照');
      return Promise.resolve();
    }
    snapshotSaving.value = true;
    return addTicketSnapshot(resolvedTicketId.value, {
      summary: latestSnapshotSummary.value || detail.value.description || '',
      rootCause: detail.value.rootCause || '',
      solution: detail.value.solution || '',
      prevention: latestSnapshot.value?.prevention || '',
      risk: latestSnapshot.value?.risk || '',
      owner: detail.value.currentAssigneeName || '',
      sourceType: 'manual',
      structuredData: {
        ticketId: detail.value.ticketId,
        rootCause: detail.value.rootCause,
        solution: detail.value.solution,
      },
    }).then(() => {
      proxy.$modal.msgSuccess('快照已保存');
      refreshAfterChanged();
    }).finally(() => {
      snapshotSaving.value = false;
    });
  }

  /**
   * 从当前工单提炼知识库案例。
   * @returns {void}
   */
  function generateKnowledgeFromTicket() {
    if (knowledgeGenerating.value) return;
    if (!resolvedTicketId.value) {
      proxy.$modal.msgWarning('工单ID无效，无法生成知识库案例');
      return;
    }
    knowledgeGenerating.value = true;
    extractTicketKnowledge(resolvedTicketId.value).then(() => {
      proxy.$modal.msgSuccess('知识库案例已生成');
      refreshAfterChanged();
    }).finally(() => {
      knowledgeGenerating.value = false;
    });
  }

  watch(
    () => props.detail,
    () => {
      if (hasExternalDetail.value) {
        detail.value = props.detail || {};
        reloadDetailVersionsAndResetMessageForm();
      }
    },
    { immediate: true, deep: true }
  );

  watch(
    resolvedTicketId,
    () => {
      detail.value = hasExternalDetail.value ? props.detail || {} : {};
      if (props.active) {
        refreshDetail();
      } else {
        reloadDetailVersionsAndResetMessageForm();
      }
    },
    { immediate: true }
  );

  watch(
    () => props.active,
    (active) => {
      if (active) refreshDetail();
    }
  );

  loadAgentOptions();
  loadProviderOptions();
</script>

<template>
  <div v-loading="loading" class="ai-analysis-tab">
    <section class="ai-records-panel">
      <div class="ai-section-heading">
        <div>
          <div class="ai-section-title">AI分析记录</div>
          <div class="ai-section-caption">查看追问、分析结果和结构化结论，继续追问可发起新一轮分析</div>
        </div>
      </div>

      <el-card shadow="never" class="ai-records-card">
        <el-empty v-if="!messageItems.length" description="暂无AI分析记录，输入追问后发送" />
        <div v-else class="ai-record-list">
          <article
            v-for="item in messageItems"
            :key="item.id"
            :class="['ai-record', item.role === 'ai' ? 'ai-record--assistant' : 'ai-record--user']"
          >
            <div class="record-head">
              <span class="record-author">{{ item.role === 'ai' ? 'AI分析' : '我的追问' }}</span>
              <el-tag v-if="item.role === 'ai'" size="small" type="success" effect="plain">
                {{ item.typeLabel }}
              </el-tag>
              <span class="record-time">{{ parseTime(item.createTime) }}</span>
              <el-button
                v-if="item.attachments"
                link
                type="primary"
                size="small"
                @click="openMessageDetail(item)"
              >
                查看详情
              </el-button>
            </div>
            <div class="record-content">{{ item.content || '-' }}</div>
          </article>
        </div>
      </el-card>
    </section>

    <section v-if="!readOnly" class="ai-composer" aria-label="AI追问编辑区">
      <div class="ai-config-bar">
        <div class="ai-config-heading">
          <el-icon><Setting /></el-icon>
          <span>AI配置</span>
          <span class="ai-config-hint">本次追问使用</span>
        </div>
        <el-form :model="messageForm" class="ai-config-form" @submit.prevent>
          <el-form-item label="版本">
            <el-select
              v-model="messageForm.versionId"
              size="small"
              placeholder="请选择版本"
              filterable
              clearable
              class="ai-config-select ai-config-select--version"
            >
              <el-option
                v-for="item in detailVersionOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="Agent">
            <el-select
              v-model="messageForm.agentCode"
              size="small"
              placeholder="可选"
              filterable
              clearable
              class="ai-config-select"
              @change="handleMessageAgentChange"
            >
              <el-option
                v-for="item in agentOptions"
                :key="item.agentCode"
                :label="`${item.agentName || item.agentCode} [${item.agentCode}]`"
                :value="item.agentCode"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="Provider">
            <el-select
              v-model="messageForm.aiProviderCode"
              size="small"
              placeholder="可选"
              filterable
              clearable
              class="ai-config-select"
              @change="handleMessageProviderChange"
            >
              <el-option
                v-for="item in providerOptions"
                :key="item.providerCode"
                :label="`${item.providerName || item.providerCode} [${item.providerCode}] ${item.defaultModel ? `- ${item.defaultModel}` : ''}`"
                :value="item.providerCode"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="模型">
            <el-select
              v-model="messageForm.aiModelName"
              size="small"
              placeholder="默认模型"
              filterable
              clearable
              class="ai-config-select"
              :disabled="!messageForm.aiProviderCode"
              @change="handleMessageModelChange"
            >
              <el-option
                v-for="item in (messageModelOptions || [])"
                :key="item.modelId"
                :label="item.displayName || item.modelId"
                :value="item.modelId"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <div class="ai-composer-body">
        <el-input
          v-model="messageForm.content"
          type="textarea"
          :rows="3"
          resize="none"
          maxlength="4000"
          show-word-limit
          placeholder="输入本次分析重点或追问内容"
          class="ai-composer-input"
          @keydown.meta.enter.prevent="submitMessage"
          @keydown.ctrl.enter.prevent="submitMessage"
        />
        <el-collapse v-model="advancedCollapse" class="collab-advanced">
          <el-collapse-item name="advanced" title="分析上下文 JSON（可选）">
            <el-input
              v-model="messageDataText"
              type="textarea"
              :rows="3"
              resize="none"
              placeholder='如 {"traceIds":["..."],"evidence":"..."}'
            />
          </el-collapse-item>
        </el-collapse>
        <div class="ai-composer-footer">
          <span class="ai-composer-tip">Enter 换行，Ctrl/⌘ + Enter 发送并分析</span>
          <div class="ai-composer-actions">
            <el-button link :disabled="messageSubmitting" @click="resetMessageForm">重置</el-button>
            <el-button
              type="primary"
              :icon="Promotion"
              :loading="messageSubmitting"
              :disabled="messageSubmitting || !String(messageForm.content || '').trim()"
              @click="submitMessage"
              v-hasPermi="['ticket:message:add']"
            >
              发送并分析
            </el-button>
          </div>
        </div>
      </div>
    </section>

    <section v-if="!readOnly" class="ai-actions-bar">
      <div class="ai-actions-title">
        <el-icon><Operation /></el-icon>
        <span>分析结果操作</span>
      </div>
      <div class="ai-actions-buttons">
        <el-button
          type="success"
          plain
          :icon="Document"
          :loading="snapshotSaving"
          :disabled="snapshotSaving || knowledgeGenerating"
          @click="saveSnapshotFromCurrentState"
          v-hasPermi="['ticket:snapshot:add']"
        >
          生成快照
        </el-button>
        <el-button
          type="warning"
          plain
          :icon="Collection"
          :loading="knowledgeGenerating"
          :disabled="snapshotSaving || knowledgeGenerating"
          @click="generateKnowledgeFromTicket"
          v-hasPermi="['ticket:knowledge:add']"
        >
          生成知识库
        </el-button>
        <el-button
          v-if="showAiHistory"
          link
          type="primary"
          :icon="Clock"
          @click="emit('open-ai-history')"
          v-hasPermi="['ticket:ai:analysis:list']"
        >
          任务历史
        </el-button>
      </div>
    </section>

    <el-dialog v-model="detailDialogVisible" :title="detailDialogTitle" width="720px" append-to-body>
      <pre class="json-block">{{ detailDialogContent }}</pre>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
  .ai-analysis-tab {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .ai-records-panel,
  .ai-composer,
  .ai-actions-bar {
    border: 1px solid #e4e7ed;
    border-radius: 10px;
    background: #fff;
  }

  .ai-section-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 16px 10px;
  }

  .ai-section-title {
    color: #303133;
    font-size: 15px;
    font-weight: 600;
  }

  .ai-section-caption {
    margin-top: 4px;
    color: #909399;
    font-size: 12px;
  }

  .ai-records-card {
    border: 0;
    border-top: 1px solid #f0f2f5;
    border-radius: 0 0 10px 10px;
  }

  .ai-record-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-height: 420px;
    padding: 2px 4px 4px;
    overflow-y: auto;
  }

  .ai-record {
    max-width: 88%;
    padding: 11px 13px;
    border: 1px solid #ebeef5;
    border-radius: 8px;
  }

  .ai-record--user {
    align-self: flex-end;
    background: #f0f7ff;
    border-color: #c6e2ff;
  }

  .ai-record--assistant {
    align-self: flex-start;
    background: #f8fafc;
  }

  .record-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 7px;
    color: #909399;
    font-size: 12px;
  }

  .record-author {
    color: #606266;
    font-weight: 600;
  }

  .record-time {
    margin-left: auto;
    white-space: nowrap;
  }

  .record-content {
    color: #303133;
    line-height: 1.65;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .ai-composer {
    padding: 12px;
    background: #fbfcfe;
  }

  .ai-config-bar {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 8px 10px;
    border: 1px solid #ebeef5;
    border-radius: 8px;
    background: #fff;
  }

  .ai-config-heading {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    gap: 5px;
    color: #303133;
    font-size: 13px;
    font-weight: 600;
  }

  .ai-config-hint {
    color: #a8abb2;
    font-size: 12px;
    font-weight: 400;
  }

  .ai-config-form {
    display: grid;
    flex: 1;
    grid-template-columns: repeat(4, minmax(120px, 1fr));
    gap: 8px;
  }

  .ai-config-form :deep(.el-form-item) {
    display: flex;
    align-items: center;
    min-width: 0;
    margin: 0;
  }

  .ai-config-form :deep(.el-form-item__label) {
    padding-right: 5px;
    color: #909399;
    font-size: 12px;
    line-height: 28px;
  }

  .ai-config-form :deep(.el-form-item__content) {
    min-width: 0;
    flex: 1;
  }

  .ai-config-select {
    width: 100%;
  }

  .ai-composer-body {
    margin-top: 10px;
    padding: 10px;
    border: 1px solid #dcdfe6;
    border-radius: 8px;
    background: #fff;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }

  .ai-composer-body:focus-within {
    border-color: #409eff;
    box-shadow: 0 0 0 2px rgb(64 158 255 / 12%);
  }

  .ai-composer-input :deep(.el-textarea__inner) {
    padding: 4px 2px;
    border: 0;
    box-shadow: none;
    line-height: 1.6;
  }

  .collab-advanced {
    border-top: 1px solid #f0f2f5;
    border-bottom: 0;
  }

  .collab-advanced :deep(.el-collapse-item__header) {
    height: 32px;
    color: #909399;
    font-size: 12px;
  }

  .collab-advanced :deep(.el-collapse-item__wrap) {
    border-bottom: 0;
  }

  .ai-composer-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-top: 8px;
  }

  .ai-composer-tip {
    color: #a8abb2;
    font-size: 12px;
  }

  .ai-composer-actions {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .ai-actions-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    padding: 10px 14px;
    background: #fbfcfe;
  }

  .ai-actions-title {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #606266;
    font-size: 13px;
    font-weight: 600;
  }

  .ai-actions-buttons {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .json-block {
    padding: 10px;
    margin: 0;
    overflow: auto;
    max-height: 60vh;
    background: #f6f8fa;
    border-radius: 4px;
  }

  @media (max-width: 900px) {
    .ai-config-bar {
      align-items: flex-start;
      flex-direction: column;
      gap: 8px;
    }

    .ai-config-form {
      width: 100%;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 600px) {
    .ai-record {
      max-width: 100%;
    }

    .ai-config-form {
      grid-template-columns: 1fr;
    }

    .ai-composer-footer,
    .ai-actions-bar {
      align-items: flex-start;
      flex-direction: column;
    }

    .ai-actions-buttons {
      flex-wrap: wrap;
    }
  }
</style>
