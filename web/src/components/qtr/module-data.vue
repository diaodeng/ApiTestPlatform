<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="项目" prop="projectId">
        <el-select v-model="queryParams.projectId" placeholder="请选择" clearable style="width: 150px">
          <el-option
              v-for="option in projectOptions"
              :key="option.projectId"
              :label="option.projectName"
              :value="option.projectId">
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item label="模块名称" prop="moduleName">
        <el-input
            v-model="queryParams.moduleName"
            placeholder="请输入模块名称"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="模块状态" clearable style="width: 200px">
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
        v-loading="loading"
        :data="moduleList"
        style="width: 100%"
        height="350"
        @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column label="模块ID" align="center" prop="moduleId"/>
      <el-table-column label="模块名称" align="center" prop="moduleName"/>
      <el-table-column label="所属项目" align="center" :formatter="formatProject"/>
      <el-table-column label="测试人员" align="center" prop="testUser"/>
      <el-table-column label="模块排序" align="center" prop="sort"/>
      <el-table-column label="状态" align="center" prop="status">
        <template #default="scope">
          <dict-tag :options="sys_normal_disable" :value="scope.row.status"/>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" class-name="small-padding fixed-width">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" prop="createTime" class-name="small-padding fixed-width">
        <template #default="scope">
          <span>{{ parseTime(scope.row.updateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" align="center" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['hrm:module:edit']">
            修改
          </el-button>
          <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)"
                     v-hasPermi="['hrm:module:remove']">删除
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
  </div>
</template>

<script setup name="Module">
import {listModule, addModule, delModule, getModule, updateModule} from "@/api/hrm/module";
import {listProject} from "@/api/hrm/project";
import {HrmDataTypeEnum} from "@/components/hrm/enum.js";
import RunDialog from "@/components/hrm/common/run_dialog.vue";
import {ElMessageBox} from "element-plus";
import {addSuiteDetail} from "@/api/qtr/suite.js";

const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");

const moduleList = ref([]);
const projectOptions = ref([]);
const open = ref(false);
const loading = ref(false);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");

const runDialogShow = ref(false);
const runIds = ref([]);
const configSuiteId = defineModel("suiteId");
const moduleIds = ref([]);

const data = reactive({
  form: {
    testUser: undefined
  },
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    suiteId: configSuiteId,
    dataType: 2,
    projectId: undefined,
    moduleName: undefined,
    status: undefined
  },
  rules: {
    moduleName: [{required: true, message: "模块名称不能为空", trigger: "blur"}],
    projectId: [{required: true, message: "所属项目不能为空", trigger: "blur"}],
    testUser: [{required: true, message: "测试负责人不能为空", trigger: "blur"}],
    sort: [{required: true, message: "模块顺序不能为空", trigger: "blur"}]
  }
});

const {queryParams, form, rules} = toRefs(data);

defineExpose({getList})

/** 查询模块列表 */
function getList() {
  loading.value = true;
  listModule(queryParams.value).then(response => {
    moduleList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}

/** 查询项目列表 */
function getProjectSelect() {
  listProject(null).then(response => {
    projectOptions.value = response.data;
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
  for (const project of projectOptions.value) {
    if (projectId === project.projectId) {
      return project.projectName;
    }
  }
}

/** 取消按钮 */
function cancel() {
  open.value = false;
  reset();
}

/** 表单重置 */
function reset() {
  form.value = {
    moduleId: undefined,
    projectId: undefined,
    moduleName: undefined,
    sort: 0,
    status: "0",
    remark: undefined
  };
  proxy.resetForm("postRef");
}

/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1;
  getProjectSelect();
  getList();
}

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.moduleId);
  moduleIds.value = ids.value;
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加模块";
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const moduleId = row.moduleId || ids.value;
  getModule(moduleId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改模块";
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["postRef"].validate(valid => {
    if (valid) {
      if (form.value.moduleId != undefined) {
        updateModule(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addModule(form.value).then(response => {
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
  const moduleIds = row.moduleId || ids.value;
  proxy.$modal.confirm('是否确认删除模块编号为"' + moduleIds + '"的数据项？').then(function () {
    return delModule(moduleIds);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {
  });
}

/** 导出按钮操作 */
function handleExport() {
  proxy.download("hrm/module/export", {
    ...queryParams.value
  }, `Module_${new Date().getTime()}.xlsx`);
}

/** 运行用例 */
function runTest(row) {
  if (row && "moduleId" in row && row.moduleId){
    runIds.value = [row.moduleId];
  }
  if (!runIds.value || runIds.value.length === 0) {
    ElMessageBox.alert('请选择要运行的模块', "提示！", {type: 'warning'});
      return;
  }

  runDialogShow.value = true;

}

/** 保存套件配置 **/
function saveConfigSuite(row) {
  if (row && "projectId" in row && row.moduleId){
    moduleIds.value = [row.moduleId];
  }
  if (!moduleIds.value || moduleIds.value.length === 0) {
    ElMessageBox.alert('请选择模块', "提示！", {type: "warning"});
      return;
  }
  const data = {
    "suiteId": configSuiteId.value,
    "dataIds": moduleIds.value,
    "dataType": 2
  }
  addSuiteDetail(data).then(response => {
    proxy.$modal.msgSuccess("新增成功");
    openProjectCaseDialog.value = false;
  });
}


getProjectSelect();
// getList();
</script>
