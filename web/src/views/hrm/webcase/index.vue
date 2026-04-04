<template>
  <div class="app-container">
    <el-form :inline="true" :model="queryParams" class="mb8">
      <el-form-item label="用例名称">
        <el-input v-model="queryParams.caseName" placeholder="请输入 Web 用例名称" clearable @keyup.enter="getList" />
      </el-form-item>
      <el-form-item label="项目">
        <el-select v-model="queryParams.projectId" clearable filterable placeholder="全部项目" style="width: 180px">
          <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
        </el-select>
      </el-form-item>
      <el-form-item label="模块">
        <el-select v-model="queryParams.moduleId" clearable filterable placeholder="全部模块" style="width: 180px">
          <el-option v-for="item in filteredSearchModules" :key="item.moduleId" :label="item.moduleName" :value="item.moduleId" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="getList">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd">新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="default" plain icon="Refresh" @click="getList">刷新</el-button>
      </el-col>
    </el-row>

    <el-table v-loading="loading.page" :data="pageDataList" border table-layout="fixed" max-height="calc(100vh - 290px)">
      <el-table-column label="Web用例ID" prop="webCaseId" width="150" />
      <el-table-column label="用例名称" prop="caseName" min-width="220" />
      <el-table-column label="项目" min-width="140">
        <template #default="scope">{{ projectNameMap[scope.row.projectId] || scope.row.projectId }}</template>
      </el-table-column>
      <el-table-column label="模块" min-width="140">
        <template #default="scope">{{ moduleNameMap[scope.row.moduleId] || scope.row.moduleId }}</template>
      </el-table-column>
      <el-table-column label="起始地址" prop="startUrl" min-width="240" show-overflow-tooltip />
      <el-table-column label="浏览器" prop="browserName" width="120" />
      <el-table-column label="无头" width="90">
        <template #default="scope">{{ scope.row.headless ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" @click="handleEdit(scope.row)">编辑</el-button>
          <el-button link type="success" icon="CaretRight" @click="openRunDialog(scope.row)">执行</el-button>
          <el-button link type="warning" icon="VideoPlay" @click="openRecordingDialog(scope.row)">录制</el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
          v-model:current-page="queryParams.pageNum"
          v-model:page-size="queryParams.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @size-change="getList"
          @current-change="getList"
      />
    </div>

    <el-dialog v-model="showCaseDialog" :title="caseDialogTitle" width="1100px" destroy-on-close>
      <el-form :model="form" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="用例名称">
              <el-input v-model="form.caseName" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="浏览器">
              <el-select v-model="form.browserName" style="width: 100%">
                <el-option label="Chromium" value="chromium" />
                <el-option label="Firefox" value="firefox" />
                <el-option label="WebKit" value="webkit" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="无头模式">
              <el-switch v-model="form.headless" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目">
              <el-select v-model="form.projectId" clearable filterable style="width: 100%">
                <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模块">
              <el-select v-model="form.moduleId" clearable filterable style="width: 100%">
                <el-option v-for="item in filteredCaseModules" :key="item.moduleId" :label="item.moduleName" :value="item.moduleId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="起始地址">
              <el-input v-model="form.startUrl" placeholder="https://example.com" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="说明">
              <el-input v-model="form.notes" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="步骤JSON">
              <el-input
                  v-model="stepsText"
                  type="textarea"
                  :rows="18"
                  placeholder="录制后会自动回填，也可以手工编辑 JSON。"
                  class="monospace-area"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="showCaseDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading.save" @click="saveCase">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRunDialog" title="执行 Web 用例" width="520px" destroy-on-close>
      <el-form :model="runForm" label-width="110px">
        <el-form-item label="执行 Agent">
          <el-select v-model="runForm.agentId" filterable style="width: 100%">
            <el-option v-for="item in agentOptions" :key="item.agentId" :label="`${item.agentName || item.agentCode} [${item.agentCode}]`" :value="item.agentId" />
          </el-select>
        </el-form-item>
        <el-form-item label="浏览器">
          <el-select v-model="runForm.browserName" style="width: 100%">
            <el-option label="Chromium" value="chromium" />
            <el-option label="Firefox" value="firefox" />
            <el-option label="WebKit" value="webkit" />
          </el-select>
        </el-form-item>
        <el-form-item label="无头模式">
          <el-switch v-model="runForm.headless" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRunDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading.run" @click="submitRun">执行</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRecordingDialog" title="录制 Web 用例" width="980px" destroy-on-close>
      <el-form :model="recordingForm" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="执行 Agent">
              <el-select v-model="recordingForm.agentId" filterable style="width: 100%">
                <el-option v-for="item in agentOptions" :key="item.agentId" :label="`${item.agentName || item.agentCode} [${item.agentCode}]`" :value="item.agentId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="浏览器">
              <el-select v-model="recordingForm.browserName" style="width: 100%">
                <el-option label="Chromium" value="chromium" />
                <el-option label="Firefox" value="firefox" />
                <el-option label="WebKit" value="webkit" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="无头模式">
              <el-switch v-model="recordingForm.headless" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="起始地址">
              <el-input v-model="recordingForm.startUrl" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <div class="recording-toolbar">
        <el-button type="primary" :loading="loading.recording" @click="startRecording">开始录制</el-button>
        <el-button type="warning" :disabled="!recordingForm.recordingId" @click="stopRecording">停止录制</el-button>
        <el-button type="success" :disabled="!recordingForm.recordingId" @click="applyRecording">应用到当前用例</el-button>
        <el-button :disabled="!recordingForm.recordingId" @click="refreshRecording">刷新详情</el-button>
        <span class="recording-meta">会话ID：{{ recordingForm.recordingId || '-' }}</span>
      </div>
      <el-table :data="recordingEvents" border max-height="360px">
        <el-table-column label="序号" prop="eventIndex" width="80" />
        <el-table-column label="动作" prop="payload.actionType" width="140">
          <template #default="scope">{{ scope.row.payload?.actionType }}</template>
        </el-table-column>
        <el-table-column label="名称" prop="payload.stepName" min-width="220">
          <template #default="scope">{{ scope.row.payload?.stepName }}</template>
        </el-table-column>
        <el-table-column label="元素文本" min-width="220">
          <template #default="scope">{{ scope.row.payload?.targetSnapshot?.elementText }}</template>
        </el-table-column>
      </el-table>
      <el-input v-model="recordingDetailText" type="textarea" :rows="10" readonly class="monospace-area mt16" />
    </el-dialog>
  </div>
