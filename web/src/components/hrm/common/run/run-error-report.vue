<script setup>
  import {
    errorRecords as fetchErrorRecords,
    errorSummary as fetchErrorSummary,
  } from '@/api/hrm/report.js';

  const props = defineProps(['runId', 'reportId']);
  const openErrorSummaryDialog = defineModel('openErrorSummaryDialog');

  const queryParams = ref({
    pageNum: 1,
    pageSize: 10,
    runId: props.runId,
    reportId: props.reportId,
    runName: undefined,
    projectId: undefined,
    moduleId: undefined,
    status: undefined,
    runType: null,
  });

  const loading = ref({
    page: false,
    runDetail: false,
    errorRecords: false,
  });

  const reportErrorSummary = ref({
    totalCount: 0,
    assertFailCount: 0,
    exceptionCount: 0,
    errorTypeStats: [],
    assertReasonStats: [],
  });
  const errorDrawerOpen = ref(false);
  const currentReasonLabel = ref('');
  const errorRecordList = ref([]);
  const errorRecordTotal = ref(0);
  const errorRecordQuery = ref({
    pageNum: 1,
    pageSize: 10,
    errorType: undefined,
    fingerprint: undefined,
  });

  function loadReportErrorSummary() {
    console.log('Loading Report', queryParams.value.reportId);
    if (!queryParams.value.reportId) {
      reportErrorSummary.value = {
        totalCount: 0,
        assertFailCount: 0,
        exceptionCount: 0,
        errorTypeStats: [],
        assertReasonStats: [],
      };
      return;
    }
    fetchErrorSummary(queryParams.value.reportId, { onlySelf: false }).then((response) => {
      reportErrorSummary.value = response;
    });
  }

  function formatErrorTypeLabel(type) {
    if (type === 'assert_fail') {
      return '断言失败';
    }
    if (type === 'exception') {
      return '执行异常';
    }
    return type || '-';
  }

  function openErrorDrawer(filter = {}) {
    errorDrawerOpen.value = true;
    errorRecordQuery.value.pageNum = 1;
    errorRecordQuery.value.errorType = filter.errorType;
    errorRecordQuery.value.fingerprint = filter.fingerprint;
    currentReasonLabel.value = filter.errorTemplate || '';
    loadErrorRecords();
  }

  function loadErrorRecords() {
    if (!queryParams.value.reportId) {
      return;
    }
    loading.value.errorRecords = true;
    fetchErrorRecords(queryParams.value.reportId, {
      ...errorRecordQuery.value,
      onlySelf: false,
    })
      .then((response) => {
        errorRecordList.value = response.rows;
        errorRecordTotal.value = response.total;
      })
      .finally(() => {
        loading.value.errorRecords = false;
      });
  }

  function handleErrorRecordQuery() {
    errorRecordQuery.value.pageNum = 1;
    loadErrorRecords();
  }

  function resetErrorRecordQuery() {
    currentReasonLabel.value = '';
    errorRecordQuery.value.pageNum = 1;
    errorRecordQuery.value.pageSize = 10;
    errorRecordQuery.value.errorType = undefined;
    errorRecordQuery.value.fingerprint = undefined;
    loadErrorRecords();
  }

  watch(
    () => props.reportId,
    () => {
      console.log('id变化');
      queryParams.value.reportId = props.reportId;
      loadReportErrorSummary();
    }
  );

  onMounted(() => {
    console.log('启动');
    loadReportErrorSummary();
  });
</script>

