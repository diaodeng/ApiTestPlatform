<script setup name="TicketSimilarPanel">
  import { useRouter } from 'vue-router';

  /**
   * 相似工单共享展示面板。
   * 工单内容相似与处理案例相似的统一展示区域，供列表详情弹窗和独立详情页复用。
   * 写操作通过 allowBindIssue 控制是否展示“归入同一问题”入口；系统详情、飞书详情为只读跳转，始终展示。
   */
  const props = defineProps({
    // 工单内容相似（symptom scope）候选
    symptomTickets: {
      type: Array,
      default: () => [],
    },
    // 处理案例相似（case scope）候选
    caseTickets: {
      type: Array,
      default: () => [],
    },
    similarLoading: {
      type: Boolean,
      default: false,
    },
    // 相似接口返回的向量状态信息，非空时以警告条展示
    similarError: {
      type: String,
      default: '',
    },
    // 相似查询状态：idle/loading/ready/pending/failed 等
    similarStatus: {
      type: String,
      default: 'idle',
    },
    // 是否允许“归入同一问题”写操作；只读入口传 false
    allowBindIssue: {
      type: Boolean,
      default: false,
    },
    // 归因请求进行中状态，用于按钮 loading
    issueActionLoading: {
      type: Boolean,
      default: false,
    },
  });

  const emit = defineEmits(['bind-issue']);
  const router = useRouter();

  /**
   * 解析外部工单详情链接，优先工单链接字段并按同步摘要兜底。
   * @param {object} ticketRow 工单行或相似候选
   * @returns {string} 外部链接
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
   * 打开外部系统工单详情链接。
   * @param {object} item 相似候选
   */
  function openExternalTicket(item) {
    const url = resolveTicketDetailUrl(item);
    if (url) {
      window.open(url, '_blank', 'noopener');
    }
  }

  /**
   * 打开系统内独立工单详情页。
   * @param {object} item 相似候选
   */
  function openSystemTicketDetail(item) {
    const ticketId = Number(item?.ticketId || item?.ticket_id || 0);
    if (!Number.isFinite(ticketId) || ticketId <= 0) return;
    const resolved = router.resolve({ name: 'TicketDetail', params: { ticketId } });
    window.open(resolved.href || `/ticket/detail/${ticketId}`, '_blank');
  }

  /**
   * 综合相似度百分比文案。
   * @param {number|string} value 相似度分数
   * @returns {string} 百分比文案
   */
  function formatPercent(value) {
    const numeric = Number(value || 0);
    return `${(numeric * 100).toFixed(1)}%`;
  }

  /**
   * 处理案例状态文案。
   * @param {string} value 案例状态编码
   * @returns {string} 状态文案
   */
  function formatCaseStatus(value) {
    const labels = { draft: '案例草稿', verified: '已验证案例', rejected: '已驳回' };
    return labels[String(value || '')] || String(value || '');
  }
</script>

<template>
  <div v-loading="similarLoading" class="similar-panel">
    <el-alert
      v-if="similarError && !similarLoading"
      type="warning"
      show-icon
      :closable="false"
      class="mb12"
      :title="similarError"
    />
    <!-- 有状态提示时仍渲染结果区：向量 stale/missing 等提示不应隐藏已召回的候选 -->
    <template v-if="!similarLoading">
      <el-card shadow="never" class="similar-card">
        <template #header>工单内容相似</template>
        <el-empty
          v-if="similarStatus === 'pending' && !symptomTickets.length"
          description="相似工单正在生成，请稍后刷新"
        />
        <el-empty v-else-if="!symptomTickets.length" description="暂无内容相似工单" />
        <div v-for="item in symptomTickets" :key="`symptom-${item.ticketId}`" class="similar-item">
          <div>
            <div class="similar-title">{{ item.ticketNo || '-' }} {{ item.title || '-' }}</div>
            <div class="similar-meta">
              <span>相似度 {{ formatPercent(item.score) }}</span>
              <span>{{ item.moduleName || '-' }}</span>
              <span>{{ item.status || '-' }}</span>
            </div>
            <div v-if="item.matchReasons?.length || item.conflicts?.length" class="similar-meta">
              <span v-if="item.matchReasons?.length">命中：{{ item.matchReasons.join('、') }}</span>
              <span v-if="item.conflicts?.length">冲突：{{ item.conflicts.join('、') }}</span>
            </div>
          </div>
          <div class="similar-actions">
            <el-button link type="primary" @click="openSystemTicketDetail(item)">系统详情</el-button>
            <el-button v-if="resolveTicketDetailUrl(item)" link type="primary" @click="openExternalTicket(item)">
              飞书详情
            </el-button>
            <el-button
              v-if="allowBindIssue"
              link
              type="success"
              :loading="issueActionLoading"
              @click="emit('bind-issue', item)"
              v-hasPermi="['ticket:issue:bind']"
            >
              归入同一问题
            </el-button>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="similar-card similar-card--case">
        <template #header>处理案例相似</template>
        <el-empty v-if="!caseTickets.length" description="暂无处理案例" />
        <div v-for="item in caseTickets" :key="`case-${item.ticketId}`" class="similar-item">
          <div>
            <div class="similar-title">{{ item.ticketNo || '-' }} {{ item.title || '-' }}</div>
            <div class="similar-meta">
              <span>相似度 {{ formatPercent(item.score) }}</span>
              <span>{{ formatCaseStatus(item.caseStatus) }}</span>
            </div>
            <div class="similar-meta">根因：{{ item.rootCause || '-' }}</div>
          </div>
          <div class="similar-actions">
            <el-button link type="primary" @click="openSystemTicketDetail(item)">系统详情</el-button>
          </div>
        </div>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
  .similar-panel {
    min-height: 160px;
  }

  .similar-card--case {
    margin-top: 16px;
  }

  .similar-item {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    padding: 10px 0;
    border-bottom: 1px solid #ebeef5;
  }

  .similar-item:last-child {
    border-bottom: 0;
  }

  .similar-title {
    font-weight: 600;
    color: #303133;
  }

  .similar-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 16px;
    margin-top: 4px;
    color: #909399;
    font-size: 12px;
  }

  .similar-actions {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    gap: 0;
    white-space: nowrap;
  }
</style>