</template>

<script setup name="WebCase">
import { ElMessage, ElMessageBox } from "element-plus";
import { all as getAllAgent } from "@/api/hrm/agent.js";
import { listProject } from "@/api/hrm/project.js";
import { showModulList } from "@/api/hrm/module.js";
import {
  addWebCase,
  applyWebRecording,
  delWebCase,
  getWebCase,
  getWebRecording,
  listWebCase,
  runWebCase,
  startWebRecording,
  stopWebRecording,
  updateWebCase,
} from "@/api/hrm/web_case.js";

const pageDataList = ref([]);
const total = ref(0);
const loading = ref({ page: false, save: false, run: false, recording: false });
const projectOptions = ref([]);
const moduleOptions = ref([]);
const agentOptions = ref([]);
const selectedCase = ref(null);
const recordingEvents = ref([]);
const recordingDetailText = ref("");
let recordingTimer = null;

const queryParams = ref({
  pageNum: 1,
  pageSize: 10,
  caseName: undefined,
  projectId: undefined,
  moduleId: undefined,
});

const showCaseDialog = ref(false);
const showRunDialog = ref(false);
const showRecordingDialog = ref(false);
const stepsText = ref("[]");

const form = ref({
  webCaseId: undefined,
  caseName: "新增 Web 用例",
  projectId: undefined,
  moduleId: undefined,
  startUrl: "",
  browserName: "chromium",
  headless: false,
  runtimeSettings: {},
  notes: "",
  status: 2,
  remark: "",
});

const runForm = ref({
  agentId: undefined,
  browserName: "chromium",
  headless: true,
});

const recordingForm = ref({
  webCaseId: undefined,
  agentId: undefined,
  browserName: "chromium",
  headless: false,
  startUrl: "",
  recordingId: undefined,
});

const projectNameMap = computed(() => Object.fromEntries(projectOptions.value.map((item) => [item.projectId, item.projectName])));
const moduleNameMap = computed(() => Object.fromEntries(moduleOptions.value.map((item) => [item.moduleId, item.moduleName])));
const filteredSearchModules = computed(() => {
  if (!queryParams.value.projectId) return moduleOptions.value;
  return moduleOptions.value.filter((item) => item.projectId === queryParams.value.projectId);
});
const filteredCaseModules = computed(() => {
  if (!form.value.projectId) return moduleOptions.value;
  return moduleOptions.value.filter((item) => item.projectId === form.value.projectId);
});
const caseDialogTitle = computed(() => `${form.value.webCaseId ? "编辑" : "新增"} Web 用例`);

function resetQuery() {
  queryParams.value = {
    pageNum: 1,
    pageSize: 10,
    caseName: undefined,
    projectId: undefined,
    moduleId: undefined,
  };
  getList();
}

function resetForm() {
  form.value = {
    webCaseId: undefined,
    caseName: "新增 Web 用例",
    projectId: undefined,
    moduleId: undefined,
    startUrl: "",
    browserName: "chromium",
    headless: false,
    runtimeSettings: {},
    notes: "",
    status: 2,
    remark: "",
  };
  stepsText.value = "[]";
}

async function loadBaseData() {
  const [projectRes, moduleRes, agentRes] = await Promise.all([
    listProject({ isPage: false }),
    showModulList({ isPage: false }),
    getAllAgent(),
  ]);
  projectOptions.value = projectRes.data || projectRes.rows || [];
  moduleOptions.value = moduleRes.data || moduleRes.rows || [];
  agentOptions.value = agentRes.data || agentRes.rows || [];
}

function getList() {
  loading.value.page = true;
  listWebCase(queryParams.value).then((response) => {
    pageDataList.value = response.rows || [];
    total.value = response.total || 0;
  }).finally(() => {
    loading.value.page = false;
  });
}

