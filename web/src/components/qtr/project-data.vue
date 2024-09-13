<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="项目名称" prop="projectName">
        <el-input
            v-model="queryParams.projectName"
            placeholder="请输入项目名称"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="项目状态" clearable style="width: 200px">
          <el-option
              v-for="dict in sys_normal_disable"
              :key="dict.value"
              :label="dict.label"
              :value="dict.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>
    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" @click="saveConfigSuite">保存</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table
        border
        v-if="refreshTable"
        v-loading="loading"
        :data="projectList"
        style="width: 100%"
        height="350"
        row-key="projectId"
        :default-expand-all="isExpandAll"
        @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column prop="projectId" label="ID" width="150"></el-table-column>
      <el-table-column prop="projectName" align="center" label="项目名称" width="200"></el-table-column>
      <el-table-column prop="responsibleName" align="center" label="负责人" width="120"></el-table-column>
      <el-table-column prop="testUser" label="测试负责人" align="center" width="120"></el-table-column>
      <el-table-column prop="devUser" label="开发负责人" align="center" width="120"></el-table-column>
      <el-table-column prop="orderNum" label="排序" align="center" width="100"></el-table-column>
      <el-table-column prop="status" label="状态" align="center" width="100">
        <template #default="scope">
          <dict-tag :options="sys_normal_disable" :value="scope.row.status"/>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" class-name="small-padding fixed-width">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" prop="updateTime" class-name="small-padding fixed-width">
        <template #default="scope">
          <span>{{ parseTime(scope.row.updateTime) }}</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup name="project">
import {ElMessageBox} from "element-plus";
import {listProject, getProject, delProject, addProject, updateProject} from "@/api/hrm/project.js";
import {HrmDataTypeEnum} from "@/components/hrm/enum.js";
import RunDialog from "@/components/hrm/common/run_dialog.vue";
import {addSuiteDetail} from "@/api/qtr/suite.js";

const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");

const projectList = ref([]);
const open = ref(false);
const loading = ref(false);
const showSearch = ref(true);
const title = ref("");
const isExpandAll = ref(true);
const refreshTable = ref(true);

const runDialogShow = ref(false);
const ids = ref([]);
const configSuiteId = defineModel("suiteId");
const projectIds = ref([]);

const data = reactive({
  form: {},
  queryParams: {
    projectName: undefined,
    status: undefined
  },
  rules: {
    projectName: [{required: true, message: "项目名称不能为空", trigger: "blur"}],
    orderNum: [{required: true, message: "显示排序不能为空", trigger: "blur"}]
  },
});

const {queryParams, form, rules} = toRefs(data);

defineExpose({getList})

/** 查询项目列表 */
function getList() {
  loading.value = true;
  listProject(queryParams.value).then(response => {
    projectList.value = response.data;
    loading.value = false;
  });
}


/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.projectId);
  projectIds.value = ids.value;
  multiple.value = !selection.length;
}

/** 取消按钮 */
function cancel() {
  open.value = false;
  reset();
}

/** 表单重置 */
function reset() {
  form.value = {
    projectId: undefined,
    projectName: undefined,
    orderNum: 0,
    simpleDesc: undefined,
    status: "0"
  };
  proxy.resetForm("projectRef");
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

/** 新增按钮操作 */
function handleAdd(row) {
  reset();
  listProject().then(response => {
    projectOptions.value = proxy.handleTree(response.data, "projectId");
  });
  open.value = true;
  title.value = "添加项目";
}

/** 展开/折叠操作 */
function toggleExpandAll() {
  refreshTable.value = false;
  isExpandAll.value = !isExpandAll.value;
  nextTick(() => {
    refreshTable.value = true;
  });
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  getProject(row.projectId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改项目";
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["projectRef"].validate(valid => {
    if (valid) {
      if (form.value.projectId != undefined) {
        updateProject(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addProject(form.value).then(response => {
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


/** 保存套件配置 **/
function saveConfigSuite(row) {
  if (row && "projectId" in row && row.projectId){
    projectIds.value = [row.projectId];
  }
  if (!projectIds.value || projectIds.value.length === 0) {
    ElMessageBox.alert('请选择项目', "提示！", {type: "warning"});
      return;
  }
  const data = {
    "suiteId": configSuiteId.value,
    "dataIds": projectIds.value,
    "dataType": 1
  }
  addSuiteDetail(data).then(response => {
    proxy.$modal.msgSuccess("新增成功");
    openProjectCaseDialog.value = false;
  });
}

// getList();
</script>
