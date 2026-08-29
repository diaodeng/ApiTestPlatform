<script setup name="TicketDetailCollabTab">
  import { computed, ref, watch } from 'vue';
  import { getCurrentInstance } from 'vue';
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
      .filter((item) => ['question', 'analysis', 'conclusion'].includes(item.messageType))
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
    addTicketMessage(resolvedTicketId.value, {
      ...messageForm.value,
      content,
      attachments,
    }).then((response) => {
      const payload = response.data || response || {};
      const aiResult = payload.result || {};
      // 按表单“发起AI”开关决定是否提示AI追问结果；开关关闭时只提示消息提交成功。
      if (messageForm.value.runAi && !aiResult.aiSuccess) {
        proxy.$modal.msgWarning(
          aiResult.aiMessage || payload.message || '消息已保存，但AI追问未发起'
        );
      } else {
        proxy.$modal.msgSuccess(
          payload.message || (aiResult.aiSuccess ? 'AI追问任务已提交' : '消息提交成功')
        );
      }
      resetMessageForm();
      refreshAfterChanged();
    });
  }

  /**
   * 基于当前详情生成快照。
   * @returns {Promise<void>} 保存完成 Promise。
   */
  function saveSnapshotFromCurrentState() {
    if (!resolvedTicketId.value) {
      proxy.$modal.msgWarning('工单ID无效，无法保存快照');
      return Promise.resolve();
    }
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
    });
  }

  /**
   * 从当前工单提炼知识库案例。
   * @returns {void}
   */
  function generateKnowledgeFromTicket() {
    if (!resolvedTicketId.value) {
      proxy.$modal.msgWarning('工单ID无效，无法生成知识库案例');
      return;
    }
    extractTicketKnowledge(resolvedTicketId.value).then(() => {
      proxy.$modal.msgSuccess('知识库案例已生成');
      refreshAfterChanged();
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
  <div v-loading="loading">
    <el-row :gutter="16">
      <el-col :span="24">
        <el-form :model="messageForm" label-width="90px" class="mb16">
          <el-row :gutter="12">
            <el-col :span="6">
              <el-form-item label="角色">
                <el-select v-model="messageForm.role">
                  <el-option label="提问人" value="user" />
                  <el-option label="AI" value="ai" />
                  <el-option label="开发" value="developer" />
                  <el-option label="测试" value="tester" />
                  <el-option label="系统" value="system" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="类型">
                <el-select v-model="messageForm.messageType">
                  <el-option label="追问" value="question" />
                  <el-option label="分析" value="analysis" />
                  <el-option label="日志" value="log" />
                  <el-option label="结论" value="conclusion" />
                  <el-option label="动作" value="action" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="发起AI">
                <el-switch
                  v-model="messageForm.runAi"
                  inline-prompt
                  active-text="是"
                  inactive-text="否"
                />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label-width="0">
                <el-button
                  @click="emit('open-ai-history')"
                  v-hasPermi="['ticket:ai:analysis:list']"
                >
                  任务历史
                </el-button>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="版本">
                <el-select
                  v-model="messageForm.versionId"
                  placeholder="请选择版本"
                  filterable
                  clearable
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in detailVersionOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Agent">
                <el-select
                  v-model="messageForm.agentCode"
                  placeholder="可选"
                  filterable
                  clearable
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
            </el-col>
            <el-col :span="12">
              <el-form-item label="Provider">
                <el-select
                  v-model="messageForm.aiProviderCode"
                  placeholder="可选"
                  filterable
                  clearable
                  style="width: 100%"
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
            </el-col>
            <el-col :span="12">
              <el-form-item label="模型">
                <el-select
                  v-model="messageForm.aiModelName"
                  placeholder="留空使用默认模型"
                  filterable
                  clearable
                  style="width: 100%"
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
            </el-col>
            <el-col :span="24">
              <el-form-item label="内容">
                <el-input
                  v-model="messageForm.content"
                  type="textarea"
                  :rows="4"
                  placeholder="补充追问、开发反馈、排查动作或AI结论"
                />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-collapse v-model="advancedCollapse" class="collab-advanced">
                <el-collapse-item name="advanced" title="高级选项（附件 JSON）">
                  <el-form-item label="附件JSON" label-width="90px">
                    <el-input
                      v-model="messageDataText"
                      type="textarea"
                      :rows="3"
                      placeholder='可选，如 {"traceIds":["..."],"evidence":"..."}'
                    />
                  </el-form-item>
                </el-collapse-item>
              </el-collapse>
            </el-col>
            <el-col :span="24">
              <el-form-item>
                <el-button type="primary" @click="submitMessage" v-hasPermi="['ticket:message:add']"
                  >提交消息</el-button
                >
                <el-button @click="resetMessageForm">重置</el-button>
                <el-button
                  type="success"
                  plain
                  @click="saveSnapshotFromCurrentState"
                  v-hasPermi="['ticket:snapshot:add']"
                >
                  生成快照
                </el-button>
                <el-button
                  type="warning"
                  plain
                  @click="generateKnowledgeFromTicket"
                  v-hasPermi="['ticket:knowledge:add']"
                >
                  生成知识库
                </el-button>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>

        <el-card shadow="never">
          <template #header>消息流</template>
          <el-empty v-if="!messageItems.length" description="暂无AI分析相关消息" />
          <div v-for="item in messageItems" :key="item.id" class="mb12">
            <div class="record-head">
              <span>{{ item.roleLabel }}</span>
              <el-tag size="small">{{ item.typeLabel }}</el-tag>
              <span>{{ parseTime(item.createTime) }}</span>
              <el-button
                v-if="item.attachments"
                link
                type="primary"
                size="small"
                @click="openMessageDetail(item)"
              >
                详情
              </el-button>
            </div>
            <div>{{ item.content || '-' }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="detailDialogVisible" :title="detailDialogTitle" width="720px" append-to-body>
      <pre class="json-block">{{ detailDialogContent }}</pre>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
  .collab-advanced {
    width: 100%;
    border-top: none;
    border-bottom: none;
  }

  .record-head {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 8px;
    color: #606266;
    font-size: 13px;
  }

  .json-block {
    padding: 10px;
    margin: 0;
    overflow: auto;
    max-height: 60vh;
    background: #f6f8fa;
    border-radius: 4px;
  }
</style>
