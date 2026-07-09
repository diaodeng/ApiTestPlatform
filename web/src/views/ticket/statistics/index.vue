<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true">
      <el-form-item label="提交时间范围">
        <el-date-picker
          v-model="dateRange"
          value-format="YYYY-MM-DD"
          type="daterange"
          range-separator="-"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
        />
      </el-form-item>
      <el-form-item label="项目">
        <el-select
          v-model="selectedProjectIds"
          multiple
          clearable
          collapse-tags
          collapse-tags-tooltip
          filterable
          placeholder="所属项目"
          style="width: 260px"
          @change="handleProjectChange"
        >
          <el-option
            v-for="item in projectOptions"
            :key="item.projectId"
            :label="item.projectName"
            :value="item.projectId"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="模块">
        <el-select
          v-model="selectedModuleIds"
          multiple
          clearable
          collapse-tags
          collapse-tags-tooltip
          filterable
          placeholder="所属模块"
          style="width: 280px"
        >
          <el-option
            v-for="item in moduleOptions"
            :key="`${item.projectId}-${item.moduleId}`"
            :label="formatModuleOptionLabel(item)"
            :value="item.moduleId"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="模块Code">
        <el-select
          v-model="selectedModuleCodes"
          multiple
          clearable
          collapse-tags
          collapse-tags-tooltip
          filterable
          placeholder="模块Code"
          style="width: 240px"
        >
          <el-option
            v-for="item in moduleCodeOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="细分问题">
        <el-select
          v-model="selectedProblemPatternCodes"
          multiple
          clearable
          collapse-tags
          collapse-tags-tooltip
          filterable
          placeholder="细分问题类型"
          style="width: 260px"
        >
          <el-option
            v-for="item in problemPatternOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="趋势粒度">
        <el-segmented v-model="trendGranularity" :options="trendGranularityOptions" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">查询</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
        <el-button icon="Setting" @click="blockConfigOpen = true">显示配置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="16" class="mb16">
      <el-col :span="6">
        <el-card shadow="never">
          <div class="metric-label">工单总数</div>
          <div class="metric-value">{{ overview.total || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="metric-label">新增工单</div>
          <div class="metric-value">{{ overview.newCount || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="metric-label">已处理数</div>
          <div class="metric-value">{{ overview.processedInNewCount || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="metric-label">处理率</div>
          <div class="metric-value">{{ formatPercent(overview.processRate) }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="stats-block-grid">
      <el-col
        v-for="block in visibleStatisticsBlocks"
        :key="block.key"
        :span="block.span"
        class="stats-block-col"
      >
        <el-card shadow="never">
          <template #header>{{ block.title }}</template>
          <el-table v-loading="loading" :data="getStatisticsBlockRows(block)">
            <el-table-column :label="block.label">
              <template #default="scope">{{ scope.row.__statLabel }}</template>
            </el-table-column>
            <el-table-column :label="block.countLabel" prop="count" width="100" align="center" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row v-show="hasVisibleTrendCharts" :gutter="16" class="trend-chart-grid mt16">
      <el-col
        v-show="isTrendBlockVisible('overallTrend')"
        :xs="24"
        :lg="12"
        class="trend-chart-col"
      >
        <el-card shadow="never">
          <template #header>整体趋势</template>
          <div ref="overallTrendChartRef" class="trend-chart" />
        </el-card>
      </el-col>
      <el-col
        v-show="isTrendBlockVisible('problemTrend')"
        :xs="24"
        :lg="12"
        class="trend-chart-col"
      >
        <el-card shadow="never">
          <template #header>问题性质趋势</template>
          <div ref="problemTrendChartRef" class="trend-chart" />
        </el-card>
      </el-col>
      <el-col
        v-show="isTrendBlockVisible('processingTrend')"
        :xs="24"
        :lg="12"
        class="trend-chart-col"
      >
        <el-card shadow="never">
          <template #header>处理率与存量趋势</template>
          <div ref="processingTrendChartRef" class="trend-chart" />
        </el-card>
      </el-col>
      <el-col v-show="isTrendBlockVisible('moduleTrend')" :xs="24" :lg="12" class="trend-chart-col">
        <el-card shadow="never">
          <template #header>Top模块趋势</template>
          <div ref="moduleTrendChartRef" class="trend-chart" />
        </el-card>
      </el-col>
      <el-col
        v-show="isTrendBlockVisible('problemPatternTrend')"
        :xs="24"
        :lg="12"
        class="trend-chart-col"
      >
        <el-card shadow="never">
          <template #header>Top细分问题趋势</template>
          <div ref="problemPatternTrendChartRef" class="trend-chart" />
        </el-card>
      </el-col>
    </el-row>

    <el-card v-show="isTrendBlockVisible('trendDetail')" shadow="never" class="mt16">
      <template #header>趋势明细</template>
      <el-table v-loading="loading" :data="trend.series || []">
        <el-table-column label="周期" prop="bucket" width="120" />
        <el-table-column label="新增" prop="newCount" width="90" align="center" />
        <el-table-column label="已响应" prop="firstRespondedCount" width="90" align="center" />
        <el-table-column label="已处理" prop="processedCount" width="90" align="center" />
        <el-table-column label="新增已处理" prop="processedInNewCount" width="110" align="center" />
        <el-table-column label="处理率" width="90" align="center">
          <template #default="scope">{{ formatPercent(scope.row.processRate) }}</template>
        </el-table-column>
        <el-table-column label="处置完成" prop="resolvedCount" width="100" align="center" />
        <el-table-column label="关闭" prop="closedCount" width="90" align="center" />
        <el-table-column label="净增" prop="netIncrease" width="90" align="center" />
        <el-table-column label="未处理存量" prop="unprocessedBacklog" width="110" align="center" />
        <el-table-column label="未关闭存量" prop="openBacklog" width="110" align="center" />
        <el-table-column label="Bug" prop="problemCount" width="90" align="center" />
        <el-table-column label="非Bug" prop="nonProblemCount" width="90" align="center" />
        <el-table-column label="支持类" prop="supportCount" width="90" align="center" />
        <el-table-column label="平均响应耗时" width="130" align="center">
          <template #default="scope">{{ formatSeconds(scope.row.avgFirstResponseSeconds) }}</template>
        </el-table-column>
        <el-table-column label="平均处理耗时" width="130" align="center">
          <template #default="scope">{{ formatSeconds(scope.row.avgFirstProcessSeconds) }}</template>
        </el-table-column>
        <el-table-column label="Top细分问题" min-width="220" show-overflow-tooltip>
          <template #default="scope">{{ formatTopRows(scope.row.problemPatternCounts) }}</template>
        </el-table-column>
        <el-table-column label="Top模块" min-width="180" show-overflow-tooltip>
          <template #default="scope">{{ formatTopRows(scope.row.moduleCounts) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog title="统计块显示配置" v-model="blockConfigOpen" width="560px" append-to-body>
      <div class="config-section-title">汇总统计块</div>
      <el-checkbox-group v-model="visibleStatisticsBlockKeys" class="statistics-block-config">
        <el-checkbox v-for="item in statisticsBlockOptions" :key="item.key" :label="item.key">
          {{ item.title }}
        </el-checkbox>
      </el-checkbox-group>
      <el-divider />
      <div class="config-section-title">趋势展示</div>
      <el-checkbox-group v-model="visibleTrendBlockKeys" class="statistics-block-config">
        <el-checkbox v-for="item in trendBlockOptions" :key="item.key" :label="item.key">
          {{ item.title }}
        </el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="resetStatisticsBlockConfig">恢复默认</el-button>
        <el-button type="primary" @click="saveStatisticsBlockConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="TicketStatistics">
  import {
    getTicketStatClassificationOptions,
    getTicketStatistics,
    getTicketStatisticsTrend,
    getTicketWorkflow,
    listTicketModuleOptions,
    listTicketProjectOptions,
  } from '@/api/ticket/ticket';
  import { getOptionLabel, sourceOptions } from '../constants';
  import { getCurrentUserConfig, saveCurrentUserConfig } from '@/api/system/userConfig';
  import * as echarts from 'echarts';

  const { proxy } = getCurrentInstance();
  const loading = ref(false);
  const dateRange = ref([]);
  const overview = ref({});
  const trend = ref({ series: [] });
  const projectOptions = ref([]);
  const moduleOptions = ref([]);
  const moduleCodeOptions = ref([]);
  const selectedProjectIds = ref([]);
  const selectedModuleIds = ref([]);
  const selectedModuleCodes = ref([]);
  const selectedProblemPatternCodes = ref([]);
  const trendGranularity = ref('week');
  const issueTypeOptions = ref([]);
  const workflowStatusOptions = ref([]);
  const rootCauseTypeOptions = ref([]);
  const solutionTypeOptions = ref([]);
  const resolutionOptions = ref([]);
  const problemPatternOptions = ref([]);
  const blockConfigOpen = ref(false);
  const overallTrendChartRef = ref(null);
  const problemTrendChartRef = ref(null);
  const processingTrendChartRef = ref(null);
  const moduleTrendChartRef = ref(null);
  const problemPatternTrendChartRef = ref(null);
  const trendChartInstances = {};
  const queryParams = ref({
    beginTime: undefined,
    endTime: undefined,
  });
  const trendGranularityOptions = [
    { label: '日', value: 'day' },
    { label: '周', value: 'week' },
    { label: '月', value: 'month' },
  ];
  const trendBlockOptions = [
    { key: 'overallTrend', title: '整体趋势曲线' },
    { key: 'problemTrend', title: '问题性质趋势曲线' },
    { key: 'processingTrend', title: '处理率与存量趋势曲线' },
    { key: 'moduleTrend', title: 'Top模块趋势曲线' },
    { key: 'problemPatternTrend', title: 'Top细分问题趋势曲线' },
    { key: 'trendDetail', title: '趋势明细表格' },
  ];
  const statisticsBlockConfigVersion = 2;
  const trendBlockKeysAddedInV2 = ['processingTrend'];

  const statisticsBlockOptions = [
    {
      key: 'status',
      title: '状态分布',
      dataKey: 'statusCounts',
      label: '状态',
      countLabel: '数量',
      span: 8,
      format: (row) => getOptionLabel(workflowStatusOptions.value, row.status),
    },
    {
      key: 'module',
      title: '模块分布',
      dataKey: 'moduleCounts',
      label: '模块',
      countLabel: '数量',
      span: 8,
      format: (row) => row.module || '未填写',
    },
    {
      key: 'assignee',
      title: '人员处理量',
      dataKey: 'assigneeCounts',
      label: '处理人',
      countLabel: '数量',
      span: 8,
      format: (row) => row.userName || '未分配',
    },
    {
      key: 'category',
      title: '问题分类',
      dataKey: 'categoryCounts',
      label: '分类',
      countLabel: '数量',
      span: 8,
      format: (row) => row.category || '未填写',
    },
    {
      key: 'rootCause',
      title: '原因分类',
      dataKey: 'rootCauseCounts',
      label: '原因',
      countLabel: '数量',
      span: 8,
      format: (row) => row.rootCause || '未填写',
    },
    {
      key: 'transition',
      title: '状态流转',
      dataKey: 'transitionCounts',
      label: '流转',
      countLabel: '次数',
      span: 8,
      format: (row) => formatTransition(row),
    },
    {
      key: 'source',
      title: '来源分布',
      dataKey: 'sourceCounts',
      label: '来源',
      countLabel: '数量',
      span: 12,
      format: (row) => getOptionLabel(sourceOptions, row.source),
    },
    {
      key: 'priority',
      title: '内部优先级',
      dataKey: 'priorityCounts',
      label: '优先级',
      countLabel: '数量',
      span: 12,
      format: (row) => row.priority || '未填写',
    },
    {
      key: 'issueType',
      title: '工单类型',
      dataKey: 'issueTypeCounts',
      label: '类型',
      countLabel: '数量',
      span: 8,
      format: (row) => formatIssueType(row),
    },
    {
      key: 'problem',
      title: '是否真实问题',
      dataKey: 'problemCounts',
      label: '问题性质',
      countLabel: '数量',
      span: 8,
      format: (row) => formatProblemFlag(row.isProblem),
    },
    {
      key: 'rootCauseType',
      title: '根因分类',
      dataKey: 'rootCauseTypeCounts',
      label: '根因',
      countLabel: '数量',
      span: 8,
      format: (row) => getStatOptionLabel(rootCauseTypeOptions, row.rootCauseType),
    },
    {
      key: 'solutionType',
      title: '解决方式',
      dataKey: 'solutionTypeCounts',
      label: '方式',
      countLabel: '数量',
      span: 12,
      format: (row) => getStatOptionLabel(solutionTypeOptions, row.solutionType),
    },
    {
      key: 'resolution',
      title: '关闭结果',
      dataKey: 'resolutionCounts',
      label: '结果',
      countLabel: '数量',
      span: 12,
      format: (row) => formatResolution(row),
    },
    {
      key: 'problemPattern',
      title: '细分问题',
      dataKey: 'problemPatternCounts',
      label: '细分问题',
      countLabel: '数量',
      span: 12,
      format: (row) => formatProblemPattern(row),
    },
  ];
  const defaultStatisticsBlockKeys = statisticsBlockOptions.map((item) => item.key);
  const defaultTrendBlockKeys = trendBlockOptions.map((item) => item.key);
  const visibleStatisticsBlockKeys = ref([...defaultStatisticsBlockKeys]);
  const visibleTrendBlockKeys = ref([...defaultTrendBlockKeys]);
  const visibleStatisticsBlocks = computed(() => {
    const visibleKeys = new Set(visibleStatisticsBlockKeys.value);
    return statisticsBlockOptions.filter((item) => visibleKeys.has(item.key));
  });
  const visibleTrendBlockKeySet = computed(() => new Set(visibleTrendBlockKeys.value));
  const hasVisibleTrendCharts = computed(
    () =>
      isTrendBlockVisible('overallTrend') ||
      isTrendBlockVisible('problemTrend') ||
      isTrendBlockVisible('processingTrend') ||
      isTrendBlockVisible('moduleTrend') ||
      isTrendBlockVisible('problemPatternTrend')
  );

  function getStatistics() {
    loading.value = true;
    const params = buildQueryParams();
    Promise.all([getTicketStatistics(params), getTicketStatisticsTrend(params)])
      .then(([overviewResponse, trendResponse]) => {
        overview.value = overviewResponse.data || {};
        trend.value = trendResponse.data || { series: [] };
        nextTick(() => renderTrendCharts());
      })
      .finally(() => {
        loading.value = false;
      });
  }

  /**
   * 获取统计汇总块表格行，并按最终展示文案合并数量。
   * 后端同一业务含义可能因空值、占位值或 code/name 混用拆成多行，
   * 这里以用户看到的标签为准聚合，避免“未填写”“POS客户端支付”等重复展示。
   * @param {object} block 汇总块配置，包含 dataKey 和 format 方法
   * @returns {Array<object>} 合并后的统计行
   */
  function getStatisticsBlockRows(block) {
    const rows = Array.isArray(overview.value?.[block.dataKey]) ? overview.value[block.dataKey] : [];
    const rowMap = new Map();
    rows.forEach((row) => {
      const statLabel = normalizeStatisticsBlockLabel(block.format(row));
      const existing = rowMap.get(statLabel);
      if (existing) {
        existing.count = Number(existing.count || 0) + Number(row.count || 0);
        return;
      }
      rowMap.set(statLabel, {
        ...row,
        __statLabel: statLabel,
        count: Number(row.count || 0),
      });
    });
    return Array.from(rowMap.values());
  }

  /**
   * 归一化统计汇总块的展示标签。
   * @param {string} value 原始展示文案
   * @returns {string} 去空白后的展示文案，空值统一为未填写
   */
  function normalizeStatisticsBlockLabel(value) {
    return String(value || '').trim() || '未填写';
  }

  function buildQueryParams() {
    return {
      ...queryParams.value,
      granularity: trendGranularity.value,
      projectIds: selectedProjectIds.value.length ? selectedProjectIds.value.join(',') : undefined,
      moduleIds: selectedModuleIds.value.length ? selectedModuleIds.value.join(',') : undefined,
      moduleCodes: selectedModuleCodes.value.length
        ? selectedModuleCodes.value.join(',')
        : undefined,
      problemPatternCodes: selectedProblemPatternCodes.value.length
        ? selectedProblemPatternCodes.value.join(',')
        : undefined,
    };
  }

  function normalizeStatOptions(items = []) {
    return (Array.isArray(items) ? items : [])
      .map((item) => ({
        value: String(item.value || item.code || '').trim(),
        label: String(item.label || item.name || item.value || item.code || '').trim(),
      }))
      .filter((item) => item.value);
  }

  function loadStatClassificationOptions() {
    getTicketStatClassificationOptions().then((response) => {
      const config = response.data || {};
      issueTypeOptions.value = normalizeStatOptions(config.issueTypes);
      rootCauseTypeOptions.value = normalizeStatOptions(config.rootCauseTypes);
      solutionTypeOptions.value = normalizeStatOptions(config.solutionTypes);
      resolutionOptions.value = normalizeStatOptions(config.resolutions);
      problemPatternOptions.value = normalizeStatOptions(config.problemPatterns);
    });
  }

  function normalizeStatisticsBlockKeys(value) {
    const rawKeys = Array.isArray(value?.visibleBlocks) ? value.visibleBlocks : value;
    const validKeys = new Set(statisticsBlockOptions.map((item) => item.key));
    const normalized = (Array.isArray(rawKeys) ? rawKeys : defaultStatisticsBlockKeys)
      .map((item) => String(item || '').trim())
      .filter((item) => validKeys.has(item));
    return normalized.length ? normalized : [...defaultStatisticsBlockKeys];
  }

  function normalizeTrendBlockKeys(value) {
    const rawKeys = Array.isArray(value?.visibleTrendBlocks) ? value.visibleTrendBlocks : value;
    const validKeys = new Set(trendBlockOptions.map((item) => item.key));
    const normalized = (Array.isArray(rawKeys) ? rawKeys : defaultTrendBlockKeys)
      .map((item) => String(item || '').trim())
      .filter((item) => validKeys.has(item));
    const result = normalized.length ? normalized : [...defaultTrendBlockKeys];
    const configVersion = Number(value?.configVersion || 1);
    if (!Array.isArray(value) && configVersion >= statisticsBlockConfigVersion) {
      return result;
    }
    // 兼容历史用户显示配置：旧配置保存时不存在新增趋势项，需要默认补齐一次。
    trendBlockKeysAddedInV2.forEach((key) => {
      if (validKeys.has(key) && !result.includes(key)) {
        result.push(key);
      }
    });
    return result;
  }

  function loadStatisticsBlockConfig() {
    return getCurrentUserConfig('ticket', 'ticket_statistics_blocks')
      .then((response) => {
        const configValue = response.data?.configValue;
        visibleStatisticsBlockKeys.value = normalizeStatisticsBlockKeys(configValue);
        visibleTrendBlockKeys.value = normalizeTrendBlockKeys(configValue);
      })
      .catch(() => {
        visibleStatisticsBlockKeys.value = [...defaultStatisticsBlockKeys];
        visibleTrendBlockKeys.value = [...defaultTrendBlockKeys];
      });
  }

  function saveStatisticsBlockConfig() {
    visibleStatisticsBlockKeys.value = normalizeStatisticsBlockKeys(
      visibleStatisticsBlockKeys.value
    );
    visibleTrendBlockKeys.value = normalizeTrendBlockKeys(visibleTrendBlockKeys.value);
    saveCurrentUserConfig({
      configType: 'ticket',
      configKey: 'ticket_statistics_blocks',
      configValue: {
        configVersion: statisticsBlockConfigVersion,
        visibleBlocks: visibleStatisticsBlockKeys.value,
        visibleTrendBlocks: visibleTrendBlockKeys.value,
      },
      remark: '工单统计页面显示块配置',
    }).then(() => {
      blockConfigOpen.value = false;
      nextTick(() => {
        renderTrendCharts();
        resizeTrendCharts();
      });
      proxy.$modal.msgSuccess('保存成功');
    });
  }

  function resetStatisticsBlockConfig() {
    visibleStatisticsBlockKeys.value = [...defaultStatisticsBlockKeys];
    visibleTrendBlockKeys.value = [...defaultTrendBlockKeys];
    nextTick(() => {
      renderTrendCharts();
      resizeTrendCharts();
    });
  }

  function loadProjectOptions() {
    return listTicketProjectOptions().then((response) => {
      projectOptions.value = response.data || [];
    });
  }

  async function loadModuleOptions(projectIds = []) {
    const ids = Array.isArray(projectIds) ? projectIds.filter(Boolean) : [];
    const requests = ids.length
      ? ids.map((projectId) => listTicketModuleOptions({ projectId }))
      : [listTicketModuleOptions({})];
    const responses = await Promise.all(requests);
    const moduleMap = new Map();
    responses.forEach((response) => {
      (response.data || []).forEach((item) => {
        const key = `${item.projectId || ''}-${item.moduleId}`;
        if (item.moduleId && !moduleMap.has(key)) {
          moduleMap.set(key, item);
        }
      });
    });
    moduleOptions.value = Array.from(moduleMap.values());
    moduleCodeOptions.value = buildModuleCodeOptions(moduleOptions.value);
    const validModuleIds = new Set(moduleOptions.value.map((item) => item.moduleId));
    selectedModuleIds.value = selectedModuleIds.value.filter((moduleId) =>
      validModuleIds.has(moduleId)
    );
    const validModuleCodes = new Set(moduleCodeOptions.value.map((item) => item.value));
    selectedModuleCodes.value = selectedModuleCodes.value.filter((moduleCode) =>
      validModuleCodes.has(moduleCode)
    );
  }

  function handleProjectChange(projectIds) {
    loadModuleOptions(projectIds);
  }

  function handleQuery() {
    queryParams.value.beginTime = dateRange.value?.[0];
    queryParams.value.endTime = dateRange.value?.[1];
    getStatistics();
  }

  function resetQuery() {
    dateRange.value = [];
    selectedProjectIds.value = [];
    selectedModuleIds.value = [];
    selectedModuleCodes.value = [];
    selectedProblemPatternCodes.value = [];
    trendGranularity.value = 'week';
    queryParams.value = { beginTime: undefined, endTime: undefined };
    loadModuleOptions([]);
    getStatistics();
  }

  function formatSeconds(seconds) {
    if (!seconds) return '-';
    const hour = Math.floor(seconds / 3600);
    const minute = Math.floor((seconds % 3600) / 60);
    const second = seconds % 60;
    return `${hour}小时${minute}分${second}秒`;
  }

  function formatPercent(value) {
    const numeric = Number(value || 0);
    return `${(numeric * 100).toFixed(1)}%`;
  }

  function getStatOptionLabel(options, value) {
    const text = String(value || '').trim();
    if (!text || text === '未填写') {
      return '未填写';
    }
    const rows = Array.isArray(options) ? options : options.value || [];
    return rows.find((item) => item.value === text)?.label || text;
  }

  function formatIssueType(row) {
    if (row.issueTypeName) {
      return row.issueTypeName;
    }
    return getStatOptionLabel(issueTypeOptions, row.issueTypeId);
  }

  function formatProblemFlag(value) {
    if (value === true) return '真实问题';
    if (value === false) return '非问题';
    return '未填写';
  }

  function formatResolution(row) {
    if (row.resolutionName) {
      return row.resolutionName;
    }
    return getStatOptionLabel(resolutionOptions, row.resolutionCode);
  }

  function formatProblemPattern(row) {
    const code = row.problemPatternCode || row.problem_pattern_code || '';
    const name = row.problemPatternName || row.problem_pattern_name || code;
    return getStatOptionLabel(problemPatternOptions, code) || name || '未填写';
  }

  function formatTopRows(rows = []) {
    return (
      (Array.isArray(rows) ? rows : [])
        .slice(0, 3)
        .map(
          (item) =>
            `${item.name || item.problemPatternName || item.module || '-'} ${item.count || 0}`
        )
        .join('，') || '-'
    );
  }

  function formatModuleOptionLabel(item) {
    const project = projectOptions.value.find(
      (projectItem) => projectItem.projectId === item.projectId
    );
    return project?.projectName ? `${project.projectName} / ${item.moduleName}` : item.moduleName;
  }

  function buildModuleCodeOptions(moduleItems = []) {
    const codeMap = new Map();
    (Array.isArray(moduleItems) ? moduleItems : []).forEach((item) => {
      const code = String(item?.moduleCode || '').trim();
      if (!code || codeMap.has(code)) {
        return;
      }
      codeMap.set(code, {
        value: code,
        label: code,
      });
    });
    return Array.from(codeMap.values());
  }

  function formatTransition(row) {
    const fromStatus =
      row.fromStatus === '创建' ? '创建' : getOptionLabel(workflowStatusOptions.value, row.fromStatus);
    return `${fromStatus} -> ${getOptionLabel(workflowStatusOptions.value, row.toStatus)}`;
  }

  function isTrendBlockVisible(key) {
    return visibleTrendBlockKeySet.value.has(key);
  }

  function getTrendSeries() {
    return Array.isArray(trend.value?.series) ? trend.value.series : [];
  }

  function getTrendBuckets() {
    return getTrendSeries().map((item) => item.bucket || item.bucketStart || '-');
  }

  function getCounterRowName(item = {}) {
    return (
      String(
        item.name ||
          item.problemPatternName ||
          item.module ||
          item.issueTypeName ||
          item.rootCauseType ||
          item.resolutionName ||
          '未填写'
      ).trim() || '未填写'
    );
  }

  function getTopCounterNames(dataKey, limit = 6) {
    const totals = new Map();
    getTrendSeries().forEach((bucket) => {
      (Array.isArray(bucket[dataKey]) ? bucket[dataKey] : []).forEach((item) => {
        const name = getCounterRowName(item);
        totals.set(name, Number(totals.get(name) || 0) + Number(item.count || 0));
      });
    });
    return Array.from(totals.entries())
      .sort((left, right) => right[1] - left[1])
      .slice(0, limit)
      .map(([name]) => name);
  }

  function buildCounterTrendSeries(dataKey, names) {
    return names.map((name) => ({
      name,
      type: 'line',
      smooth: true,
      symbolSize: 6,
      data: getTrendSeries().map((bucket) => {
        const rows = Array.isArray(bucket[dataKey]) ? bucket[dataKey] : [];
        const matched = rows.find((item) => getCounterRowName(item) === name);
        return Number(matched?.count || 0);
      }),
    }));
  }

  function buildLineChartOption(series, options = {}) {
    const buckets = getTrendBuckets();
    const hasData =
      buckets.length > 0 &&
      series.some((item) => item.data.some((value) => Number(value || 0) !== 0));
    return {
      color: [
        '#2563eb',
        '#16a34a',
        '#f59e0b',
        '#dc2626',
        '#0891b2',
        '#7c3aed',
        '#db2777',
        '#65a30d',
      ],
      tooltip: {
        trigger: 'axis',
      },
      legend: {
        type: 'scroll',
        top: 0,
      },
      grid: {
        left: 44,
        right: 24,
        top: 54,
        bottom: 36,
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: buckets,
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
      },
      series,
      graphic: hasData
        ? undefined
        : {
            type: 'text',
            left: 'center',
            top: 'middle',
            style: {
              text: '暂无趋势数据',
              fill: '#909399',
              fontSize: 14,
            },
          },
      ...options,
    };
  }

  function getTrendChart(key, chartRef) {
    if (!chartRef.value) {
      return null;
    }
    if (!trendChartInstances[key]) {
      trendChartInstances[key] = echarts.init(chartRef.value);
    }
    return trendChartInstances[key];
  }

  function renderTrendCharts() {
    const overallChart = getTrendChart('overall', overallTrendChartRef);
    const problemChart = getTrendChart('problem', problemTrendChartRef);
    const processingChart = getTrendChart('processing', processingTrendChartRef);
    const moduleChart = getTrendChart('module', moduleTrendChartRef);
    const problemPatternChart = getTrendChart('problemPattern', problemPatternTrendChartRef);
    const seriesRows = getTrendSeries();
    const moduleNames = getTopCounterNames('moduleCounts');
    const problemPatternNames = getTopCounterNames('problemPatternCounts');

    overallChart?.setOption(
      buildLineChartOption([
        {
          name: '新增',
          type: 'line',
          smooth: true,
          symbolSize: 6,
          data: seriesRows.map((item) => Number(item.newCount || 0)),
        },
        {
          name: '已响应',
          type: 'line',
          smooth: true,
          symbolSize: 6,
          data: seriesRows.map((item) => Number(item.firstRespondedCount || 0)),
        },
        {
          name: '已处理',
          type: 'line',
          smooth: true,
          symbolSize: 6,
          data: seriesRows.map((item) => Number(item.processedCount || 0)),
        },
        {
          name: '处置完成',
          type: 'line',
          smooth: true,
          symbolSize: 6,
          data: seriesRows.map((item) => Number(item.resolvedCount || 0)),
        },
        {
          name: '关闭',
          type: 'line',
          smooth: true,
          symbolSize: 6,
          data: seriesRows.map((item) => Number(item.closedCount || 0)),
        },
      ]),
      true
    );
    problemChart?.setOption(
      buildLineChartOption([
        {
          name: 'Bug',
          type: 'line',
          smooth: true,
          symbolSize: 6,
          data: seriesRows.map((item) => Number(item.problemCount || 0)),
        },
        {
          name: '非Bug',
          type: 'line',
          smooth: true,
          symbolSize: 6,
          data: seriesRows.map((item) => Number(item.nonProblemCount || 0)),
        },
        {
          name: '未判断',
          type: 'line',
          smooth: true,
          symbolSize: 6,
          data: seriesRows.map((item) => Number(item.unknownProblemCount || 0)),
        },
        {
          name: '支持类',
          type: 'line',
          smooth: true,
          symbolSize: 6,
          data: seriesRows.map((item) => Number(item.supportCount || 0)),
        },
      ]),
      true
    );
    processingChart?.setOption(
      buildLineChartOption(
        [
          {
            name: '处理率',
            type: 'line',
            smooth: true,
            symbolSize: 6,
            yAxisIndex: 1,
            data: seriesRows.map((item) => Number(((item.processRate || 0) * 100).toFixed(1))),
          },
          {
            name: '未处理存量',
            type: 'line',
            smooth: true,
            symbolSize: 6,
            areaStyle: { opacity: 0.12 },
            data: seriesRows.map((item) => Number(item.unprocessedBacklog || 0)),
          },
          {
            name: '未关闭存量',
            type: 'line',
            smooth: true,
            symbolSize: 6,
            data: seriesRows.map((item) => Number(item.openBacklog || 0)),
          },
        ],
        {
          yAxis: [
            { type: 'value', minInterval: 1 },
            {
              type: 'value',
              min: 0,
              max: 100,
              axisLabel: { formatter: '{value}%' },
            },
          ],
        }
      ),
      true
    );
    moduleChart?.setOption(
      buildLineChartOption(buildCounterTrendSeries('moduleCounts', moduleNames)),
      true
    );
    problemPatternChart?.setOption(
      buildLineChartOption(buildCounterTrendSeries('problemPatternCounts', problemPatternNames)),
      true
    );
  }

  function resizeTrendCharts() {
    Object.values(trendChartInstances).forEach((instance) => instance?.resize());
  }

  function disposeTrendCharts() {
    Object.values(trendChartInstances).forEach((instance) => instance?.dispose());
  }

  loadProjectOptions().then(() => loadModuleOptions([]));
  loadStatClassificationOptions();
  loadStatisticsBlockConfig();
  getStatistics();

  watch(
    visibleTrendBlockKeys,
    () => {
      nextTick(() => {
        renderTrendCharts();
        resizeTrendCharts();
      });
    },
    { deep: true }
  );

  // 加载工作流状态配置，用于状态分布显示
  function loadWorkflowStatuses() {
    getTicketWorkflow().then((response) => {
      const statuses = response.data?.statuses || [];
      workflowStatusOptions.value = statuses.map((item) => ({
        label: item.name,
        value: item.code,
      }));
    });
  }

  onMounted(() => {
    loadWorkflowStatuses();
    window.addEventListener('resize', resizeTrendCharts);
    nextTick(() => renderTrendCharts());
  });

  onBeforeUnmount(() => {
    window.removeEventListener('resize', resizeTrendCharts);
    disposeTrendCharts();
  });
</script>

<style scoped>
  .app-container {
    /*
     * 统计页包含多组图表和明细表，需要按内容自然撑高，
     * 避免继承全局 flex: 1 后只能占满一屏导致底部内容无法继续滚动显示。
     */
    display: block;
    flex: 0 0 auto;
    min-height: auto;
  }

  .mb16 {
    margin-bottom: 16px;
  }

  .mt16 {
    margin-top: 16px;
  }

  .stats-block-grid {
    row-gap: 16px;
  }

  .stats-block-col {
    margin-bottom: 16px;
  }

  .trend-chart-grid {
    row-gap: 16px;
  }

  .trend-chart-col {
    margin-bottom: 16px;
  }

  .trend-chart {
    width: 100%;
    height: 360px;
  }

  .statistics-block-config {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px 16px;
  }

  .config-section-title {
    margin-bottom: 12px;
    color: #303133;
    font-size: 14px;
    font-weight: 600;
  }

  .metric-label {
    color: #606266;
    font-size: 14px;
  }

  .metric-value {
    margin-top: 10px;
    color: #303133;
    font-size: 28px;
    font-weight: 700;
  }
</style>
