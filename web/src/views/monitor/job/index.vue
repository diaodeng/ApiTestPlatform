<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="任务名称" prop="taskName">
        <el-input
          v-model="queryParams.taskName"
          placeholder="请输入任务名称"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="调度类型" prop="scheduleType">
        <el-select v-model="queryParams.scheduleType" clearable placeholder="请选择" style="width: 160px">
          <el-option v-for="item in scheduleTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="执行方式" prop="executionMode">
        <el-select v-model="queryParams.executionMode" clearable placeholder="请选择" style="width: 160px">
          <el-option v-for="item in executionModeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="启用状态" prop="enabled">
        <el-select v-model="queryParams.enabled" clearable placeholder="请选择" style="width: 160px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['monitor:job:add']">新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="Edit"
          :disabled="single"
          @click="handleUpdate"
          v-hasPermi="['monitor:job:edit']"
        >
          修改
        </el-button>
      </el-col>
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
        <el-button type="warning" plain icon="Download" @click="handleExport" v-hasPermi="['monitor:job:export']">
          导出
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="info" plain icon="Operation" @click="handleJobLog" v-hasPermi="['monitor:job:query']">
          日志
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="primary" plain icon="VideoPlay" @click="handleOpenRunningJobs" v-hasPermi="['monitor:job:query']">
          执行中
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="jobList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="任务ID" width="90" align="center" prop="taskId" />
      <el-table-column label="任务名称" align="center" prop="taskName" :show-overflow-tooltip="true" />
      <el-table-column label="任务注册键" align="center" prop="taskKey" :show-overflow-tooltip="true" />
      <el-table-column label="执行方式" align="center" width="100">
        <template #default="scope">
          {{ executionModeLabel(scope.row.executionMode) }}
        </template>
      </el-table-column>
      <el-table-column label="调度类型" align="center" width="110">
        <template #default="scope">
          {{ scheduleTypeLabel(scope.row.scheduleType) }}
        </template>
      </el-table-column>
      <el-table-column label="调度表达式" align="center" min-width="220" :show-overflow-tooltip="true">
        <template #default="scope">
          {{ scheduleDisplay(scope.row) }}
        </template>
      </el-table-column>
      <el-table-column label="最近状态" align="center" width="100">
        <template #default="scope">
          <el-tag :type="statusTagType(scope.row.lastStatus)">
            {{ scope.row.lastStatus || "未执行" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="启用" align="center" width="90">
        <template #default="scope">
          <el-switch v-model="scope.row.enabled" @change="handleStatusChange(scope.row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="270" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-tooltip content="修改" placement="top">
            <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['monitor:job:edit']" />
          </el-tooltip>
          <el-tooltip content="删除" placement="top">
            <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['monitor:job:remove']" />
          </el-tooltip>
          <el-tooltip content="执行一次" placement="top">
            <el-button
              link
              type="primary"
              icon="CaretRight"
              @click="handleRun(scope.row)"
              v-hasPermi="['monitor:job:changeStatus']"
            />
          </el-tooltip>
          <el-tooltip content="任务详细" placement="top">
            <el-button link type="primary" icon="View" @click="handleView(scope.row)" v-hasPermi="['monitor:job:query']" />
          </el-tooltip>
          <el-tooltip content="查看日志" placement="top">
            <el-button link type="primary" icon="Operation" @click="handleJobLog(scope.row)" v-hasPermi="['monitor:job:query']" />
          </el-tooltip>
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

    <el-dialog :title="title" v-model="open" width="860px" append-to-body>
      <el-form ref="jobRef" :model="form" :rules="rules" label-width="120px">
        <el-row>
          <el-col :span="12">
            <el-form-item label="任务名称" prop="taskName">
              <el-input v-model="form.taskName" placeholder="请输入任务名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="任务注册键" prop="taskKey">
              <el-select v-model="form.taskKey" filterable placeholder="请选择任务注册键">
                <el-option v-for="item in taskKeyOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="执行方式" prop="executionMode">
              <el-select v-model="form.executionMode" placeholder="请选择">
                <el-option v-for="item in executionModeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-alert
              v-if="form.executionMode === 'process' && processWorkerAvailable === false"
              title="未检测到进程模式 Worker（sys_process 队列），该任务将无法被执行，请先启动 Worker 或切换为线程模式"
              type="warning"
              :closable="false"
              show-icon
              style="margin-bottom: 18px"
            />
          </el-col>
          <el-col :span="12">
            <el-form-item label="调度类型" prop="scheduleType">
              <el-select v-model="form.scheduleType" placeholder="请选择">
                <el-option v-for="item in scheduleTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24" v-if="form.scheduleType === 'crontab'">
            <el-form-item label="Cron表达式" prop="cronExpression">
              <el-input v-model="form.cronExpression" placeholder="请输入 Celery 兼容 5 位 Cron（分 时 日 月 周）">
                <template #append>
                  <el-button type="primary" @click="handleShowCron">生成表达式</el-button>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12" v-if="form.scheduleType === 'interval'">
            <el-form-item label="间隔步长" prop="intervalEvery">
              <el-input-number v-model="form.intervalEvery" :min="1" controls-position="right" />
            </el-form-item>
          </el-col>
          <el-col :span="12" v-if="form.scheduleType === 'interval'">
            <el-form-item label="间隔单位" prop="intervalPeriod">
              <el-select v-model="form.intervalPeriod" placeholder="请选择">
                <el-option v-for="item in intervalPeriodOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24" v-if="form.scheduleType === 'once'">
            <el-form-item label="触发时间" prop="oneOffEta">
              <el-date-picker
                v-model="form.oneOffEta"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                placeholder="请选择单次执行时间"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="任务参数" prop="taskKwargs">
              <AceEditor
                v-model:content="form.taskKwargs"
                lang="json"
                themes="monokai"
                height="220px"
                width="700px"
                placeholder='请输入 JSON 对象，例如 {"k":"v"}'
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="允许并发" prop="allowConcurrent">
              <el-switch v-model="form.allowConcurrent" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="锁超时(秒)" prop="lockTtlSeconds">
              <el-input-number v-model="form.lockTtlSeconds" :min="30" controls-position="right" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用状态" prop="enabled">
              <el-switch v-model="form.enabled" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注" prop="remark">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="submitForm">确 定</el-button>
          <el-button @click="cancel">取 消</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog title="Cron表达式生成器" v-model="openCron" append-to-body destroy-on-close>
      <crontab ref="crontabRef" @hide="openCron = false" @fill="crontabFill" :expression="expression" />
    </el-dialog>

    <el-dialog title="执行中任务" v-model="runningOpen" width="980px" append-to-body>
      <el-button type="primary" plain icon="Refresh" @click="getRunningJobs" :loading="runningLoading" style="margin-bottom: 12px">
        刷新
      </el-button>
      <el-table :data="runningTasks" v-loading="runningLoading" max-height="460">
        <el-table-column label="Celery任务ID" prop="celeryTaskId" min-width="260" :show-overflow-tooltip="true" />
        <el-table-column label="任务ID" prop="taskId" width="90" />
        <el-table-column label="任务名称" prop="taskName" min-width="160" :show-overflow-tooltip="true" />
        <el-table-column label="执行方式" width="100">
          <template #default="scope">
            {{ executionModeLabel(scope.row.executionMode) }}
          </template>
        </el-table-column>
        <el-table-column label="队列" prop="queueName" min-width="120" :show-overflow-tooltip="true" />
        <el-table-column label="状态" prop="runtimeStateLabel" width="100" />
        <el-table-column label="Worker" prop="worker" min-width="170" :show-overflow-tooltip="true" />
        <el-table-column label="开始时间" prop="startedAt" min-width="150" />
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="scope">
            <el-button link type="warning" @click="handleCancelRunningJob(scope.row)" v-hasPermi="['monitor:job:changeStatus']">
              取消
            </el-button>
            <el-button link type="danger" @click="handleTerminateRunningJob(scope.row)" v-hasPermi="['monitor:job:changeStatus']">
              终止
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="runningOpen = false">关 闭</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog title="任务详细" v-model="openView" width="760px" append-to-body>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="任务ID">{{ form.taskId }}</el-descriptions-item>
        <el-descriptions-item label="任务名称">{{ form.taskName }}</el-descriptions-item>
        <el-descriptions-item label="任务注册键">{{ form.taskKey }}</el-descriptions-item>
        <el-descriptions-item label="执行方式">{{ executionModeLabel(form.executionMode) }}</el-descriptions-item>
        <el-descriptions-item label="队列">{{ form.queueName }}</el-descriptions-item>
        <el-descriptions-item label="调度类型">{{ scheduleTypeLabel(form.scheduleType) }}</el-descriptions-item>
        <el-descriptions-item label="调度表达式">{{ scheduleDisplay(form) }}</el-descriptions-item>
        <el-descriptions-item label="最近状态">{{ form.lastStatus || "未执行" }}</el-descriptions-item>
        <el-descriptions-item label="最近执行">{{ parseTime(form.lastRunAt) }}</el-descriptions-item>
        <el-descriptions-item label="累计执行次数">{{ form.runCount }}</el-descriptions-item>
        <el-descriptions-item label="是否启用">{{ form.enabled ? "启用" : "停用" }}</el-descriptions-item>
        <el-descriptions-item label="允许并发">{{ form.allowConcurrent ? "是" : "否" }}</el-descriptions-item>
        <el-descriptions-item label="锁超时(秒)">{{ form.lockTtlSeconds }}</el-descriptions-item>
        <el-descriptions-item label="任务参数" :span="2">{{ form.taskKwargs }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="openView = false">关 闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="Job">
import {
  addJob,
  cancelRunningJob,
  changeJobStatus,
  checkWorker,
  delJob,
  getJob,
  listJob,
  listRunningJobs,
  listTaskKeyOptions,
  runJob,
  terminateRunningJob,
  updateJob,
} from "@/api/monitor/job";
import Crontab from "@/components/Crontab";
import AceEditor from "@/components/hrm/common/ace-editor.vue";

const router = useRouter();
const { proxy } = getCurrentInstance();

const jobList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const openView = ref(false);
const openCron = ref(false);
const expression = ref("");
const taskKeyOptions = ref([]);
const runningOpen = ref(false);
const runningLoading = ref(false);
const runningTasks = ref([]);

const scheduleTypeOptions = [
  { label: "Cron", value: "crontab" },
  { label: "间隔", value: "interval" },
  { label: "单次", value: "once" },
];
const executionModeOptions = [
  { label: "线程", value: "thread" },
  { label: "进程", value: "process" },
];
const intervalPeriodOptions = [
  { label: "秒", value: "seconds" },
  { label: "分", value: "minutes" },
  { label: "小时", value: "hours" },
  { label: "天", value: "days" },
];

const validateJsonObject = (rule, value, callback) => {
  try {
    const parsed = JSON.parse(value || "{}");
    if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") {
      callback(new Error("必须是 JSON 对象"));
      return;
    }
    callback();
  } catch (error) {
    callback(new Error("JSON 格式不正确"));
  }
};

const validateSchedule = (rule, value, callback) => {
  if (form.value.scheduleType === "crontab" && !form.value.cronExpression) {
    callback(new Error("Cron 表达式不能为空"));
    return;
  }
  if (form.value.scheduleType === "interval" && !form.value.intervalEvery) {
    callback(new Error("间隔步长不能为空"));
    return;
  }
  if (form.value.scheduleType === "interval" && !form.value.intervalPeriod) {
    callback(new Error("间隔单位不能为空"));
    return;
  }
  if (form.value.scheduleType === "once" && !form.value.oneOffEta) {
    callback(new Error("触发时间不能为空"));
    return;
  }
  callback();
};

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    taskName: undefined,
    scheduleType: undefined,
    executionMode: undefined,
    enabled: undefined,
  },
  rules: {
    taskName: [{ required: true, message: "任务名称不能为空", trigger: "blur" }],
    taskKey: [{ required: true, message: "任务注册键不能为空", trigger: "change" }],
    executionMode: [{ required: true, message: "执行方式不能为空", trigger: "change" }],
    scheduleType: [{ required: true, message: "调度类型不能为空", trigger: "change" }],
    cronExpression: [{ validator: validateSchedule, trigger: "blur" }],
    intervalEvery: [{ validator: validateSchedule, trigger: "change" }],
    intervalPeriod: [{ validator: validateSchedule, trigger: "change" }],
    oneOffEta: [{ validator: validateSchedule, trigger: "change" }],
    taskKwargs: [{ validator: validateJsonObject, trigger: "blur" }],
  },
});