function handleAdd() {
  resetForm();
  showCaseDialog.value = true;
}

function handleEdit(row) {
  getWebCase(row.webCaseId).then((response) => {
    const data = response.data || {};
    form.value = { ...form.value, ...data };
    stepsText.value = JSON.stringify(data.steps || [], null, 2);
    showCaseDialog.value = true;
  });
}

function handleDelete(row) {
  ElMessageBox.confirm(`是否确认删除 Web 用例【${row.caseName}】？`, "提示", { type: "warning" }).then(() => {
    return delWebCase(row.webCaseId);
  }).then(() => {
    ElMessage.success("删除成功");
    getList();
  }).catch(() => {});
}

function saveCase() {
  loading.value.save = true;
  let steps = [];
  try {
    steps = JSON.parse(stepsText.value || "[]");
    if (!Array.isArray(steps)) throw new Error("步骤 JSON 必须是数组");
  } catch (error) {
    loading.value.save = false;
    ElMessage.error(`步骤 JSON 解析失败：${error.message}`);
    return;
  }
  const payload = { ...form.value, steps };
  const request = payload.webCaseId ? updateWebCase(payload) : addWebCase(payload);
  request.then(() => {
    ElMessage.success("保存成功");
    showCaseDialog.value = false;
    getList();
  }).finally(() => {
    loading.value.save = false;
  });
}

function openRunDialog(row) {
  selectedCase.value = row;
  runForm.value.browserName = row.browserName || "chromium";
  runForm.value.headless = row.headless ?? true;
  showRunDialog.value = true;
}

function submitRun() {
  if (!selectedCase.value?.webCaseId) {
    ElMessage.error("请选择要执行的 Web 用例");
    return;
  }
  loading.value.run = true;
  runWebCase({
    webCaseId: selectedCase.value.webCaseId,
    agentId: runForm.value.agentId,
    browserName: runForm.value.browserName,
    headless: runForm.value.headless,
  }).then((response) => {
    const resultText = JSON.stringify(response.data || {}, null, 2);
    ElMessage.success("执行指令已完成，详细结果已返回");
    recordingDetailText.value = resultText;
    showRunDialog.value = false;
  }).finally(() => {
    loading.value.run = false;
  });
}

function openRecordingDialog(row) {
  selectedCase.value = row;
  recordingEvents.value = [];
  recordingDetailText.value = "";
  recordingForm.value = {
    webCaseId: row.webCaseId,
    agentId: undefined,
    browserName: row.browserName || "chromium",
    headless: false,
    startUrl: row.startUrl || "",
    recordingId: undefined,
  };
  showRecordingDialog.value = true;
}

function startRecordingPoll() {
  stopRecordingPoll();
  recordingTimer = window.setInterval(() => {
    if (recordingForm.value.recordingId) {
      refreshRecording();
    }
  }, 3000);
}

function stopRecordingPoll() {
  if (recordingTimer) {
    window.clearInterval(recordingTimer);
    recordingTimer = null;
  }
}

function startRecording() {
  loading.value.recording = true;
  startWebRecording({
    webCaseId: recordingForm.value.webCaseId,
    agentId: recordingForm.value.agentId,
    browserName: recordingForm.value.browserName,
    headless: recordingForm.value.headless,
    startUrl: recordingForm.value.startUrl,
  }).then((response) => {
    recordingForm.value.recordingId = response.data?.recordingId;
    ElMessage.success("录制已启动");
    refreshRecording();
    startRecordingPoll();
  }).finally(() => {
    loading.value.recording = false;
  });
}

function stopRecording() {
  if (!recordingForm.value.recordingId) return;
  stopWebRecording({ recordingId: recordingForm.value.recordingId, agentId: recordingForm.value.agentId }).then(() => {
    ElMessage.success("已发送停止录制指令");
    stopRecordingPoll();
    refreshRecording();
  });
}

function refreshRecording() {
  if (!recordingForm.value.recordingId) return;
  getWebRecording(recordingForm.value.recordingId).then((response) => {
    const data = response.data || {};
    recordingEvents.value = data.events || [];
    recordingDetailText.value = JSON.stringify(data, null, 2);
  });
}

function applyRecording() {
  if (!recordingForm.value.recordingId || !selectedCase.value?.webCaseId) return;
  applyWebRecording({
    recordingId: recordingForm.value.recordingId,
    webCaseId: selectedCase.value.webCaseId,
    replaceSteps: true,
  }).then(() => {
    ElMessage.success("录制步骤已应用到当前用例");
    handleEdit(selectedCase.value);
    getList();
  });
}

onMounted(async () => {
  await loadBaseData();
  getList();
});

onBeforeUnmount(() => {
  stopRecordingPoll();
});
</script>

<style scoped lang="scss">
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.recording-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 12px 0 16px;
}

.recording-meta {
  color: #606266;
  font-size: 12px;
}

.monospace-area :deep(textarea) {
  font-family: Consolas, Monaco, monospace;
}

.mt16 {
  margin-top: 16px;
}
</style>
