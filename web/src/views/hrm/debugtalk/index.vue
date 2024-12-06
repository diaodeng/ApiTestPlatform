<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="所属项目" prop="projectId">
        <el-select v-model="queryParams.projectId" placeholder="请选择" clearable
                   style="width: 150px">
          <el-option
              v-for="option in projectOptions"
              :key="option.projectId"
              :label="option.projectName"
              :value="option.projectId">
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="状态" clearable style="width: 100px">
          <el-option
              v-for="dict in qtr_data_status"
              :key="dict.value"
              :label="dict.label"
              :value="dict.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button type="default" icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>
    <el-table
        border
        v-if="refreshTable"
        v-loading="loading"
        :data="debugtalkList"
        row-key="debugtalkId"
        :default-expand-all="isExpandAll"
        max-height="calc(100vh - 240px)"
    >
      <el-table-column prop="debugtalkId" label="ID" width="150"></el-table-column>
      <el-table-column label="项目ID" width="150" prop="projectId" align="center">
        <template #default="scope">
          <span>{{ nameOrGlob(scope.row.projectId) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="所属项目" min-width="260" prop="projectName" align="left">
        <template #default="scope">
          <el-text>{{ nameOrGlob(scope.row.projectName) }}</el-text>
        </template>
      </el-table-column>
      <!--         <el-table-column label="所属项目" width="260" :formatter="formatProject" align="center"></el-table-column>-->
      <el-table-column align="left" label="DebugTalk" min-width="115">
        <template #default="scope">
          <el-button link type="primary" @click="handleUpdate(scope.row)"
                     v-hasPermi="['hrm:debugtalk:edit', 'hrm:debugtalk:detail']">debugtalk.py
          </el-button>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" align="center" width="70">
        <template #default="scope">
          <dict-tag :options="qtr_data_status" :value="scope.row.status"/>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" class-name="small-padding fixed-width" width="150">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" prop="updateTime" class-name="small-padding fixed-width" width="150">
        <template #default="scope">
          <span>{{ parseTime(scope.row.updateTime) }}</span>
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

    <!-- 修改debugtalk对话框 -->
    <el-dialog fullscreen :title="title" v-model="open" append-to-body>
      <el-form ref="debugtalkRef" :model="form" :rules="rules" label-width="100px" style="height: 100%">
        <el-container style="height: 100%">
          <el-header height="20px" border="2px" style="border-bottom-color: #97a8be;text-align: right">
            <el-button-group>
              <el-button type="primary" icon="Save" @click="submitForm" v-hasPermi="['hrm:debugtalk:edit']">保存
              </el-button>
              <el-button type="primary" icon="Cancel" @click="cancel">取消</el-button>
            </el-button-group>
          </el-header>

          <el-main style="max-height: calc(100vh - 95px);">

            <AceEditor v-model:content="form.debugtalk" :can-set="true" lang="python" themes="monokai"></AceEditor>

          </el-main>
        </el-container>
      </el-form>

    </el-dialog>
  </div>
</template>

<script setup name="debugtalk">
import AceEditor from "@/components/hrm/common/ace-editor.vue";
import {listDebugTalk, getDebugTalk, addDebugTalk, updateDebugTalk} from "@/api/hrm/debugtalk.js";
import {listProject} from "@/api/hrm/project.js";
import {initDebugTalkFormData} from "@/components/hrm/data-template.js";

const {proxy} = getCurrentInstance();
const {qtr_data_status} = proxy.useDict("qtr_data_status");

const debugtalkList = ref([]);
const total = ref(0);
const projectOptions = ref([]);
const projectList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const title = ref("");
const isExpandAll = ref(true);
const refreshTable = ref(true);
const projectId = ref();
const debugtalk = ref();


const data = reactive({
  queryParams: {
    debugtalkId: undefined,
    projectId: undefined,
    status: undefined,
    pageSize: 10,
    pageNum: 1
  },
  rules: {
    orderNum: [{required: true, message: "显示排序不能为空", trigger: "blur"}]
  },

});
const form = ref({
  debugtalk: JSON.parse(JSON.stringify(initDebugTalkFormData))
});
const {queryParams, rules} = toRefs(data);



function nameOrGlob(val) {
  return val ? val : "全局";
}

/** 查询DebugTalk列表 */
function getList() {
  loading.value = true;
  listDebugTalk(queryParams.value).then(response => {
    debugtalkList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}

/** 取消按钮 */
function cancel() {
  open.value = false;
  reset();
}

/** 表单重置 */
function reset() {
  form.value = {
    debugtalkId: undefined,
    orderNum: 0,
    debugtalk: undefined,
    status: "0"
  };
  proxy.resetForm("debugtalkRef");
}

/** 搜索按钮操作 */
function handleQuery() {
  getList();
}

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  getDebugTalk(row.debugtalkId).then(response => {
    if (!response.data || Object.keys(response.data).length === 0) {
      alert("未查到对应数据！");
      return;
    }
    form.value = response.data;
    open.value = true;
    title.value = "编辑DebugTalk";
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["debugtalkRef"].validate(valid => {
    if (valid) {
      if (form.value.debugtalkId != undefined) {
        updateDebugTalk(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addDebugTalk(form.value).then(response => {
          proxy.$modal.msgSuccess("新增成功");
          open.value = false;
          getList();
        });
      }
    }
  });
}

/** 删除按钮操作 */
function handleDelete(row) {
  proxy.$modal.confirm('是否确认删除名称为"' + row.projectName + '"的数据项?').then(function () {
    return delProject(row.projectId);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {
  });
}

// 格式化项目名称的函数
function formatProject(row, column, cellValue) {
  // 假设每个debugtalk对象都有一个projectId属性，用于从其他地方获取项目名称
  return getProjectName(row.projectId); // getProjectName是一个根据projectId获取项目名称的函数
}

// 获取项目名称的函数（这里应该是你的实际逻辑）
function getProjectName(projectId) {
  // 根据projectId从某个地方（例如另一个数组或API）获取项目名称
  for (const project of projectList.value) {
    if (projectId === project.projectId) {
      return project.projectName;
    }
  }
}


/** 查询项目列表 */
function getProjectSelect() {
  listProject({isPage: false}).then(response => {
    projectOptions.value = response.data;
  });
}

getProjectSelect();
getList();
</script>
<style scoped>
</style>
