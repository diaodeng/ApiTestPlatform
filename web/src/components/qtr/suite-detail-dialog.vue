<template>
  <el-dialog fullscreen :title='title' v-model="openSuiteDetailDialog" append-to-body destroy-on-close>
    <div class="app-container">
      <el-form :model="queryParams" ref="queryRef_detail" :inline="true" v-show="showSearch">
        <el-form-item label="项目名称" prop="projectName">
          <el-input
              v-model="queryParams.projectName"
              placeholder="请输入套件名称"
              clearable
              style="width: 200px"
              @keyup.enter="handleQuery"
          />
        </el-form-item>
        <el-form-item label="用例ID" prop="caseId">
          <el-input
              v-model="queryParams.caseId"
              placeholder="请输入用例ID"
              clearable
              style="width: 200px"
              @keyup.enter="handleQuery"
          />
        </el-form-item>
        <el-form-item label="用例名称" prop="caseName">
          <el-input
              v-model="queryParams.caseName"
              placeholder="请输入用例名称"
              clearable
              style="width: 200px"
              @keyup.enter="handleQuery"
          />
        </el-form-item>
        <el-form-item label="用例状态" prop="status">
          <el-select v-model="queryParams.status" placeholder="用例状态" clearable style="width: 200px">
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
          <el-button type="success" icon="Refresh" @click="resetQuery">重置</el-button>
          <el-button type="warning" icon="Plus" @click="handleSelectCase">选择用例</el-button>
        </el-form-item>
      </el-form>

    </div>
    <ProjectCaseDialog
        :form-datas="form"
        v-model:open-project-case-dialog="openProjectCaseDialog">
    </ProjectCaseDialog>
  </el-dialog>

</template>

<script setup>
import ProjectCaseDialog from "@/components/qtr/project-case-dialog.vue";
import {listSuite} from "@/api/qtr/suite.js";
import {listProject} from "@/api/hrm/project.js";

const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const showSearch = ref(true);
const openProjectCaseDialog = ref(false);
const suiteDetailList = ref([]);
const projectOptions = ref([]);

const data = reactive({
  form: {},
  queryParams: {
    suiteName: undefined,
    projectId: undefined,
    projectName: undefined,
    caseId: undefined,
    caseName: undefined,
    status: undefined
  },
  rules: {
    suiteName: [{required: true, message: "套件名称不能为空", trigger: "blur"}],
    orderNum: [{required: true, message: "显示排序不能为空", trigger: "blur"}]
  },
});

const openSuiteDetailDialog = defineModel("openSuiteDetailDialog");
const {queryParams, form, rules} = toRefs(data);

/** 表单重置 */
function reset() {
  form.value = {
    suiteId: undefined,
    suiteName: undefined,
    orderNum: 0,
    simpleDesc: undefined,
    status: "0"
  };
  proxy.resetForm("suiteRef");
}

/** 搜索按钮操作 */
function handleQuery() {
  getList();
}

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef_detail");
  handleQuery();
}

/** 选择用例按钮操作 */
function handleSelectCase() {
  openProjectCaseDialog.value = true;
}

/** 新增按钮操作 */
function handleAdd(row) {
  reset();
  open.value = true;
  title.value = "添加套件";
}

/** 查询项目列表 */
function getProjectSelect() {
  listProject(null).then(response => {
    projectOptions.value = response.data;
  });
}

/** 查询套件详情列表 */
function getList() {
  loading.value = true;
  listSuite(queryParams.value).then(response => {
    suiteDetailList.value = response.rows;
    total.value = response.total;
  }).finally(()=>{
    loading.value = false;
  });
}

// getProjectSelect();
// getList();

</script>

<style scoped lang="scss">

</style>
