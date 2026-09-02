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
        <el-button
          v-hasPermi="['ticket:issue:bind']"
          type="primary"
          plain
          icon="Connection"
          @click="openIssueBindDialog"
        >
          {{ detail.issueId ? '更换问题实例' : '关联问题实例' }}
        </el-button>
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
        <div v-loading="similarLoading" class="similar-loading-wrap">
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
            <section class="similar-group">
              <h4>工单内容相似</h4>
              <el-empty v-if="!symptomTickets.length" description="暂无内容相似工单" />
              <div v-for="item in symptomTickets" :key="`symptom-${item.ticketId}`" class="similar-item">
                <div>
                  <div class="similar-title">{{ item.ticketNo || '-' }} {{ item.title || '-' }}</div>
                  <div class="detail-meta">
                    <span>相似度 {{ formatPercent(item.score) }}</span>
                    <span>{{ item.moduleName || '-' }}</span>
                    <span>{{ item.status || '-' }}</span>
                  </div>
                  <div v-if="item.matchReasons?.length || item.conflicts?.length" class="detail-meta">
                    <span v-if="item.matchReasons?.length">命中：{{ item.matchReasons.join('、') }}</span>
                    <span v-if="item.conflicts?.length">冲突：{{ item.conflicts.join('、') }}</span>
                  </div>
                </div>
                <div class="similar-actions">
                  <el-button link type="primary" @click="openSystemTicketDetail(item)">系统详情</el-button>
                  <el-button v-if="resolveTicketDetailUrl(item)" link type="primary" @click="openExternalTicket(item)">
                    飞书详情
                  </el-button>
                </div>
              </div>
            </section>
            <section class="similar-group similar-group--case">
              <h4>处理案例相似</h4>
              <el-empty v-if="!caseTickets.length" description="暂无处理案例" />
              <div v-for="item in caseTickets" :key="`case-${item.ticketId}`" class="similar-item">
                <div>
                  <div class="similar-title">{{ item.ticketNo || '-' }} {{ item.title || '-' }}</div>
                  <div class="detail-meta">
                    <span>相似度 {{ formatPercent(item.score) }}</span>
                    <span>{{ formatCaseStatus(item.caseStatus) }}</span>
                  </div>
                  <div class="detail-meta">根因：{{ item.rootCause || '-' }}</div>
                </div>
                <div class="similar-actions">
                  <el-button link type="primary" @click="openSystemTicketDetail(item)">系统详情</el-button>
                </div>
              </div>
            </section>
          </template>
        </div>
      </el-tab-pane>

      <el-tab-pane label="AI分析" name="collab">
        <TicketDetailCollabTab
          :ticket-id="props.ticketId"
          :active="activeTab === 'collab'"
          :detail="detail"
          :show-ai-history="false"
          @changed="refreshDetailData"
        />
      </el-tab-pane>

      <el-tab-pane label="评论" name="comments">
        <TicketDetailCommentsTab
          :ticket-id="props.ticketId"
          :active="activeTab === 'comments'"
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

    <el-dialog
      v-model="issueBindOpen"
      :title="detail.issueId ? '更换问题实例' : '关联问题实例'"
      width="720px"
      append-to-body
      destroy-on-close
      @closed="resetIssueBindForm"
    >
      <el-alert
        v-if="detail.issueId"
        type="warning"
        :closable="false"
        show-icon
        class="mb12"
        :title="`当前已归属问题：${detail.issueNo || detail.issueId} ${detail.issueTitle || ''}`"
      />
      <el-form :model="issueBindForm" label-width="110px">
        <el-form-item label="目标问题实例" required>
          <el-select
            v-model="issueBindForm.issueId"
            filterable
            remote
            reserve-keyword
            clearable
            placeholder="输入问题编号或标题搜索"
            :remote-method="searchIssueBindOptions"
            :loading="issueBindOptionLoading"
            style="width: 100%"
            @focus="searchIssueBindOptions('')"
          >
            <el-option
              v-for="item in issueBindOptions"
              :key="item.issueId"
              :label="formatIssueBindOption(item)"
              :value="item.issueId"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="归因类型">
          <el-select v-model="issueBindForm.relationType" style="width: 100%">
            <el-option label="手工归因" value="manual" />
            <el-option label="主问题" value="primary" />
            <el-option label="重复工单" value="duplicate" />
            <el-option label="相关工单" value="related" />
          </el-select>
        </el-form-item>
        <el-form-item label="已确认">
          <el-switch v-model="issueBindForm.confirmed" />
        </el-form-item>
        <el-form-item label="归因说明">
          <el-input
            v-model="issueBindForm.remark"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="可选，说明本次归因依据"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="issueBindSubmitting" @click="issueBindOpen = false">取消</el-button>
        <el-button
          type="primary"
          :loading="issueBindSubmitting"
          :disabled="issueBindSubmitting"
          @click="submitIssueBind"
        >
          确认关联
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
  import { computed, getCurrentInstance, ref, watch } from 'vue';
  import { useRouter } from 'vue-router';
  import {
    bindTicketIssue,
    getTicketSummary,
    getTicketSimilarTickets,
    getTicketTimeline,
    listTicketIssues,
    updateTicketSimilarityCaseStatus,
  } from '@/api/ticket/ticket';
  import TicketDetailCollabTab from './detail-tabs/TicketDetailCollabTab.vue';
  import TicketDetailCommentsTab from './detail-tabs/TicketDetailCommentsTab.vue';
  import { useWorkflow } from '../hooks/useWorkflow';

  const props = defineProps({
    ticketId: {
      type: [Number, String],
      required: true,
    },
  });

  const { proxy } = getCurrentInstance();
  const router = useRouter();
  // 工单状态选项：合并自定义工作流状态节点，用于把状态 code 转成状态名称展示
  const currentTicketStatus = ref('');
  const { ticketStatusOptions, getStatusTagType, loadWorkflowConfig } = useWorkflow(currentTicketStatus);
  const loading = ref(false);
  const activeTab = ref('overview');
  const descriptionExpanded = ref(true);
  const translationExpanded = ref(true);
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
  // 问题实例关联弹窗状态
  const issueBindOpen = ref(false);
  const issueBindSubmitting = ref(false);
  const issueBindOptionLoading = ref(false);
  const issueBindOptions = ref([]);
  const issueBindForm = ref(createDefaultIssueBindForm());

  /**
   * 构建问题实例关联表单默认值。
   * 已有问题归属时，预填当前归属的问题实例和归因类型，方便直接查看或换绑。
   */
  function createDefaultIssueBindForm() {
    return {
      issueId: undefined,
      relationType: 'manual',
      confirmed: true,
      remark: '',
    };
  }

  /**
   * 拼接问题实例下拉选项的展示文案：编号 + 标题 + 状态。
   */
  function formatIssueBindOption(item) {
    return [item.issueNo || item.issueId, item.title, item.status ? `【${item.status}】` : '']
      .filter(Boolean)
      .join(' ');
  }

  /**
   * 打开关联问题实例弹窗，并预置当前归属问题为第一个选项。
   */
  function openIssueBindDialog() {
    if (!detail.value.ticketId) {
      proxy.$modal.msgWarning('请先等待工单详情加载完成');
      return;
    }
    issueBindForm.value = {
      ...createDefaultIssueBindForm(),
      relationType: detail.value.issueRelationType || 'manual',
      confirmed: detail.value.issueConfirmed !== false,
    };
    // 当前已归属的问题始终保留在选项中，避免搜索结果中不含当前问题时丢失显示
    issueBindOptions.value = detail.value.issueId
      ? [{
          issueId: detail.value.issueId,
          issueNo: detail.value.issueNo,
          title: detail.value.issueTitle,
          status: detail.value.issueStatus,
        }]
      : [];
    issueBindOpen.value = true;
  }

  /**
   * 远程搜索问题实例选项，按关键字匹配编号、标题和摘要。
   */
  function searchIssueBindOptions(keyword) {
    const text = String(keyword || '').trim();
    if (!text) {
      return Promise.resolve(issueBindOptions.value);
    }
    issueBindOptionLoading.value = true;
    return listTicketIssues({
      keyword: text,
      projectId: detail.value.projectId || undefined,
      moduleId: detail.value.moduleId || undefined,
      pageNum: 1,
      pageSize: 20,
    })
      .then((response) => {
        const rows = response.rows || response.data || [];
        // 搜索结果中保留当前已归属的问题实例，保证换绑场景下选项不丢失
        const current = issueBindOptions.value.find(
          (item) => String(item.issueId) === String(detail.value.issueId)
        );
        issueBindOptions.value =
          current && !rows.some((item) => String(item.issueId) === String(current.issueId))
            ? [current, ...rows]
            : rows;
        return issueBindOptions.value;
      })
      .finally(() => {
        issueBindOptionLoading.value = false;
      });
  }

  /**
   * 重置关联问题实例弹窗状态。
   */
  function resetIssueBindForm() {
    issueBindForm.value = createDefaultIssueBindForm();
    issueBindOptions.value = [];
    issueBindSubmitting.value = false;
    issueBindOptionLoading.value = false;
  }

  /**
   * 提交工单与问题实例的关联。
   * 已有问题归属且选择了不同问题时需要二次确认；同一问题重复提交幂等成功。
   */
  function submitIssueBind() {
    const targetIssueId = issueBindForm.value.issueId;
    if (!targetIssueId) {
      proxy.$modal.msgWarning('请选择目标问题实例');
      return;
    }
    const currentIssueId = detail.value.issueId;
    const execute = () => {
      issueBindSubmitting.value = true;
      return bindTicketIssue(detail.value.ticketId, {
        issueId: targetIssueId,
        relationType: issueBindForm.value.relationType || 'manual',
        confirmed: issueBindForm.value.confirmed !== false,
        remark: String(issueBindForm.value.remark || '').trim() || undefined,
      })
        .then(() => {
          proxy.$modal.msgSuccess(currentIssueId ? '问题实例已更换' : '问题实例关联成功');
          issueBindOpen.value = false;
          loadDetail();
        })
        .finally(() => {
          issueBindSubmitting.value = false;
        });
    };
    if (currentIssueId && String(currentIssueId) !== String(targetIssueId)) {
      proxy.$modal.confirm('当前工单已有问题归属，是否确认更换为所选问题？').then(execute);
      return;
    }
    execute();
  }

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

  function confirmSimilarCase(item) {
    const ticketId = item?.ticketId || item?.ticket_id;
    if (!ticketId) return;
    proxy.$modal.confirm('确认将该工单沉淀为可复用处理案例吗？').then(() => {
      return updateTicketSimilarityCaseStatus(ticketId, {
        status: 'verified',
        remark: '详情页人工确认案例可复用',
      });
    }).then(() => {
      proxy.$modal.msgSuccess('案例已确认');
      refreshDetailData();
    }).catch(() => {});
  }

  function formatPercent(value) {
    const numeric = Number(value || 0);
    return `${(numeric * 100).toFixed(1)}%`;
  }

  function formatCaseStatus(value) {
    const labels = { draft: '案例草稿', verified: '已验证案例', rejected: '已驳回' };
    return labels[String(value || '')] || String(value || '');
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
      requestGeneration += 1;
      activeTab.value = 'overview';
      descriptionExpanded.value = true;
      translationExpanded.value = true;
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

  .similar-loading-wrap {
    min-height: 160px;
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
