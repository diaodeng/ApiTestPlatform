<script setup name="TicketDetailOverviewTab">
  import { computed, getCurrentInstance, ref, watch } from 'vue';
  import { bindTicketIssueFromSimilar, getTicketSummary } from '@/api/ticket/ticket';
  import TicketSimilarPanel from '../detail-shared/TicketSimilarPanel.vue';

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
    similarTickets: {
      type: Array,
      default: () => [],
    },
    symptomTickets: {
      type: Array,
      default: () => [],
    },
    caseTickets: {
      type: Array,
      default: () => [],
    },
    similarLoading: {
      type: Boolean,
      default: false,
    },
    similarError: {
      type: String,
      default: '',
    },
    similarStatus: {
      type: String,
      default: 'idle',
    },
    // 当前工单自身的相似处理案例摘要
    similarityCase: {
      type: Object,
      default: null,
    },
    // 案例状态变更请求进行中
    caseActionLoading: {
      type: Boolean,
      default: false,
    },
  });

  const emit = defineEmits([
    'run-ai',
    'refresh-ai',
    'open-ai-history',
    'open-ai-repo-mapping',
    'open-project-vendor-map',
    'changed',
    'case-action',
  ]);
  const { proxy } = getCurrentInstance();

  const loading = ref(false);
  const detail = ref({});
  const issueActionLoading = ref(false);
  const hasExternalDetail = computed(() =>
    Boolean(props.detail?.ticketId || props.detail?.ticket_id)
  );
  const resolvedTicketId = computed(() => {
    const ticketId = Number(props.ticketId || props.detail?.ticketId || props.detail?.ticket_id);
    return Number.isFinite(ticketId) && ticketId > 0 ? ticketId : undefined;
  });
  const latestAiAnalysisTask = computed(() => detail.value.latestAiAnalysis || null);
  const aiTokenSummary = computed(() => detail.value.aiTokenSummary || null);
  const latestSnapshot = computed(
    () => detail.value.latestSnapshot || detail.value.snapshots?.[0] || null
  );
  const latestConclusion = computed(() => ({
    summary: latestSnapshot.value?.summary || latestAiAnalysisTask.value?.analysisSummary || '',
    rootCause: latestSnapshot.value?.rootCause || latestAiAnalysisTask.value?.rootCause || '',
    solution:
      latestSnapshot.value?.solution || latestAiAnalysisTask.value?.fixSuggestion || '',
    prevention: latestSnapshot.value?.prevention || '',
    risk: latestSnapshot.value?.risk || '',
    owner: latestSnapshot.value?.owner || '',
  }));
  const latestSimilarTickets = computed(() => (props.similarTickets || []).slice(0, 5));
  const symptomSimilarTickets = computed(() =>
    (props.symptomTickets?.length ? props.symptomTickets : latestSimilarTickets.value.filter((item) => item.matchType !== 'case')).slice(0, 5)
  );
  const caseSimilarTickets = computed(() =>
    (props.caseTickets?.length ? props.caseTickets : latestSimilarTickets.value.filter((item) => item.matchType === 'case')).slice(0, 5)
  );

  /**
   * 加载概览 tab 需要的工单快照、AI 任务和相似工单数据。
   * @returns {Promise<void>} 数据加载完成 Promise。
   */
  function loadOverview() {
    if (hasExternalDetail.value) {
      detail.value = props.detail || {};
      return Promise.resolve();
    }
    if (!resolvedTicketId.value) return Promise.resolve();
    loading.value = true;
    return getTicketSummary(resolvedTicketId.value)
      .then((response) => {
        detail.value = response.data || {};
      })
      .finally(() => {
        loading.value = false;
      });
  }

  /**
   * 刷新父详情 AI 数据并重新加载概览数据。
   * @returns {void}
   */
  function refreshAiData() {
    emit('refresh-ai');
    loadOverview();
  }

  /**
   * 数据变更后刷新当前 tab，外部已提供详情时交给详情父组件刷新。
   * @returns {Promise<void>} 刷新完成 Promise。
   */
  function refreshOverviewAfterChanged() {
    if (hasExternalDetail.value) {
      emit('changed');
      return Promise.resolve();
    }
    return loadOverview().then(() => {
      emit('changed');
    });
  }

  /**
   * 获取 AI 任务状态标签类型。
   * @param {string} value AI 任务状态。
   * @returns {string} Element Plus 标签类型。
   */
  function getAiStatusTagType(value) {
    const status = String(value || '');
    if (status === 'success') return 'success';
    if (status === 'failed') return 'danger';
    if (status === 'running') return 'warning';
    if (status === 'created') return 'info';
    return 'info';
  }

  /**
   * 获取 AI 任务状态展示文案。
   * @param {string} value AI 任务状态。
   * @returns {string} 状态文案。
   */
  function getAiStatusLabel(value) {
    const status = String(value || '');
    if (status === 'success') return '成功';
    if (status === 'failed') return '失败';
    if (status === 'running') return '执行中';
    if (status === 'created') return '待执行';
    return status || '-';
  }

  /**
   * 格式化 Token 数量。
   * @param {number|string|null|undefined} value Token 数值。
   * @returns {string} 展示文本。
   */
  function formatTokenCount(value) {
    return Number.isFinite(Number(value)) ? String(Number(value)) : '-';
  }

  /**
   * 将当前工单与相似工单归入同一问题（共享相似面板回传事件）。
   * @param {object} item 相似工单。
   * @returns {void}
   */
  function bindSimilarIssue(item) {
    const similarTicketId = Number(item?.ticketId || item?.ticket_id);
    if (!resolvedTicketId.value || !similarTicketId) {
      proxy.$modal.msgWarning('相似工单ID无效，无法归因');
      return;
    }
    proxy.$modal
      .confirm(`是否确认将当前工单与 ${item.ticketNo || similarTicketId} 归入同一问题？`)
      .then(() => {
        issueActionLoading.value = true;
        return bindTicketIssueFromSimilar(resolvedTicketId.value, {
          similarTicketId,
          confidence: item.score,
          relationType: 'similar',
        });
      })
      .then(() => {
        proxy.$modal.msgSuccess('相似工单归因已确认');
        refreshOverviewAfterChanged();
      })
      .finally(() => {
        issueActionLoading.value = false;
      });
  }

  watch(
    () => [props.ticketId, props.detail],
    () => {
      if (hasExternalDetail.value) {
        detail.value = props.detail || {};
        return;
      }
      detail.value = {};
      if (props.active) loadOverview();
    },
    { immediate: true, deep: true }
  );

  watch(
    () => props.active,
    (active) => {
      if (active) loadOverview();
    },
    { immediate: true }
  );