const { queryParams, form, rules } = toRefs(data);

/** 进程模式 Worker 是否在线（null=尚未检测） */
const processWorkerAvailable = ref(null);
/** 是否正在检测 Worker */
const checkingWorker = ref(false);

/**
 * 检查进程模式 Celery Worker 是否在线。
 */
async function doCheckWorker() {
  if (form.value.executionMode !== "process") {
    processWorkerAvailable.value = null;
    return;
  }
  checkingWorker.value = true;
  try {
    const res = await checkWorker();
    processWorkerAvailable.value = res?.data?.available ?? false;
  } catch {
    processWorkerAvailable.value = false;
  } finally {
    checkingWorker.value = false;
  }
}

// 当用户切换执行方式为"进程"时，自动检测 Worker 状态
watch(() => form.value.executionMode, () => {
  doCheckWorker();
});

function defaultTaskKey() {
  return taskKeyOptions.value?.[0]?.value || "module_task.scheduler_test.job";
}

function defaultForm() {
  return {
    taskId: undefined,
    taskName: undefined,
    taskKey: defaultTaskKey(),
    queueName: "sys",
    executionMode: "thread",
    scheduleType: "crontab",
    cronExpression: "0 0 * * *",
    intervalEvery: 1,
    intervalPeriod: "minutes",
    oneOffEta: undefined,
    taskArgs: "[]",
    taskKwargs: "{}",
    enabled: true,
    allowConcurrent: false,
    lockTtlSeconds: 3600,
    remark: "",
  };
}

