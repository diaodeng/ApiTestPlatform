<template>
  <div class="ticket-detail-view" v-loading="loading">
    <div class="detail-header">
      <div>
        <div class="detail-title">{{ detail.ticketNo || '-' }} {{ detail.title || '' }}</div>
        <div class="detail-meta">
          <span>{{ detail.projectName || detail.merchantName || '未填写项目' }}</span>
          <span>{{ detail.moduleName || '未填写模块' }}</span>
          <span>{{ detail.status || '未填写状态' }}</span>
        </div>
      </div>
      <el-button icon="Refresh" @click="loadDetail">刷新</el-button>
    </div>

    <el-descriptions :column="3" border>
      <el-descriptions-item label="工单类型">{{ formatIssueType(detail) }}</el-descriptions-item>
      <el-descriptions-item label="问题性质">{{ formatProblemFlag(detail.isProblem) }}</el-descriptions-item>
      <el-descriptions-item label="当前处理人">{{ detail.currentAssigneeName || '-' }}</el-descriptions-item>
      <el-descriptions-item label="一线人员">{{ detail.firstLineAssigneeName || '-' }}</el-descriptions-item>
      <el-descriptions-item label="内部负责人">{{ detail.internalOwnerName || '-' }}</el-descriptions-item>
      <el-descriptions-item label="提交时间">{{ formatDateTime(detail.submitTime || detail.createTime) }}</el-descriptions-item>
      <el-descriptions-item label="根因分类">{{ detail.rootCauseType || '-' }}</el-descriptions-item>
      <el-descriptions-item label="解决方式">{{ detail.solutionType || '-' }}</el-descriptions-item>
      <el-descriptions-item label="关闭结果">{{ detail.resolutionName || detail.resolutionCode || '-' }}</el-descriptions-item>
    </el-descriptions>

    <section class="detail-section">
      <div class="section-title section-title--with-actions">
        <span>描述</span>
        <el-button link type="primary" @click="descriptionExpanded = !descriptionExpanded">
          {{ descriptionExpanded ? '收起' : '展开' }}
        </el-button>
      </div>
      <div
        :class="[
          'section-content',
          'pre-line',
          { 'section-content--collapsed': !descriptionExpanded },
        ]"
      >
        {{ detailOriginalDescription || '-' }}
      </div>
      <div v-if="detailAiTranslation" class="translation-block">
        <div class="section-title section-title--with-actions">
          <span>AI翻译</span>
          <el-button link type="primary" @click="translationExpanded = !translationExpanded">
            {{ translationExpanded ? '收起' : '展开' }}
          </el-button>
        </div>
        <div
          :class="[
            'section-content',
            'pre-line',
            { 'section-content--collapsed': !translationExpanded },
          ]"
        >
          {{ detailAiTranslation }}
        </div>
      </div>
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
        <el-alert
          v-if="detail.similarEmbeddingStatus && detail.similarEmbeddingStatus !== 'ready'"
          type="warning"
          show-icon
          :closable="false"
          class="mb12"
          :title="detail.similarEmbeddingMessage || '当前相似工单向量不可用'"
        />
        <el-empty v-if="!similarTickets.length" description="暂无相似工单" />
        <div v-for="item in similarTickets" :key="item.ticketId" class="similar-item">
          <div>
            <div class="similar-title">{{ item.ticketNo }} {{ item.title }}</div>
            <div class="detail-meta">
              <span>相似度 {{ formatPercent(item.score) }}</span>
              <span>{{ item.moduleName || '-' }}</span>
              <span>{{ item.status || '-' }}</span>
            </div>
          </div>
          <div class="similar-actions">
            <el-button link type="primary" @click="openSystemTicketDetail(item)">系统详情</el-button>
            <el-button v-if="resolveTicketDetailUrl(item)" link type="primary" @click="openExternalTicket(item)">
              飞书详情
            </el-button>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="评论" name="comments">
        <el-empty v-if="!commentList.length" description="暂无评论" />
        <div v-for="item in commentList" :key="item.commentId || item.id" class="comment-item">
          <div class="comment-meta">
            <strong>{{ item.createdByName || item.operatorName || item.createBy || '-' }}</strong>
            <span>{{ formatDateTime(item.createTime) }}</span>
          </div>
          <div class="pre-line">{{ item.content || '-' }}</div>
        </div>
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
  import { useRouter } from 'vue-router';
  import { getTicket, getTicketComments, getTicketTimeline } from '@/api/ticket/ticket';

  const props = defineProps({
    ticketId: {
      type: [Number, String],
      required: true,
    },
  });

  const router = useRouter();
  const loading = ref(false);
  const activeTab = ref('overview');
  const descriptionExpanded = ref(true);
  const translationExpanded = ref(true);
  const detail = ref({});
  const commentList = ref([]);
  const commentLoaded = ref(false);
  const timeline = ref({});
  const timelineLoaded = ref(false);

  const detailOriginalDescription = computed(() => {
    const extraData = detail.value.extraData || {};
    return (
      detail.value.originalDescription ||
      extraData.originDescription ||
      extraData.origin_description ||
      detail.value.description ||
      ''
    );
  });
  const detailAiTranslation = computed(() => {
    const extraData = detail.value.extraData || {};
    return detail.value.aiTranslation || extraData.aiTranslation || extraData.ai_translation || '';
  });
  const latestSummary = computed(
    () =>
      detail.value.latestSnapshot?.summary ||
      detail.value.latestAiAnalysis?.analysisSummary ||
      detail.value.latestAiAnalysis?.summary ||
      ''
  );
  const similarTickets = computed(() => (Array.isArray(detail.value.similarTickets) ? detail.value.similarTickets : []));
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
   * 加载纯净详情页所需的工单主详情。
   */
  function loadDetail() {
    const currentTicketId = Number(props.ticketId || 0);
    if (!currentTicketId) {
      return Promise.resolve();
    }
    loading.value = true;
    return getTicket(currentTicketId)
      .then((response) => {
        detail.value = response.data || {};
      })
      .finally(() => {
        loading.value = false;
      });
  }

  /**
   * 按需加载评论，避免首次打开详情页时请求无关数据。
   */
  function loadComments() {
    if (commentLoaded.value || !props.ticketId) {
      return;
    }
    getTicketComments(props.ticketId).then((response) => {
      commentList.value = response.data || [];
      commentLoaded.value = true;
    });
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
    if (tabName === 'comments') {
      loadComments();
    }
    if (tabName === 'history') {
      loadTimeline();
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

  function formatPercent(value) {
    const numeric = Number(value || 0);
    return `${(numeric * 100).toFixed(1)}%`;
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

  function resolveTicketDetailUrl(row) {
    return row.ticketUrl || row.ticket_url || row.detailUrl || row.detail_url || '';
  }

  function openExternalTicket(row) {
    const url = resolveTicketDetailUrl(row);
    if (url) {
      window.open(url, '_blank');
    }
  }

  function openSystemTicketDetail(row) {
    const ticketId = Number(row?.ticketId || row?.ticket_id || 0);
    if (!ticketId) {
      return;
    }
    const route = router.resolve({ name: 'TicketDetail', params: { ticketId } });
    window.open(route.href || `/ticket/detail/${ticketId}`, '_blank');
  }

  watch(
    () => props.ticketId,
    () => {
      activeTab.value = 'overview';
      descriptionExpanded.value = true;
      translationExpanded.value = true;
      commentList.value = [];
      commentLoaded.value = false;
      timeline.value = {};
      timelineLoaded.value = false;
      loadDetail();
    },
    { immediate: true }
  );
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

  .section-title {
    margin-bottom: 8px;
    font-weight: 600;
    color: #303133;
  }

  .section-title--with-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .section-content {
    padding: 12px;
    border: 1px solid #ebeef5;
    border-radius: 6px;
    background: #fafafa;
  }

  .section-content--collapsed {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .translation-block {
    margin-top: 12px;
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

  .similar-item,
  .comment-item {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    padding: 12px 0;
    border-bottom: 1px solid #ebeef5;
  }

  .similar-title {
    font-weight: 600;
  }

  .similar-actions {
    flex: 0 0 auto;
    white-space: nowrap;
  }

  .comment-meta {
    display: flex;
    gap: 12px;
    margin-bottom: 6px;
    color: #606266;
  }

  .pre-line {
    white-space: pre-wrap;
    word-break: break-word;
  }

  .muted {
    color: #606266;
  }

  .mb12 {
    margin-bottom: 12px;
  }
</style>
