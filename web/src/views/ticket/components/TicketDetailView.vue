<template>
  <div class="ticket-detail-view" v-loading="loading">
    <div class="detail-header">
      <div>
        <div class="detail-title">{{ detail.ticketNo || '-' }} {{ detail.title || '' }}</div>
        <div class="detail-meta">
          <span>{{ detail.projectName || detail.merchantName || '未填写项目' }}</span>
          <span>{{ detail.moduleName || '未填写模块' }}</span>
          <el-tag :type="getStatusTagType(detail.status)">{{ formatTicketStatus(detail.status) }}</el-tag>
        </div>
      </div>
      <div class="detail-actions">
        <el-button icon="Refresh" @click="refreshDetailData">刷新</el-button>
      </div>
    </div>

    <el-descriptions :column="3" border>
      <el-descriptions-item label="工单类型">{{ formatIssueType(detail) }}</el-descriptions-item>
      <el-descriptions-item label="问题性质">{{ formatProblemFlag(detail.isProblem) }}</el-descriptions-item>
      <el-descriptions-item label="当前处理人">{{ detail.currentAssigneeName || '-' }}</el-descriptions-item>
      <el-descriptions-item label="一线人员">{{ detail.firstLineAssigneeName || '-' }}</el-descriptions-item>
      <el-descriptions-item label="内部负责人">{{ detail.internalOwnerName || '-' }}</el-descriptions-item>
      <el-descriptions-item label="提交时间">{{ formatDateTime(detail.submitTime) }}</el-descriptions-item>
      <el-descriptions-item label="根因分类">{{ detail.rootCauseType || '-' }}</el-descriptions-item>
      <el-descriptions-item label="解决方式">{{ detail.solutionType || '-' }}</el-descriptions-item>
      <el-descriptions-item label="关闭结果">{{ detail.resolutionName || detail.resolutionCode || '-' }}</el-descriptions-item>
    </el-descriptions>

    <section class="detail-section">
      <TicketDescriptionBlock
        :key="detail.ticketId"
        :original-description="detailOriginalDescription"
        :ai-translation="detailAiTranslation"
        :allow-translate="false"
      />
    </section>

    <el-tabs v-model="activeTab" class="detail-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="概览" name="overview">
        <el-row :gutter="16">
          <el-col :xs="24" :lg="12">
            <el-card shadow="never">
              <template #header>最新AI结论</template>
              <div class="pre-line">{{ latestSummary || '-' }}</div>
            </el-card>
          </el-col>
          <el-col :xs="24" :lg="12">
            <el-card shadow="never">
              <template #header>最终处理</template>
              <div class="kv-row"><span>根因</span><strong>{{ detail.rootCause || '-' }}</strong></div>
              <div class="kv-row"><span>方案</span><strong>{{ detail.solution || '-' }}</strong></div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="相似工单" name="similar">
        <TicketSimilarPanel
          :symptom-tickets="symptomTickets"
          :case-tickets="caseTickets"
          :similar-loading="similarLoading"
          :similar-error="similarError"
          :similar-status="similarStatus"
          :allow-bind-issue="false"
          :similarity-case="detail.similarityCase || null"
          :allow-case-action="false"
        />
      </el-tab-pane>

      <el-tab-pane label="AI分析" name="collab">
        <TicketDetailCollabTab
          :ticket-id="props.ticketId"
          :active="activeTab === 'collab'"
          :detail="detail"
          :show-ai-history="false"
          read-only
          @changed="refreshDetailData"
        />
      </el-tab-pane>

      <el-tab-pane label="评论" name="comments">
        <TicketDetailCommentsTab
          :ticket-id="props.ticketId"
          :active="activeTab === 'comments'"
          read-only
          @changed="loadDetail"
        />
      </el-tab-pane>

      <el-tab-pane label="历史" name="history">
        <el-empty v-if="!timelineRows.length" description="暂无历史记录" />
        <el-timeline>
          <el-timeline-item
            v-for="item in timelineRows"
            :key="item.id || `${item.type}-${item.createTime}`"
            :timestamp="formatDateTime(item.createTime || item.startedAt)"
          >
            <div>{{ item.title || item.eventType || item.toStatus || item.type || '历史记录' }}</div>
            <div class="pre-line muted">{{ item.comment || item.content || item.description || '-' }}</div>
          </el-timeline-item>
        </el-timeline>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
  import { computed, ref, watch } from 'vue';
  import {
    getTicketSummary,
    getTicketSimilarTickets,
    getTicketTimeline,
  } from '@/api/ticket/ticket';
  import TicketDetailCollabTab from './detail-tabs/TicketDetailCollabTab.vue';
  import TicketDetailCommentsTab from './detail-tabs/TicketDetailCommentsTab.vue';
  import TicketSimilarPanel from './detail-shared/TicketSimilarPanel.vue';
  import TicketDescriptionBlock from './detail-shared/TicketDescriptionBlock.vue';
  import { useWorkflow } from '../hooks/useWorkflow';

  const props = defineProps({
    ticketId: {
      type: [Number, String],
      required: true,
    },
  });

  // 工单状态选项：合并自定义工作流状态节点，用于把状态 code 转成状态名称展示
  const currentTicketStatus = ref('');
  const { ticketStatusOptions, getStatusTagType, loadWorkflowConfig } = useWorkflow(currentTicketStatus);
  const loading = ref(false);
  const activeTab = ref('overview');
  const detail = ref({});
  const timeline = ref({});
  const timelineLoaded = ref(false);
  // 相似工单独立加载状态：与主详情解耦，慢查询不阻塞首屏
  const similarLoading = ref(false);
  const similarError = ref('');
  const similarStatus = ref('idle');
  const similarTickets = ref([]);
  // 相似工单是否已按当前工单加载完成，用于相似标签懒加载
  const similarLoadedTicketId = ref(0);
  // 请求代次保护：工单切换或刷新后丢弃旧响应，避免旧数据覆盖当前工单
  let requestGeneration = 0;

  const detailOriginalDescription = computed(() => {
    const extraData = detail.value.extraData || {};
    const originalText = String(
      detail.value.originalDescription ||
      extraData.originDescription ||
      extraData.origin_description ||
      ''
    ).trim();
    if (originalText) return originalText;
    const description = String(detail.value.description || '').trim();
    return description.includes('【AI翻译】')
      ? description.split('【AI翻译】')[0].trim()
      : description;
  });
  const detailAiTranslation = computed(() => {
    const extraData = detail.value.extraData || {};
    const raw = String(
      detail.value.aiTranslation || extraData.aiTranslation || extraData.ai_translation || ''
    ).trim();
    if (!raw) return '';
    // 移除可能混入的【AI翻译】标记，确保只展示纯译文
    if (raw.startsWith('【AI翻译】')) {
      return raw.slice('【AI翻译】'.length).trim();
    }
    const markerIndex = raw.indexOf('【AI翻译】');
    if (markerIndex >= 0) {
      return raw.slice(markerIndex + '【AI翻译】'.length).trim();
    }
    return raw;
  });
  const latestSummary = computed(
    () =>
      detail.value.latestAiAnalysis?.analysisSummary ||
      detail.value.latestAiAnalysis?.summary ||
      ''
  );
  // 相似工单数据来源：独立相似接口结果，主概览不再携带相似数据
  const symptomTickets = ref([]);
  const caseTickets = ref([]);
  const timelineRows = computed(() => {
    const source = timeline.value || {};
    const rows = [
      ...(Array.isArray(source.events) ? source.events.map((item) => ({ ...item, type: '事件' })) : []),
      ...(Array.isArray(source.statusHistories)
        ? source.statusHistories.map((item) => ({ ...item, type: '状态流转' }))
        : []),
      ...(Array.isArray(source.assignHistories)
        ? source.assignHistories.map((item) => ({ ...item, type: '指派' }))
        : []),
    ];
    return rows.sort(
      (left, right) =>
        new Date(right.createTime || right.startedAt || 0).getTime() -
        new Date(left.createTime || left.startedAt || 0).getTime()
    );
  });

  /**
   * 将工单状态 code 转成状态名称。
   * 优先匹配自定义工作流状态节点名称，未匹配到时回退默认枚举，仍无结果则原样展示。
   */
  function formatTicketStatus(value) {
    const statusValue = String(value || '').trim();
    return ticketStatusOptions.value.find((item) => item.value === statusValue)?.label || statusValue || '未填写状态';
  }

  /**
   * 加载独立详情页主概览。
   * 使用轻量 summary 接口，不读取消息、快照和相似工单，保证首屏快速展示。
   */
  function loadDetail() {
    const currentTicketId = Number(props.ticketId || 0);
    if (!currentTicketId) {
      return Promise.resolve();
    }
    const generation = requestGeneration;
    loading.value = true;
    return getTicketSummary(currentTicketId)
      .then((response) => {
        if (!isCurrentRequest(currentTicketId, generation)) return;
        detail.value = response.data || {};
        // 同步当前状态供工作流转规则计算使用
        currentTicketStatus.value = detail.value.status || '';
      })
      .finally(() => {
        if (isCurrentRequest(currentTicketId, generation)) {
          loading.value = false;
        }
      });
  }

  /**
   * 统一刷新入口：重新加载主概览，并强制重查相似工单。
   */
  function refreshDetailData() {
    const currentTicketId = Number(props.ticketId || 0);
    if (!currentTicketId) {
      return Promise.resolve();
    }
    requestGeneration += 1;
    similarLoadedTicketId.value = 0;
    return Promise.all([loadDetail(), loadSimilarTickets(currentTicketId)]);
  }

  /**
   * 判断响应是否仍属于当前工单和当前请求代次。
   * @param {number} ticketId 发起请求时的工单ID
   * @param {number} generation 发起请求时的代次
   * @returns {boolean} 是否为当前有效响应
   */
  function isCurrentRequest(ticketId, generation) {
    return Number(props.ticketId || 0) === ticketId && requestGeneration === generation;
  }

  /**
   * 按需加载相似工单。
   * 相似查询可能触发向量生成与扫描，独立于主概览请求，避免阻塞首屏。
   * @param {number} ticketId 当前工单ID
   * @returns {Promise<void>} 加载完成 Promise
   */
  function loadSimilarTickets(ticketId) {
    if (!ticketId) {
      return Promise.resolve();
    }
    const generation = requestGeneration;
    similarLoading.value = true;
    similarError.value = '';
    similarStatus.value = 'loading';
    return getTicketSimilarTickets(ticketId, { limit: 5 })
      .then((response) => {
        if (!isCurrentRequest(ticketId, generation)) return;
        const payload = response?.data || {};
        similarTickets.value = payload.items || [];
        symptomTickets.value = payload.symptomTickets || payload.items?.filter((item) => item.matchType !== 'case') || [];
        caseTickets.value = payload.caseTickets || payload.items?.filter((item) => item.matchType === 'case') || [];
        similarStatus.value = payload.status || 'ready';
        similarError.value = payload.message || '';
        similarLoadedTicketId.value = ticketId;
      })
      .catch((error) => {
        if (!isCurrentRequest(ticketId, generation)) return;
        similarTickets.value = [];
        symptomTickets.value = [];
        caseTickets.value = [];
        similarStatus.value = 'failed';
        similarError.value = error?.message || '相似工单加载失败';
        similarLoadedTicketId.value = ticketId;
      })
      .finally(() => {
        if (isCurrentRequest(ticketId, generation)) {
          similarLoading.value = false;
        }
      });
  }

  /**
   * 切换到相似工单标签时懒加载相似结果。
   * 首次进入或刷新后未重新加载时才发起请求，重复切换不重复查询。
   */
  function ensureSimilarLoaded() {
    const currentTicketId = Number(props.ticketId || 0);
    if (!currentTicketId) return;
    if (similarLoadedTicketId.value === currentTicketId || similarLoading.value) return;
    loadSimilarTickets(currentTicketId);
  }

  /**
   * 按需加载历史时间线，保持纯净详情页首屏轻量。
   */
  function loadTimeline() {
    if (timelineLoaded.value || !props.ticketId) {
      return;
    }
    getTicketTimeline(props.ticketId).then((response) => {
      timeline.value = response.data || {};
      timelineLoaded.value = true;
    });
  }

  /**
   * 切换详情页标签时补充加载当前标签需要的数据。
   */
  function handleTabChange(tabName) {
    if (tabName === 'history') {
      loadTimeline();
    }
    if (tabName === 'similar') {
      ensureSimilarLoaded();
    }
  }

  function formatIssueType(row) {
    return row.issueTypeName || row.issueTypeId || '-';
  }

  function formatProblemFlag(value) {
    if (value === true) return '真实问题';
    if (value === false) return '非问题';
    return '未填写';
  }

  function formatDateTime(value) {
    if (!value) {
      return '-';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    return date.toLocaleString('zh-CN', { hour12: false });
  }

  watch(
    () => props.ticketId,
    () => {
      requestGeneration += 1;
      activeTab.value = 'overview';
      timeline.value = {};
      timelineLoaded.value = false;
      // 切换工单时清空相似工单状态，避免展示上一张工单的相似结果
      similarTickets.value = [];
      symptomTickets.value = [];
      caseTickets.value = [];
      similarLoading.value = false;
      similarError.value = '';
      similarStatus.value = 'idle';
      similarLoadedTicketId.value = 0;
      loadDetail();
    },
    { immediate: true }
  );

  // 加载工作流状态配置，保证顶部状态显示状态名称而不是状态 code
  loadWorkflowConfig();
</script>

<style scoped>
  .ticket-detail-view {
    padding: 16px;
  }

  .detail-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
  }

  .detail-actions {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    gap: 0;
    white-space: nowrap;
  }

  .detail-title {
    font-size: 20px;
    font-weight: 600;
    line-height: 1.4;
  }

  .detail-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 16px;
    margin-top: 6px;
    color: #606266;
    font-size: 13px;
  }

  .detail-section {
    margin-top: 16px;
  }

  .detail-tabs {
    margin-top: 16px;
  }

  .kv-row {
    display: flex;
    gap: 12px;
    margin-bottom: 10px;
  }

  .kv-row span {
    width: 48px;
    color: #606266;
    flex: 0 0 auto;
  }

  .pre-line {
    white-space: pre-line;
    word-break: break-word;
  }

  .muted {
    color: #909399;
    font-size: 12px;
  }
</style>