</script>

<template>
  <el-row v-loading="loading" :gutter="16">
    <el-col :span="16">
      <el-card shadow="never" class="mb16">
        <template #header>
          <div class="panel-header">
            <span>最新AI结论</span>
            <el-button-group>
              <el-button
                type="primary"
                @click="emit('run-ai')"
                v-hasPermi="['ticket:ai:analysis:run']"
              >
                发起AI分析
              </el-button>
              <el-button
                type="info"
                plain
                @click="refreshAiData"
                v-hasPermi="['ticket:ai:analysis:list']"
              >
                刷新AI数据
              </el-button>
              <el-button @click="emit('open-ai-history')" v-hasPermi="['ticket:ai:analysis:list']">
                查看任务历史
              </el-button>
              <el-button
                type="warning"
                plain
                @click="emit('open-ai-repo-mapping')"
                v-hasPermi="['ticket:ai:mapping:add']"
              >
                管理映射
              </el-button>
              <el-button
                type="success"
                plain
                @click="emit('open-project-vendor-map')"
                v-hasPermi="['ticket:logpull:config']"
              >
                商家映射
              </el-button>
            </el-button-group>
          </div>
        </template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="最新执行状态">
            <el-tag
              v-if="latestAiAnalysisTask?.status"
              :type="getAiStatusTagType(latestAiAnalysisTask.status)"
            >
              {{ getAiStatusLabel(latestAiAnalysisTask.status) }}
            </el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="快照版本">
            {{ latestSnapshot?.version || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="快照时间">
            {{ parseTime(latestSnapshot?.createTime) || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="创建人">
            {{ latestSnapshot?.createdByName || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="AI任务数">
            {{ aiTokenSummary ? formatTokenCount(aiTokenSummary.taskCount) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="成功任务数">
            {{ aiTokenSummary ? formatTokenCount(aiTokenSummary.successTaskCount) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="输入 Token">
            {{ aiTokenSummary ? formatTokenCount(aiTokenSummary.inputTokenCount) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="输出 Token">
            {{ aiTokenSummary ? formatTokenCount(aiTokenSummary.outputTokenCount) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="总 Token">
            {{ aiTokenSummary ? formatTokenCount(aiTokenSummary.totalTokenCount) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="摘要" :span="3">
            <div class="pre-wrap-text">{{ latestConclusion.summary || '-' }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="根因" :span="3">
            <div class="pre-wrap-text">{{ latestConclusion.rootCause || '-' }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="解决方案" :span="3">
            <div class="pre-wrap-text">{{ latestConclusion.solution || '-' }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="预防建议" :span="3">
            <div class="pre-wrap-text">{{ latestConclusion.prevention || '-' }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="风险说明" :span="3">
            <div class="pre-wrap-text">{{ latestConclusion.risk || '-' }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="负责人" :span="3">{{
            latestConclusion.owner || '-'
          }}</el-descriptions-item>
        </el-descriptions>
        <el-alert
          v-if="latestAiAnalysisTask?.errorMessage"
          type="error"
          show-icon
          :title="latestAiAnalysisTask.errorMessage"
          class="mt16"
        />
      </el-card>
    </el-col>
    <el-col :span="8">
      <TicketSimilarPanel
        :symptom-tickets="symptomSimilarTickets"
        :case-tickets="caseSimilarTickets"
        :similar-loading="similarLoading"
        :similar-error="similarError"
        :similar-status="similarStatus"
        :allow-bind-issue="true"
        :issue-action-loading="issueActionLoading"
        :similarity-case="similarityCase"
        :allow-case-action="true"
        :case-action-loading="caseActionLoading"
        @bind-issue="bindSimilarIssue"
        @case-action="(status) => emit('case-action', status)"
      />
    </el-col>
  </el-row>
</template>

<style scoped>
  /* AI 结论类文本保留换行与空格，避免多段文案挤成一行 */
  .pre-wrap-text {
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.65;
  }
</style>
