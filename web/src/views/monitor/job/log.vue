<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="80px">
      <el-form-item label="任务名称" prop="taskName">
        <el-input
          v-model="queryParams.taskName"
          placeholder="请输入任务名称"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="执行状态" prop="status">
        <el-select v-model="queryParams.status" clearable placeholder="请选择" style="width: 160px">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
          <el-option label="运行中" value="running" />
          <el-option label="跳过" value="skipped" />
        </el-select>
      </el-form-item>
      <el-form-item label="触发方式" prop="triggerType">
        <el-select v-model="queryParams.triggerType" clearable placeholder="请选择" style="width: 160px">
          <el-option label="调度触发" value="scheduler" />
          <el-option label="手动触发" value="manual" />
          <el-option label="单次触发" value="once" />
        </el-select>
      </el-form-item>
      <el-form-item label="执行时间" style="width: 320px">
        <el-date-picker
          v-model="dateRange"
          value-format="YYYY-MM-DD"
          type="daterange"
          range-separator="-"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
          v-hasPermi="['monitor:job:remove']"
        >
          删除
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="danger" plain icon="Delete" @click="handleClean" v-hasPermi="['monitor:job:remove']">清空</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="warning" plain icon="Download" @click="handleExport" v-hasPermi="['monitor:job:export']">导出</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="warning" plain icon="Close" @click="handleClose">关闭</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="jobLogList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="日志ID" width="90" align="center" prop="logId" />
      <el-table-column label="任务ID" width="90" align="center" prop="taskId" />
      <el-table-column label="任务名称" align="center" prop="taskName" :show-overflow-tooltip="true" />
      <el-table-column label="任务注册键" align="center" prop="taskKey" :show-overflow-tooltip="true" />
      <el-table-column label="触发方式" align="center" prop="triggerType" width="110" />
      <el-table-column label="执行状态" align="center" width="100">
        <template #default="scope">
          <el-tag :type="statusTagType(scope.row.status)">
            {{ scope.row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="日志信息" align="center" prop="message" :show-overflow-tooltip="true" />
      <el-table-column label="执行时间" align="center" prop="createTime" width="180">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="handleView(scope.row)" v-hasPermi="['monitor:job:query']">
            详细
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

    <el-dialog title="执行日志详情" v-model="open" width="760px" append-to-body>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="日志ID">{{ form.logId }}</el-descriptions-item>
        <el-descriptions-item label="任务ID">{{ form.taskId }}</el-descriptions-item>
        <el-descriptions-item label="任务名称">{{ form.taskName }}</el-descriptions-item>
        <el-descriptions-item label="任务注册键">{{ form.taskKey }}</el-descriptions-item>
        <el-descriptions-item label="触发方式">{{ form.triggerType }}</el-descriptions-item>
        <el-descriptions-item label="执行状态">{{ form.status }}</el-descriptions-item>
        <el-descriptions-item label="调度快照" :span="2">{{ form.scheduleDesc }}</el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ parseTime(form.startedAt) }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ parseTime(form.finishedAt) }}</el-descriptions-item>
        <el-descriptions-item label="耗时(ms)">{{ form.durationMs }}</el-descriptions-item>
        <el-descriptions-item label="日志时间">{{ parseTime(form.createTime) }}</el-descriptions-item>
        <el-descriptions-item label="位置参数" :span="2">{{ form.taskArgs }}</el-descriptions-item>
        <el-descriptions-item label="关键字参数" :span="2">{{ form.taskKwargs }}</el-descriptions-item>
        <el-descriptions-item label="日志信息" :span="2">{{ form.message }}</el-descriptions-item>
        <el-descriptions-item label="异常信息" :span="2">{{ form.exceptionInfo }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="open = false">关 闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="JobLog">
import { getJob } from "@/api/monitor/job";
import { cleanJobLog, delJobLog, listJobLog } from "@/api/monitor/jobLog";

const { proxy } = getCurrentInstance();
const route = useRoute();

const jobLogList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const multiple = ref(true);
const total = ref(0);
const dateRange = ref([]);

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    taskId: undefined,
    taskName: undefined,
    status: undefined,
    triggerType: undefined,
  },
});

const { queryParams, form } = toRefs(data);

function statusTagType(status) {
  if (status === "success") return "success";
  if (status === "failed") return "danger";
  if (status === "running") return "warning";
  if (status === "skipped") return "info";
  return "";
}

function getList() {
  loading.value = true;
  listJobLog(proxy.addDateRange(queryParams.value, dateRange.value))
    .then((response) => {
      jobLogList.value = response.rows;
      total.value = response.total;
    })
    .finally(() => {
      loading.value = false;
    });
}

function handleClose() {
  proxy.$tab.closeOpenPage({ path: "/monitor/job" });
}

function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

function resetQuery() {
  dateRange.value = [];
  proxy.resetForm("queryRef");
  handleQuery();
}

function handleSelectionChange(selection) {
  ids.value = selection.map((item) => item.logId);
  multiple.value = !selection.length;
}

function handleView(row) {
  form.value = row;
  open.value = true;
}

function handleDelete() {
  proxy.$modal
    .confirm(`是否确认删除调度日志编号为"${ids.value.join(",")}"的数据项?`)
    .then(() => delJobLog(ids.value.join(",")))
    .then(() => {
      getList();
      proxy.$modal.msgSuccess("删除成功");
    })
    .catch(() => {});
}

function handleClean() {
  proxy.$modal
    .confirm("是否确认清空所有调度日志数据项?")
    .then(() => cleanJobLog())
    .then(() => {
      getList();
      proxy.$modal.msgSuccess("清空成功");
    })
    .catch(() => {});
}

function handleExport() {
  proxy.download(
    "monitor/jobLog/export",
    {
      ...queryParams.value,
    },
    `job_log_${new Date().getTime()}.xlsx`
  );
}

(() => {
  const taskId = route.params && route.params.jobId;
  if (taskId !== undefined && taskId !== "0") {
    getJob(taskId).then((response) => {
      queryParams.value.taskName = response.data.taskName;
      queryParams.value.taskId = response.data.taskId;
      getList();
    });
  } else {
    getList();
  }
})();
</script>
