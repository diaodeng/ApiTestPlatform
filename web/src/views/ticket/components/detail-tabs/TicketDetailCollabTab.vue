<script setup name="TicketDetailCollabTab">
  import { computed, ref, watch } from 'vue';
  import { getCurrentInstance } from 'vue';
  import { useRouter } from 'vue-router';
  import {
    addTicketMessage,
    addTicketSnapshot,
    bindTicketIssueFromSimilar,
    extractTicketKnowledge,
    getTicket,
  } from '@/api/ticket/ticket';
  import {
    buildTicketAiPreferenceDefaults,
    saveTicketAiPreferencePatch,
  } from '../../hooks/useTicketAiPreference';
  import { useOptions } from '../../hooks/useOptions';

  const props = defineProps({
    ticketId: {
      type: [Number, String],
      required: true,
    },
    active: {
      type: Boolean,
      default: false,
    },
  });

  const emit = defineEmits(['changed', 'run-ai', 'open-ai-history']);
  const { proxy } = getCurrentInstance();
  const router = useRouter();

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
  const issueActionLoading = ref(false);
  const messageForm = ref(createDefaultMessageForm());

  const ticketMessages = computed(() => detail.value.messages || []);
  const ticketSnapshots = computed(() => detail.value.snapshots || []);
  const similarTickets = computed(() => detail.value.similarTickets || []);
  const latestSnapshot = computed(
    () => ticketSnapshots.value[0] || detail.value.latestSnapshot || null
  );
  const latestSnapshotSummary = computed(
    () => latestSnapshot.value?.summary || detail.value.rootCause || detail.value.description || ''
  );
  const messageItems = computed(() =>
    (ticketMessages.value || []).map((item) => ({
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
      runAi: true,
      versionKey: '',
      agentCode: '',
      aiProviderCode: '',
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
      versionKey: detail.value.versionKey || detail.value.extraData?.versionKey || '',
      agentCode: aiDefaults.agentCode,
      aiProviderCode: aiDefaults.aiProviderCode,
    };
    if (!aiDefaults.hasManualAgentCode) {
      applyMessageProviderAgent(messageForm.value.aiProviderCode);
    }
    messageDataText.value = '';
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
      agentCode: messageForm.value.agentCode,
    });
  }

  /**
   * 刷新协同 tab 需要的详情数据。
   * @returns {Promise<void>} 刷新完成 Promise。
   */
  function refreshDetail() {
    if (!props.ticketId) return Promise.resolve();
    loading.value = true;
    return getTicket(props.ticketId)
      .then((response) => {
        detail.value = response.data || {};
        loadDetailVersionOptions(detail.value.projectId);
        resetMessageForm();
      })
      .finally(() => {
        loading.value = false;
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
    const content = String(messageForm.value.content || '').trim();
    if (!content) {
      proxy.$modal.msgWarning('请填写消息内容');
      return;
    }
    messageForm.value.versionKey =
      detail.value.versionKey ||
      detail.value.extraData?.versionKey ||
      messageForm.value.versionKey ||
      '';
    const attachments = parseMessageAttachments();
    if (attachments === null) return;
    addTicketMessage(props.ticketId, {
      ...messageForm.value,
      content,
      attachments,
    }).then((response) => {
      const payload = response.data || response || {};
      const aiResult = payload.result || {};
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
      refreshDetail();
      emit('changed');
    });
  }

  /**
   * 基于当前详情生成快照。
   * @returns {Promise<void>} 保存完成 Promise。
   */
  function saveSnapshotFromCurrentState() {
    return addTicketSnapshot(props.ticketId, {
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
      refreshDetail();
      emit('changed');
    });
  }

  /**
   * 从当前工单提炼知识库案例。
   * @returns {void}
   */
  function generateKnowledgeFromTicket() {
    extractTicketKnowledge(props.ticketId).then(() => {
      proxy.$modal.msgSuccess('知识库案例已生成');
      refreshDetail();
      emit('changed');
    });
  }

  /**
   * 解析外部工单详情链接。
   * @param {object} ticketRow 工单行。
   * @returns {string} 外部链接。
   */
  function resolveTicketDetailUrl(ticketRow) {
    const row = ticketRow || {};
    const syncSummary = row.syncSummary || row.sync_summary || {};
    const extraData = row.extraData || row.extra_data || {};
    const externalSync = extraData.externalSync || extraData.external_sync || {};
    const source = externalSync.source || {};
    return String(
      row.ticketUrl ||
        row.ticket_url ||
        row.url ||
        syncSummary.ticketUrl ||
        syncSummary.ticket_url ||
        syncSummary.sourceRecordUrl ||
        syncSummary.source_record_url ||
        source.ticketUrl ||
        source.ticket_url ||
        source.recordUrl ||
        source.record_url ||
        ''
    ).trim();
  }

  /**
   * 打开外部工单详情。
   * @param {object} ticketRow 工单行。
   * @returns {void}
   */
  function openTicketLink(ticketRow) {
    const url = resolveTicketDetailUrl(ticketRow);
    if (!url) {
      proxy.$modal.msgWarning('当前工单未配置详情链接');
      return;
    }
    window.open(url, '_blank', 'noopener');
  }

  /**
   * 打开系统内工单详情页。
   * @param {object} ticketRow 工单行。
   * @returns {void}
   */
  function openSystemTicketDetail(ticketRow) {
    const ticketId = Number(ticketRow?.ticketId || ticketRow?.ticket_id);
    if (!Number.isFinite(ticketId) || ticketId <= 0) return;
    const resolved = router.resolve({ name: 'TicketDetail', params: { ticketId } });
    window.open(resolved.href, '_blank');
  }

  /**
   * 将当前工单与相似工单归入同一问题。
   * @param {object} item 相似工单。
   * @returns {void}
   */
  function handleBindIssueFromSimilar(item) {
    const similarTicketId = Number(item?.ticketId || item?.ticket_id);
    if (!props.ticketId || !similarTicketId) {
      proxy.$modal.msgWarning('相似工单ID无效，无法归因');
      return;
    }
    proxy.$modal
      .confirm(`是否确认将当前工单与 ${item.ticketNo || similarTicketId} 归入同一问题？`)
      .then(() => {
        issueActionLoading.value = true;
        return bindTicketIssueFromSimilar(props.ticketId, {
          similarTicketId,
          confidence: item.score,
          relationType: 'similar',
        });
      })
      .then(() => {
        proxy.$modal.msgSuccess('相似工单归因已确认');
        refreshDetail();
        emit('changed');
      })
      .finally(() => {
        issueActionLoading.value = false;
      });
  }

  watch(
    () => props.ticketId,
    () => {
      detail.value = {};
      resetMessageForm();
      if (props.active) refreshDetail();
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
    <div class="collab-toolbar mb16">
      <el-button type="primary" @click="emit('run-ai')" v-hasPermi="['ticket:ai:analysis:run']">
        发起AI分析
      </el-button>
      <el-button @click="emit('open-ai-history')" v-hasPermi="['ticket:ai:analysis:list']">
        任务历史
      </el-button>
    </div>
    <el-row :gutter="16">
      <el-col :span="16">
        <el-form :model="messageForm" label-width="90px" class="mb16">
          <el-row :gutter="12">
            <el-col :span="8">
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
            <el-col :span="8">
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
            <el-col :span="8">
              <el-form-item label="发起AI">
                <el-switch
                  v-model="messageForm.runAi"
                  inline-prompt
                  active-text="是"
                  inactive-text="否"
                />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-alert
                :title="`协同消息默认沿用工单版本号：${detail.versionKey || detail.extraData?.versionKey || '-'}。`"
                type="info"
                show-icon
                :closable="false"
                class="mb12"
              />
            </el-col>
            <el-col :span="24">
              <el-form-item label="版本号">
                <el-select
                  v-model="messageForm.versionKey"
                  placeholder="请选择或输入版本号"
                  filterable
                  clearable
                  allow-create
                  default-first-option
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
            <el-col :span="24">
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
            <el-col :span="24">
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
                    :label="`${item.providerName || item.providerCode} [${item.providerCode}] ${item.modelName ? `- ${item.modelName}` : ''}`"
                    :value="item.providerCode"
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
              <el-form-item label="附件JSON">
                <el-input
                  v-model="messageDataText"
                  type="textarea"
                  :rows="3"
                  placeholder='可选，如 {"traceIds":["..."],"evidence":"..."}'
                />
              </el-form-item>
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
          <el-empty v-if="!messageItems.length" description="暂无消息" />
          <div v-for="item in messageItems" :key="item.id" class="mb12">
            <div class="record-head">
              <span>{{ item.roleLabel }}</span>
              <el-tag size="small">{{ item.typeLabel }}</el-tag>
              <span>{{ parseTime(item.createTime) }}</span>
            </div>
            <div>{{ item.content || '-' }}</div>
            <pre v-if="item.attachments" class="json-block">{{ formatJson(item.attachments) }}</pre>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <template #header>相似工单</template>
          <el-empty v-if="!similarTickets.length" description="暂无相似工单" />
          <div v-for="item in similarTickets" :key="item.ticketId" class="similar-item">
            <div class="similar-title">{{ item.ticketNo }} {{ item.title }}</div>
            <div class="similar-meta">
              <span>相似度 {{ Math.round((item.score || 0) * 100) }}%</span>
              <span>{{ item.rootCause || '-' }}</span>
            </div>
            <div class="similar-actions">
              <el-link type="primary" :underline="false" @click="openSystemTicketDetail(item)"
                >系统详情</el-link
              >
              <el-link
                v-if="resolveTicketDetailUrl(item)"
                type="info"
                :underline="false"
                @click="openTicketLink(item)"
              >
                飞书详情
              </el-link>
              <el-button
                link
                type="success"
                :loading="issueActionLoading"
                @click="handleBindIssueFromSimilar(item)"
                v-hasPermi="['ticket:issue:bind']"
              >
                归入同一问题
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
  .collab-toolbar {
    display: flex;
    gap: 12px;
    align-items: center;
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
    margin: 10px 0 0;
    overflow: auto;
    background: #f6f8fa;
    border-radius: 4px;
  }

  .similar-item {
    padding: 10px 0;
    border-bottom: 1px solid #ebeef5;
  }

  .similar-item:last-child {
    border-bottom: 0;
  }

  .similar-title {
    margin-bottom: 4px;
    font-weight: 600;
  }

  .similar-meta {
    display: flex;
    gap: 10px;
    color: #606266;
    font-size: 12px;
  }

  .similar-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    margin-top: 6px;
    font-size: 12px;
  }
</style>
