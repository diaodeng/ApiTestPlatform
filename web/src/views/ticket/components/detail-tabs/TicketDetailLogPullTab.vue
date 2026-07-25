<script setup name="TicketDetailLogPullTab">
  import {
    computed,
    getCurrentInstance,
    nextTick,
    onBeforeUnmount,
    onMounted,
    ref,
    watch,
  } from 'vue';
  import LogPullConfigFields from '@/components/ticket/LogPullConfigFields.vue';
  import LogPullNotifyConfigFields from '@/components/ticket/LogPullNotifyConfigFields.vue'
import LogViewerDialog from '@/components/ticket/LogViewerDialog.vue';
  import { getTicket } from '@/api/ticket/ticket';
  import {
    getLogPullStatusTagType,
    getOptionLabel,
    logPullDataTypeOptions,
    logPullStatusOptions,
    logPullStorageModeOptions,
  } from '../../constants';
  import { useLogViewer } from '../../hooks/useLogViewer';
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

  const emit = defineEmits(['changed']);
  const { proxy } = getCurrentInstance();
  const currentTicketId = ref();
  const detail = ref({});
  const detailRef = computed(() => detail.value || {});
  const detailOpenRef = computed(() => Boolean(props.active));
  const hasExternalDetail = computed(() =>
    Boolean(props.detail?.ticketId || props.detail?.ticket_id)
  );
  const resolvedTicketId = computed(() => {
    const ticketId = Number(props.ticketId || props.detail?.ticketId || props.detail?.ticket_id);
    return Number.isFinite(ticketId) && ticketId > 0 ? ticketId : undefined;
  });

  const {
    agentOptions,
    providerOptions,
    vendorOptions,
    environmentOptions,
    parameterExamples,
    pushOptions,
    loadVendorOptions,
    loadProjectVendorMapOptions,
    loadProviderOptions,
    loadPushOptions,
    loadAgentOptions,
    getProjectVendorNo,
  } = useOptions();

  /**
   * 通知详情主组件刷新基础信息和列表。
   * @returns {Promise<void>} 通知完成 Promise。
   */
  function emitChanged() {
    emit('changed');
    return Promise.resolve();
  }

  /**
   * 加载日志拉取 tab 所需的工单详情元信息。
   * @returns {Promise<void>} 详情加载完成 Promise。
   */
  function loadTicketDetail() {
    if (hasExternalDetail.value) {
      detail.value = props.detail || {};
      return Promise.resolve();
    }
    if (!currentTicketId.value) return Promise.resolve();
    return getTicket(currentTicketId.value).then((response) => {
      detail.value = response.data || {};
    });
  }

  /**
   * 刷新日志 tab 本地详情并通知父详情刷新顶部信息。
   * @returns {Promise<void>} 刷新完成 Promise。
   */
  function refreshTicketDetailAndNotify() {
    if (hasExternalDetail.value) {
      emitChanged();
      return Promise.resolve();
    }
    return Promise.all([loadTicketDetail(), emitChanged()]).then(() => undefined);
  }

  const {
    logPullLoading,
    logPullSubmitting,
    logPullActionLoading,
    logPullSubmitOpen,
    logPullContentOpen,
    logPullList,
    logPullTotal,
    logPullForm,
    logPullQuery,
    logPullWrapEnabled,
    logPullAutoRefreshing,
    selectedLogPullRecord,
    activeLogPullStatuses,
    logViewerTicketMeta,
    logViewerSearching,
    logViewerHits,
    logViewerContext,
    logViewerErrorSummary,
    logViewerResultViewMode,
    logViewerContextViewMode,
    logViewerHighlightText,
    logViewerHighlightKeywords,
    logViewerHighlightSummary,
    logViewerForm,
    resetStoreSelection,
    resetLogPullForm,
    openLogPullSubmitDialog,
    stopLogPullAutoRefresh,
    loadLogPullList,
    submitLogPull,
    deleteLogPull,
    retryLogPull,
    redownloadLogPull,
    handleCopyLogPull,
    getLogPullOriginalDownloadUrl,
    getLogPullArchiveDownloadUrl,
    getLogPullArchiveDisplayText,
    formatLogPullParameter,
    copyLogPullOriginalDownloadUrl,
    copyLogPullArchiveDownloadUrl,
    downloadLogPullArchive,
    downloadLogPullOriginal,
    getLogViewerDownloadProgress,
    openLogViewerFromPullRecord,
    handleLogPullDialogClosed,
    searchLogViewerInFile,
    clearLogViewerFileScope,
    captureLogViewerHighlight,
    clearLogViewerSelectionHighlight,
    updateLogViewerHighlightKeywords,
    clearLogViewerHighlight,
    setLogViewerPanelMode,
    searchLogViewerKeyword,
    loadLogViewerErrors,
    selectLogViewerHit,
    pageLogViewerContext,
  } = useLogViewer(proxy, currentTicketId, {
    detail: detailRef,
    detailOpen: detailOpenRef,
    getList: emitChanged,
    refreshDetail: refreshTicketDetailAndNotify,
    applyProjectVendorMapping,
  });

  const logPullRules = {
    vendorId: [{ required: true, message: 'vendorId不能为空', trigger: 'blur' }],
    storeId: [{ required: true, message: 'storeId不能为空', trigger: 'blur' }],
    posNo: [{ required: true, message: 'posNo不能为空', trigger: 'blur' }],
  };
  const logViewerContextBlockRef = ref(null);
  const logViewerHighlightName = 'ticket-log-context-highlight';
  const logViewerNativeHighlightSupported = computed(() => supportsNativeLogViewerHighlight());
  const logViewerFileOptions = computed(() => {
    const files = new Set();
    logViewerHits.value.forEach((item) => {
      const file = String(item?.file || '').trim();
      if (file) files.add(file);
    });
    const scopedFile = String(logViewerForm.value.file || '').trim();
    if (scopedFile) files.add(scopedFile);
    return Array.from(files).sort();
  });
  const logViewerContextDisplayLines = computed(() => {
    const lines = logViewerContext.value?.lines || [];
    return lines.map((item) => ({
      file: item.file || logViewerContext.value?.file || '',
      line: item.line,
      paddedLine: `${String(item.line).padStart(6, ' ')}  `,
      content: item.content || '',
      // 原生高亮只是不拆分 mark，仍需保留文本节点供上下文内容和 Range 高亮渲染。
      parts: logViewerNativeHighlightSupported.value
        ? [{ text: item.content || '', highlight: false }]
        : splitLogViewerHighlightParts(item.content || ''),
    }));
  });
  const logViewerResultTableHeight = computed(() =>
    logViewerResultViewMode.value === 'fullscreen'
      ? 'calc(100vh - 170px)'
      : !logViewerContext.value || logViewerContextViewMode.value === 'minimized'
        ? 'calc(100vh - 250px)'
        : 320
  );
  const logViewerDialogTitle = computed(() => {
    const ticketNo = String(logViewerTicketMeta.value?.ticketNo || '').trim();
    const ticketTitle = String(logViewerTicketMeta.value?.title || '').trim();
    if (ticketNo && ticketTitle) return `日志查看 - ${ticketNo} - ${ticketTitle}`;
    if (ticketNo) return `日志查看 - ${ticketNo}`;
    if (ticketTitle) return `日志查看 - ${ticketTitle}`;
    return '日志查看';
  });

  /**
   * 根据工单项目映射预填日志拉取商家。
   * @param {number|string} projectId 工单项目 ID。
   * @returns {void}
   */
  function applyProjectVendorMapping(projectId) {
    const vendorNo = getProjectVendorNo(projectId);
    if (!vendorNo) return;
    logPullForm.value.vendorId = String(vendorNo);
    resetStoreSelection(logPullForm.value, logPullForm.value.vendorId);
  }

  /**
   * 打开云端搜索日志查看器。
   * @param {object} row 日志拉取记录行数据。
   * @returns {void}
   */
  function handleOpenLogViewer(row) {
    const ticketMeta = {
      ticketId: row?.ticketId || currentTicketId.value || detail.value?.ticketId || 0,
      ticketNo: row?.ticketNo || detail.value?.ticketNo || '',
      title: row?.title || detail.value?.title || '',
    }
    if (!row?.id) {
      proxy.$modal.msgWarning('当前日志记录缺少记录ID，无法查看日志')
      return
    }
    selectedLogPullRecord.value = {
      ...(row || {}),
      ticketId: ticketMeta.ticketId,
      ticketNo: ticketMeta.ticketNo,
      title: ticketMeta.title,
    }
    logPullContentOpen.value = true
  }

  /**
   * 判断当前浏览器是否支持 CSS Highlight API。
   * @returns {boolean} 支持时返回 true。
   */
  function supportsNativeLogViewerHighlight() {
    return Boolean(
      window.CSS?.highlights &&
      typeof window.Highlight === 'function' &&
      typeof window.Range === 'function'
    );
  }

  /**
   * 清理日志上下文区域注册到浏览器的原生高亮。
   * @returns {void}
   */
  function clearNativeLogViewerHighlights() {
    if (!supportsNativeLogViewerHighlight()) return;
    window.CSS.highlights.delete(logViewerHighlightName);
  }

  /**
   * 为一个文本节点生成不重叠的关键字高亮 Range。
   * @param {Text} textNode 文本节点。
   * @param {string[]} keywords 已按长度降序排列的高亮词。
   * @returns {Range[]} 当前文本节点中的高亮范围。
   */
  function buildLogViewerHighlightRanges(textNode, keywords) {
    const text = textNode.textContent || '';
    const ranges = [];
    let cursor = 0;
    while (cursor < text.length) {
      let nextMatch = null;
      keywords.forEach((keyword) => {
        const index = text.indexOf(keyword, cursor);
        if (index < 0) return;
        if (
          !nextMatch ||
          index < nextMatch.index ||
          (index === nextMatch.index && keyword.length > nextMatch.keyword.length)
        ) {
          nextMatch = { index, keyword };
        }
      });
      if (!nextMatch) break;
      const range = new window.Range();
      range.setStart(textNode, nextMatch.index);
      range.setEnd(textNode, nextMatch.index + nextMatch.keyword.length);
      ranges.push(range);
      cursor = nextMatch.index + nextMatch.keyword.length;
    }
    return ranges;
  }

  /**
   * 使用 CSS Highlight API 给当前日志上下文做非侵入高亮，避免重建日志文本 DOM。
   * @returns {void}
   */
  function refreshNativeLogViewerHighlights() {
    if (!supportsNativeLogViewerHighlight()) return;
    const block = logViewerContextBlockRef.value;
    const keywords = Array.from(new Set(logViewerHighlightKeywords.value || []))
      .map((item) => String(item || '').trim())
      .filter(Boolean)
      .sort((left, right) => right.length - left.length);
    if (!block || !keywords.length || logViewerContextViewMode.value === 'minimized') {
      clearNativeLogViewerHighlights();
      return;
    }
    const ranges = [];
    block.querySelectorAll('.log-context-line-content').forEach((contentNode) => {
      // 模板中的普通文本由 span 承载，使用 TreeWalker 覆盖所有后代文本节点。
      const walker = document.createTreeWalker(contentNode, window.NodeFilter.SHOW_TEXT);
      let textNode = walker.nextNode();
      while (textNode) {
        ranges.push(...buildLogViewerHighlightRanges(textNode, keywords));
        textNode = walker.nextNode();
      }
    });
    if (!ranges.length) {
      clearNativeLogViewerHighlights();
      return;
    }
    window.CSS.highlights.set(logViewerHighlightName, new window.Highlight(...ranges));
  }

  /**
   * 将日志行按高亮词拆成普通片段和高亮片段。
   * @param {string} content 日志行内容。
   * @returns {Array<object>} 可渲染的片段列表。
   */
  function splitLogViewerHighlightParts(content) {
    const text = String(content || '');
    const keywords = Array.from(new Set(logViewerHighlightKeywords.value || []))
      .map((item) => String(item || '').trim())
      .filter(Boolean)
      .sort((left, right) => right.length - left.length);
    if (!keywords.length) return [{ text, highlight: false }];
    const parts = [];
    let cursor = 0;
    while (cursor < text.length) {
      let nextMatch = null;
      keywords.forEach((keyword, keywordIndex) => {
        const index = text.indexOf(keyword, cursor);
        if (index < 0) return;
        if (
          !nextMatch ||
          index < nextMatch.index ||
          (index === nextMatch.index && keyword.length > nextMatch.keyword.length)
        ) {
          nextMatch = { index, keyword, keywordIndex };
        }
      });
      if (!nextMatch) {
        parts.push({ text: text.slice(cursor), highlight: false });
        break;
      }
      if (nextMatch.index > cursor) {
        parts.push({ text: text.slice(cursor, nextMatch.index), highlight: false });
      }
      parts.push({
        text: text.slice(nextMatch.index, nextMatch.index + nextMatch.keyword.length),
        highlight: true,
        highlightClass: `log-context-highlight-${nextMatch.keywordIndex % 6}`,
      });
      cursor = nextMatch.index + nextMatch.keyword.length;
    }
    return parts.length ? parts : [{ text, highlight: false }];
  }

  /**
   * 读取日志上下文区域内的浏览器选区文本。
   * @returns {string} 选中文本。
   */
  function getLogViewerContextSelectionText() {
    const block = logViewerContextBlockRef.value;
    const selection = window.getSelection?.();
    if (!block || !selection || selection.rangeCount === 0 || selection.isCollapsed) {
      return '';
    }
    if (!block.contains(selection.anchorNode) || !block.contains(selection.focusNode)) {
      return '';
    }
    return selection.toString();
  }

  /**
   * 将日志详情中的选中文本追加为临时高亮词。
   * @returns {void}
   */
  function handleLogViewerContextSelection() {
    const selectedText = getLogViewerContextSelectionText();
    if (!selectedText) return;
    captureLogViewerHighlight(selectedText);
  }

  /**
   * 浏览器选区取消或移出日志详情后清理临时高亮。
   * @returns {void}
   */
  function handleLogViewerDocumentSelectionChange() {
    const block = logViewerContextBlockRef.value;
    const selection = window.getSelection?.();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
      clearLogViewerSelectionHighlight();
      return;
    }
    if (block && block.contains(selection.anchorNode) && block.contains(selection.focusNode)) {
      return;
    }
    clearLogViewerSelectionHighlight();
  }

  watch(
    () => props.detail,
    () => {
      if (hasExternalDetail.value) {
        detail.value = props.detail || {};
      }
    },
    { immediate: true, deep: true }
  );

  watch(
    resolvedTicketId,
    (ticketId) => {
      currentTicketId.value = ticketId;
      logPullList.value = [];
      logPullTotal.value = 0;
      selectedLogPullRecord.value = null;
      detail.value = hasExternalDetail.value ? props.detail || {} : {};
      logPullQuery.value.pageNum = 1;
      resetLogPullForm();
      if (props.active && currentTicketId.value) {
        loadTicketDetail().then(() => loadLogPullList());
      }
    },
    { immediate: true }
  );

  watch(
    () => props.active,
    (active) => {
      if (active && currentTicketId.value) {
        loadTicketDetail().then(() => loadLogPullList());
      }
      if (!active) {
        stopLogPullAutoRefresh();
        logPullContentOpen.value = false;
        logPullSubmitOpen.value = false;
        clearNativeLogViewerHighlights();
      }
    }
  );

  watch(
    [logViewerContext, logViewerHighlightKeywords, logViewerContextViewMode],
    () => {
      nextTick(() => refreshNativeLogViewerHighlights());
    },
    { deep: true }
  );

  onMounted(() => {
    document.addEventListener('selectionchange', handleLogViewerDocumentSelectionChange);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('selectionchange', handleLogViewerDocumentSelectionChange);
    clearNativeLogViewerHighlights();
    stopLogPullAutoRefresh();
  });

  loadAgentOptions();
  loadProviderOptions();
  loadVendorOptions();
  loadPushOptions();
  loadProjectVendorMapOptions();
