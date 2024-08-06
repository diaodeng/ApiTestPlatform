<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="报告名称" prop="reportName">
        <el-input
            v-model="queryParams.reportName"
            placeholder="请输入报告名称"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="报告状态" clearable style="width: 100px">
          <el-option
              v-for="dict in hrm_run_status"
              :key="dict.value"
              :label="dict.label"
              :value="dict.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button type="default" icon="Refresh" @click="resetQuery">重置</el-button>
        <el-button type="danger" icon="Delete" @click="handleDelete" v-hasPermi="['hrm:report:delete']">删除</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="reportList"
              @selection-change="handleSelectionChange"
              border
    >
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column label="ID" align="center" prop="reportId"/>
      <el-table-column label="报告名" align="center" prop="reportName"/>
      <el-table-column label="success" align="center" prop="success"/>
      <el-table-column label="total" align="center" prop="total"/>
      <el-table-column label="status" align="center" prop="status">
        <template #default="scope">
          <dict-tag :options="hrm_run_status" :value="scope.row.status"/>
        </template>
      </el-table-column>
      <el-table-column label="执行开始时间" align="center" prop="createTime" class-name="small-padding fixed-width">
        <template #default="scope">
          <span>{{ parseTime(scope.row.startAt) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="执行时长(S)" align="center" prop="createTime" class-name="small-padding fixed-width">
        <template #default="scope">
          <span>{{ scope.row.testDuration }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" align="center" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="handleView(scope.row)" v-hasPermi="['hrm:report:detail']"
                     title="查看">
          </el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)"
                     v-hasPermi="['hrm:report:delete']" title="删除">
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination
        v-show="total > 0"
        :total="total"
        v-model:page="queryParams.pageNum"
        v-model:limit="queryParams.pageSize"
        @pagination="getList"
    />

    <el-dialog fullscreen v-model="showReportDetail" append-to-body>
      <el-container style="height: 100%">
        <!--          <el-header height="20px" border="2px" style="border-bottom-color: #97a8be;text-align: right">-->
        <!--          </el-header>-->
        <el-main style="max-height: calc(100vh - 95px);">
          <RunDetail :report-id="currentReportId" :view-type="runDetailViewTypeEnum.report"></RunDetail>
        </el-main>
      </el-container>
    </el-dialog>
  </div>
</template>

<script setup name="RunDetail">
import * as ReportApi from "@/api/hrm/report.js";
import {runDetailViewTypeEnum} from "@/components/hrm/enum.js";
import DictTag from "@/components/DictTag/index.vue";
import RunDetail from "@/components/hrm/common/run-detail.vue";


const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const {hrm_run_status} = proxy.useDict("hrm_run_status");
const {sys_request_method} = proxy.useDict("sys_request_method");
const {hrm_data_type} = proxy.useDict("hrm_data_type");


provide("hrm_data_type", hrm_data_type);

const reportList = ref([]);
const projectOptions = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const showReportDetail = ref(false);
const currentReportId = ref(null);

const data = reactive({
  // form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    reportId: undefined,
    reportName: undefined,
    projectId: undefined,
    moduleId: undefined,
    status: undefined
  }
});

const {queryParams} = toRefs(data);

/** 查询用例列表 */
function getList() {
  loading.value = true;
  ReportApi.list(queryParams.value).then(response => {
    reportList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}


/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.reportId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}


/** 删除按钮操作 */
function handleDelete(row) {
  let detailIds = [];
  if (row.reportId) {
    detailIds = [row.reportId];
  } else {
    detailIds = ids.value
  }
  proxy.$modal.confirm('是否确认删除ID为"' + detailIds + '"的数据项？').then(function () {
    return ReportApi.del({reportIds: detailIds});
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {
  });
}

function handleView(row) {
  let detailIds = row.reportId;
  currentReportId.value = detailIds;
  showReportDetail.value = true;
  // ReportApi.detail(detailIds).then(response => {
  //   alert(JSON.stringify(response, null, 4));
  // });
}


getList();
</script>