function normalizeFormData(data) {
  return {
    ...defaultForm(),
    ...data,
    taskArgs: "[]",
    taskKwargs: data?.taskKwargs || "{}",
    queueName: "sys",
    executionMode: data?.executionMode || "thread",
    taskKey: data?.taskKey || defaultTaskKey(),
  };
}

function executionModeLabel(value) {
  const found = executionModeOptions.find((item) => item.value === value);
  return found ? found.label : value || "-";
}

function scheduleTypeLabel(value) {
  const found = scheduleTypeOptions.find((item) => item.value === value);
  return found ? found.label : value || "-";
}

function scheduleDisplay(row) {
  if (!row) return "-";
  if (row.scheduleType === "interval") {
    return `every ${row.intervalEvery} ${row.intervalPeriod}`;
  }
  if (row.scheduleType === "once") {
    return row.oneOffEta || "-";
  }
  return row.cronExpression || "-";
}

function statusTagType(status) {
  if (status === "success") return "success";
  if (status === "failed") return "danger";
  if (status === "running") return "warning";
  if (status === "skipped") return "info";
  return "";
}

function getTaskKeyOptions() {
  listTaskKeyOptions().then((response) => {
    taskKeyOptions.value = response.data || [];
    if (!form.value.taskId && !form.value.taskKey) {
      form.value.taskKey = defaultTaskKey();
    }
  });
}