</script>

<template>
  <div class="panel-header mb16">
    <div class="panel-inline">
      <span>拉取记录</span>
      <el-tag v-if="logPullAutoRefreshing" size="small" type="warning">自动刷新中</el-tag>
    </div>
    <div class="panel-inline">
      <PromptButton button-text="参数提示" title="参数配置入口" width="420">
        <div>
          日志拉取地址、Cookie、FTP/本地归档配置已统一移到系统参数配置。
          <br />
          <code>ticket.logPull.external</code> 管理外部地址与 Cookie。
          <br />
          <code>ticket.logPull.storage</code> 管理本地/FTP 与轮询参数。
        </div>
      </PromptButton>
      <el-button type="primary" @click="openLogPullSubmitDialog" v-hasPermi="['ticket:logpull:add']"
        >拉取日志</el-button
      >
      <el-button link type="primary" @click="loadLogPullList">刷新</el-button>
    </div>
  </div>
  <el-table
    v-loading="logPullLoading"
    :data="logPullList"
    row-key="id"
    class="mb16 log-pull-record-table"
    scrollbar-always-on
  >
    <el-table-column label="创建时间" prop="createTime" width="170">
      <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
    </el-table-column>
    <el-table-column label="数据类型" width="90" align="center">
      <template #default="scope">
        {{ getOptionLabel(logPullDataTypeOptions, scope.row.commandDataType) }}
      </template>
    </el-table-column>
    <el-table-column label="拉取参数" min-width="180" show-overflow-tooltip>
      <template #default="scope">{{ formatLogPullParameter(scope.row) }}</template>
    </el-table-column>
    <el-table-column label="商家" prop="vendorId" width="110" show-overflow-tooltip />
    <el-table-column label="门店" prop="storeId" min-width="150" show-overflow-tooltip />
    <el-table-column label="POSID" prop="posNo" width="110" show-overflow-tooltip />
    <el-table-column label="状态" min-width="170">
      <template #default="scope">
        <el-tag :type="getLogPullStatusTagType(scope.row.status)">
          {{ scope.row.statusDesc || getOptionLabel(logPullStatusOptions, scope.row.status) }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="保存方式" width="90" align="center">
      <template #default="scope">{{
        getOptionLabel(logPullStorageModeOptions, scope.row.storageMode)
      }}</template>
    </el-table-column>
    <el-table-column label="归档地址" min-width="220" show-overflow-tooltip>
      <template #default="scope">
        <el-link
          v-if="getLogPullArchiveDownloadUrl(scope.row)"
          type="primary"
          :href="getLogPullArchiveDownloadUrl(scope.row)"
          target="_blank"
          @click.prevent="downloadLogPullArchive(scope.row)"
          @contextmenu.prevent="copyLogPullArchiveDownloadUrl(scope.row)"
        >
          {{ getLogPullArchiveDisplayText(scope.row) }}
        </el-link>
        <span v-else>-</span>
      </template>
    </el-table-column>
    <el-table-column label="原始压缩包" min-width="180" show-overflow-tooltip>
      <template #default="scope">
        <el-link
          v-if="getLogPullOriginalDownloadUrl(scope.row)"
          type="primary"
          :href="getLogPullOriginalDownloadUrl(scope.row)"
          target="_blank"
          @click.prevent="downloadLogPullOriginal(scope.row)"
          @contextmenu.prevent="copyLogPullOriginalDownloadUrl(scope.row)"
        >
          {{ getLogPullOriginalDownloadUrl(scope.row) }}
        </el-link>
        <span v-else>-</span>
      </template>
    </el-table-column>
    <el-table-column label="摘要/异常" prop="contentSummary" min-width="220" show-overflow-tooltip>
      <template #default="scope">
        <span>{{ scope.row.errorMessage || scope.row.contentSummary || '-' }}</span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="380">
      <template #default="scope">
        <el-button-group>
          <el-tooltip
            v-if="getLogViewerDownloadProgress(scope.row)"
            :content="getLogViewerDownloadProgress(scope.row).message"
            placement="top"
          >
            <el-progress
              class="log-view-download-progress"
              type="circle"
              :percentage="getLogViewerDownloadProgress(scope.row).percentage"
              :width="26"
              :stroke-width="3"
            />
          </el-tooltip>
          <el-button
            v-else
            link
            type="primary"
            @click="handleOpenLogViewer(scope.row)"
            :disabled="logPullActionLoading"
          >
            查看日志
          </el-button>
          <el-button
            link
            type="primary"
            @click="handleCopyLogPull(scope.row)"
            :disabled="logPullActionLoading || activeLogPullStatuses.includes(scope.row.status)"
            v-hasPermi="['ticket:logpull:add']"
          >
            复制
          </el-button>
          <el-button
            link
            type="warning"
            @click="retryLogPull(scope.row)"
            :disabled="logPullActionLoading || activeLogPullStatuses.includes(scope.row.status)"
            v-hasPermi="['ticket:logpull:add']"
          >
            重新拉取
          </el-button>
          <el-button
            link
            type="success"
            @click="redownloadLogPull(scope.row)"
            :disabled="
              logPullActionLoading || (!scope.row.commandResultUrl && !scope.row.storagePath)
            "
            v-hasPermi="['ticket:logpull:add']"
          >
            重新下载
          </el-button>
          <el-button
            link
            type="danger"
            @click="deleteLogPull(scope.row)"
            :disabled="logPullActionLoading || activeLogPullStatuses.includes(scope.row.status)"
            v-hasPermi="['ticket:logpull:remove']"
          >
            删除
          </el-button>
        </el-button-group>
      </template>
    </el-table-column>
  </el-table>
  <pagination
    v-show="logPullTotal > 0"
    :total="logPullTotal"
    v-model:page="logPullQuery.pageNum"
    v-model:limit="logPullQuery.pageSize"
    @pagination="loadLogPullList"
  />
  <el-dialog
    v-model="logPullSubmitOpen"
    title="提交拉取任务"
    width="760px"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    @closed="resetLogPullForm"
  >
    <el-form ref="logPullRef" :model="logPullForm" :rules="logPullRules" label-width="110px">
      <LogPullConfigFields
        v-model="logPullForm"
        :vendor-options="vendorOptions"
        :environment-options="environmentOptions"
        :parameter-examples="parameterExamples"
        :agent-options="agentOptions"
        :provider-options="providerOptions"
        :data-type-options="logPullDataTypeOptions"
        :storage-mode-options="logPullStorageModeOptions"
      />
      <LogPullNotifyConfigFields v-model="logPullForm.notifyConfig" :push-options="pushOptions" />
      <el-form-item>
        <el-button type="primary" @click="submitLogPull" :loading="logPullSubmitting"
          >提交任务</el-button
        >
        <el-button @click="logPullSubmitOpen = false">取消</el-button>
      </el-form-item>
    </el-form>
  </el-dialog>

  <LogViewerDialog v-model="logPullContentOpen" :record="selectedLogPullRecord">
    <template #toolbar-actions>
      <el-button
        type="warning"
        @click="retryLogPull(selectedLogPullRecord)"
        :disabled="logPullActionLoading"
        v-hasPermi="['ticket:logpull:add']"
      >
        重新拉取
      </el-button>
      <el-button
        type="success"
        @click="redownloadLogPull(selectedLogPullRecord)"
        :disabled="
          logPullActionLoading ||
          (!selectedLogPullRecord?.commandResultUrl && !selectedLogPullRecord?.storagePath)
        "
        v-hasPermi="['ticket:logpull:add']"
      >
        重新下载
      </el-button>
    </template>
  </LogViewerDialog>
</template>

<style scoped lang="scss">
  .panel-header {
    display: flex;
    justify-content: start;
    gap: 12px;
  }

  .panel-inline {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: nowrap;
  }

  .mb16 {
    margin-bottom: 16px;
  }

  .mb8 {
    margin-bottom: 8px;
  }

  .log-view-download-progress {
    display: inline-flex;
    width: 26px;
    height: 26px;
    margin: 0 8px;
    pointer-events: none;
    vertical-align: middle;
  }

  .log-view-download-progress :deep(.el-progress__text) {
    font-size: 8px !important;
  }
</style>
