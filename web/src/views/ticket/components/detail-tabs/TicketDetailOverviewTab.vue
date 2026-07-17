<script setup name="TicketDetailOverviewTab">
  import { computed, getCurrentInstance, ref, watch } from 'vue';
  import { useRouter } from 'vue-router';
  import { bindTicketIssueFromSimilar, getTicket } from '@/api/ticket/ticket';

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

  const emit = defineEmits([
    'run-ai',
    'refresh-ai',
    'open-ai-history',
    'open-ai-repo-mapping',
    'open-project-vendor-map',
    'changed',
  ]);
  const { proxy } = getCurrentInstance();
  const router = useRouter();

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
  const latestSnapshot = computed(
    () => detail.value.latestSnapshot || detail.value.snapshots?.[0] || null
  );
  const latestSimilarTickets = computed(() => (detail.value.similarTickets || []).slice(0, 3));

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
    return getTicket(resolvedTicketId.value)
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
   * 打开外部工单详情链接。
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
        <el-descriptions :column="2" border>
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
          <el-descriptions-item label="摘要" :span="2">{{
            latestSnapshot?.summary || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="根因" :span="2">{{
            latestSnapshot?.rootCause || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="解决方案" :span="2">{{
            latestSnapshot?.solution || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="预防建议" :span="2">{{
            latestSnapshot?.prevention || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="风险说明" :span="2">{{
            latestSnapshot?.risk || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="负责人" :span="2">{{
            latestSnapshot?.owner || '-'
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
      <el-card shadow="never">
        <template #header>相似工单</template>
        <el-empty v-if="!latestSimilarTickets.length" description="暂无相似工单" />
        <div v-for="item in latestSimilarTickets" :key="item.ticketId" class="similar-item">
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
              @click="bindSimilarIssue(item)"
              v-hasPermi="['ticket:issue:bind']"
            >
              归入同一问题
            </el-button>
          </div>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>

<style scoped>
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