function getList() {
  loading.value = true;
  listJob(queryParams.value)
    .then((response) => {
      jobList.value = response.rows;
      total.value = response.total;
    })
    .finally(() => {
      loading.value = false;
    });
}

function cancel() {
  open.value = false;
  reset();
}

function reset() {
  form.value = defaultForm();
  proxy.resetForm("jobRef");
}

function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}

function handleSelectionChange(selection) {
  ids.value = selection.map((item) => item.taskId);
  single.value = selection.length !== 1;
  multiple.value = !selection.length;
}

function handleStatusChange(row) {
  const text = row.enabled ? "启用" : "停用";
  proxy.$modal
    .confirm(`确认要${text}任务"${row.taskName}"吗?`)
    .then(() => changeJobStatus(row.taskId, row.enabled))
    .then(() => {
      proxy.$modal.msgSuccess(`${text}成功`);
    })
    .catch(() => {
      row.enabled = !row.enabled;
    });
}

function handleRun(row) {
  proxy.$modal
    .confirm(`确认要立即执行一次"${row.taskName}"任务吗?`)
    .then(() => runJob(row.taskId))
    .then(() => {
      proxy.$modal.msgSuccess("任务已提交执行");
    })
    .catch(() => {});
}

function handleView(row) {
  getJob(row.taskId).then((response) => {
    form.value = normalizeFormData(response.data);
    openView.value = true;
  });
}