<template>
  <el-dialog v-model="openErrorSummaryDialog" width="80%" append-to-body>
    <el-card v-if="queryParams.reportId" class="error-summary-card" shadow="never">
      <template #header>
        <div class="error-summary-header">
          <span>失败原因统计</span>
          <el-button link type="primary" @click="openErrorDrawer()">查看全部错误</el-button>
        </div>
      </template>

      <el-row :gutter="12" class="error-metric-row">
        <el-col :xs="24" :sm="8">
          <div class="error-metric error-metric--all">
            <div class="error-metric__label">错误总数</div>
            <div class="error-metric__value">{{ reportErrorSummary.totalCount || 0 }}</div>
          </div>
        </el-col>
        <el-col :xs="24" :sm="8">
          <div class="error-metric error-metric--assert">
            <div class="error-metric__label">断言失败</div>
            <div class="error-metric__value">{{ reportErrorSummary.assertFailCount || 0 }}</div>
            <el-button link type="danger" @click="openErrorDrawer({ errorType: 'assert_fail' })"
              >查看明细</el-button
            >
          </div>
        </el-col>
        <el-col :xs="24" :sm="8">
          <div class="error-metric error-metric--exception">
            <div class="error-metric__label">执行异常</div>
            <div class="error-metric__value">{{ reportErrorSummary.exceptionCount || 0 }}</div>
            <el-button link type="warning" @click="openErrorDrawer({ errorType: 'exception' })"
              >查看明细</el-button
            >
          </div>
        </el-col>
      </el-row>

      <div class="error-type-list" v-if="reportErrorSummary.errorTypeStats?.length">
        <el-tag
          v-for="item in reportErrorSummary.errorTypeStats"
          :key="item.errorType"
          class="error-type-tag"
          effect="plain"
        >
          {{ formatErrorTypeLabel(item.errorType) }} {{ item.count }}
        </el-tag>
      </div>

      <el-table
        v-if="reportErrorSummary.assertReasonStats?.length"
        :data="reportErrorSummary.assertReasonStats"
        border
        size="small"
        class="error-assert-table"
        max-height="260"
      >
        <el-table-column
          label="断言失败原因"
          prop="errorTemplate"
          min-width="260"
          show-overflow-tooltip
        />
        <el-table-column label="断言方法" prop="assertName" width="140" />
        <el-table-column label="检查项" prop="checkKey" min-width="180" show-overflow-tooltip />
        <el-table-column label="失败次数" prop="count" width="100" />
        <el-table-column label="影响用例数" prop="caseCount" width="110" />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="openErrorDrawer(scope.row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="当前报告没有结构化失败数据" :image-size="72" />
    </el-card>

    <el-drawer
      v-model="errorDrawerOpen"
      size="100%"
      append-to-body
      destroy-on-close
      title="失败明细"
    >
      <div class="error-drawer-toolbar">
        <div class="error-drawer-toolbar__filters">
          <el-select
            v-model="errorRecordQuery.errorType"
            clearable
            placeholder="错误类型"
            style="width: 140px"
            @change="handleErrorRecordQuery"
          >
            <el-option label="断言失败" value="assert_fail" />
            <el-option label="执行异常" value="exception" />
          </el-select>
          <el-button @click="resetErrorRecordQuery">重置</el-button>
        </div>
        <el-tag v-if="currentReasonLabel" type="info" effect="plain">
          {{ currentReasonLabel }}
        </el-tag>
      </div>

      <el-table
        v-loading="loading.errorRecords"
        :data="errorRecordList"
        border
        table-layout="fixed"
      >
        <el-table-column label="用例" prop="runName" min-width="180" show-overflow-tooltip />
        <el-table-column label="步骤" prop="stepName" min-width="160" show-overflow-tooltip />
        <el-table-column label="类型" prop="errorType" width="90">
          <template #default="scope">
            <span>{{ formatErrorTypeLabel(scope.row.errorType) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" prop="errorSource" width="120" />
        <el-table-column label="断言方法" prop="assertName" width="120" />
        <el-table-column label="检查项" prop="checkKey" min-width="180" show-overflow-tooltip />
        <el-table-column
          label="期望值"
          prop="expectedValue"
          min-width="180"
          show-overflow-tooltip
        />
        <el-table-column label="实际值" prop="actualValue" min-width="180" show-overflow-tooltip />
        <el-table-column
          label="错误信息"
          prop="errorMessage"
          min-width="260"
          show-overflow-tooltip
        />
        <el-table-column label="时间" prop="createTime" width="170">
          <template #default="scope">
            <span>{{ parseTime(scope.row.createTime) }}</span>
          </template>
        </el-table-column>
      </el-table>

      <pagination
        v-show="errorRecordTotal > 0"
        :total="errorRecordTotal"
        v-model:page="errorRecordQuery.pageNum"
        v-model:limit="errorRecordQuery.pageSize"
        @pagination="loadErrorRecords"
      />
    </el-drawer>
  </el-dialog>
</template>

<style scoped>
  .error-summary-card {
    margin-bottom: 16px;
  }

  .error-summary-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .error-metric-row {
    margin-bottom: 12px;
  }

  .error-metric {
    padding: 16px;
    border-radius: 10px;
    min-height: 120px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }

  .error-metric--all {
    background: linear-gradient(135deg, #f7f4ea, #f1e2bd);
  }

  .error-metric--assert {
    background: linear-gradient(135deg, #fce9e4, #f8cbbf);
  }

  .error-metric--exception {
    background: linear-gradient(135deg, #fff3dd, #ffd699);
  }

  .error-metric__label {
    font-size: 13px;
    color: #6b7280;
  }

  .error-metric__value {
    font-size: 30px;
    font-weight: 700;
    color: #1f2937;
  }

  .error-type-list {
    margin-bottom: 12px;
  }

  .error-type-tag {
    margin-right: 8px;
    margin-bottom: 8px;
  }

  .error-drawer-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }

  .error-drawer-toolbar__filters {
    display: flex;
    align-items: center;
    gap: 8px;
  }
</style>