function handleShowCron() {
  expression.value = form.value.cronExpression;
  openCron.value = true;
}

function crontabFill(value) {
  form.value.cronExpression = value;
}

function handleJobLog(row) {
  const taskId = row?.taskId || 0;
  const taskName = row?.taskName;
  router.push({
    path: "/monitor/job-log/index/" + taskId,
    query: taskName ? { taskName } : undefined,
  });
}

function handleOpenRunningJobs() {
  runningOpen.value = true;
  getRunningJobs();
}

function getRunningJobs() {
  runningLoading.value = true;
  listRunningJobs()
    .then((response) => {
      runningTasks.value = response.data || [];
    })
    .finally(() => {
      runningLoading.value = false;
    });
}

function handleCancelRunningJob(row) {
  if (!row?.celeryTaskId) return;
  proxy.$modal
    .confirm(`确认要取消任务 "${row.taskName || row.taskId || row.celeryTaskId}" 吗?`)
    .then(() => cancelRunningJob(row.celeryTaskId))
    .then(() => {
      proxy.$modal.msgSuccess("已发送取消指令");
      getRunningJobs();
    })
    .catch(() => {});
}

function handleTerminateRunningJob(row) {
  if (!row?.celeryTaskId) return;
  proxy.$modal
    .confirm(`确认要终止任务 "${row.taskName || row.taskId || row.celeryTaskId}" 吗?`)
    .then(() => terminateRunningJob(row.celeryTaskId))
    .then(() => {
      proxy.$modal.msgSuccess("已发送终止指令");
      getRunningJobs();
    })
    .catch(() => {});
}

function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加任务";
}

function handleUpdate(row) {
  reset();
  const taskId = row?.taskId || ids.value[0];
  getJob(taskId).then((response) => {
    form.value = normalizeFormData(response.data);
    open.value = true;
    title.value = "修改任务";
  });
}

function submitForm() {
  proxy.$refs["jobRef"].validate(async (valid) => {
    if (!valid) return;

    const doSave = () => {
      const payload = { ...form.value };
      payload.queueName = undefined;
      payload.taskArgs = "[]";
      if (payload.scheduleType !== "crontab") payload.cronExpression = undefined;
      if (payload.scheduleType !== "interval") {
        payload.intervalEvery = undefined;
        payload.intervalPeriod = undefined;
      }
      if (payload.scheduleType !== "once") payload.oneOffEta = undefined;

      if (payload.taskId !== undefined) {
        updateJob(payload).then(() => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addJob(payload).then(() => {
          proxy.$modal.msgSuccess("新增成功");
          open.value = false;
          getList();
        });
      }
    };

    // 如果选择了进程模式，但 Worker 不可用，弹框警告
    if (form.value.executionMode === "process" && processWorkerAvailable.value === false) {
      proxy.$modal
        .confirm(
          "未检测到进程模式 Celery Worker（sys_process 队列），该任务将无法被执行。<br/>是否仍要保存？",
          "进程 Worker 缺失",
          { confirmButtonText: "仍要保存", cancelButtonText: "取消", type: "warning", dangerouslyUseHTMLString: true }
        )
        .then(() => {
          doSave();
        })
        .catch(() => {});
      return;
    }

    doSave();
  });
}

function handleDelete(row) {
  const taskIds = row?.taskId || ids.value.join(",");
  proxy.$modal
    .confirm(`是否确认删除任务编号为"${taskIds}"的数据项?`)
    .then(() => delJob(taskIds))
    .then(() => {
      getList();
      proxy.$modal.msgSuccess("删除成功");
    })
    .catch(() => {});
}

function handleExport() {
  proxy.download(
    "monitor/job/export",
    {
      ...queryParams.value,
    },
    `job_${new Date().getTime()}.xlsx`
  );
}

reset();
getTaskKeyOptions();
getList();
</script>
