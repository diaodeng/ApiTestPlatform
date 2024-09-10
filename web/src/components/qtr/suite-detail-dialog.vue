<template>
  <el-dialog fullscreen :title='title' v-model="openSuiteDetailDialog" append-to-body destroy-on-close>
    <div class="app-container">
      <el-form :model="queryParams" ref="queryRef_detail" :inline="true" v-show="showSearch">
        <el-form-item label="所属项目" prop="projectId">
          <el-select v-model="queryParams.projectId" placeholder="请选择" @change="resetModule" clearable
                     style="width: 150px">
            <el-option
                v-for="option in projectOptions"
                :key="option.projectId"
                :label="option.projectName"
                :value="option.projectId">
            </el-option>
          </el-select>
      </el-form-item>
      <el-form-item label="所属模块" prop="moduleId">
        <el-select v-model="queryParams.moduleId" placeholder="请选择" clearable style="width: 150px">
          <el-option
              v-for="option in moduleOptions"
              :key="option.moduleId"
              :label="option.moduleName"
              :value="option.moduleId">
          </el-option>
        </el-select>
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
    <el-table
        border
        v-if="refreshTable"
        v-loading="loading"
        :data="suiteDetailList"
        row-key="suiteDetailId"
        :default-expand-all="isExpandAll"
        @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column prop="suiteDetailId" label="ID" width="160"></el-table-column>
      <el-table-column prop="suiteId" label="套件ID" width="160"></el-table-column>
      <el-table-column prop="projectId" label="项目ID" width="160"></el-table-column>
      <el-table-column prop="projectName" label="项目名称" width="160"></el-table-column>
      <el-table-column prop="caseId" label="用例ID" width="160"></el-table-column>
      <el-table-column prop="caseName" label="用例名称" width="200"></el-table-column>
      <el-table-column prop="orderNum" label="排序" width="200"></el-table-column>
      <el-table-column prop="status" label="状态" width="100">
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
<!--      <el-table-column label="操作" align="center" class-name="small-padding fixed-width">-->
<!--        <template #default="scope">-->
<!--          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['qtr:suite:edit']">-->
<!--            修改-->
<!--          </el-button>-->
<!--          <el-button link type="primary" icon="Tools" @click="handleConfigSuite(scope.row)" v-hasPermi="['qtr:suite:edit']">-->
<!--            配置-->
<!--          </el-button>-->
<!--          <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['qtr:suite:remove']">-->
<!--            删除-->
<!--          </el-button>-->
<!--        </template>-->
<!--      </el-table-column>-->
    </el-table>
    <pagination
        v-show="total > 0"
        :total="total"
        v-model:page="queryParams.pageNum"
        v-model:limit="queryParams.pageSize"
        @pagination="getList"
    />
    <ProjectCaseDialog
        :form-datas="form"
        v-model:open-project-case-dialog="openProjectCaseDialog">
    </ProjectCaseDialog>
  </el-dialog>

</template>

<script setup name="SuiteDetail">
import ProjectCaseDialog from "@/components/qtr/project-case-dialog.vue";
import {listDetailSuite} from "@/api/qtr/suite.js";
import {listProject} from "@/api/hrm/project.js";
import {selectModulList} from "@/api/hrm/module.js";

const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const showSearch = ref(true);
const openProjectCaseDialog = ref(false);
const loading = ref(true);
const total = ref(0);
const suiteDetailList = ref([]);
const projectOptions = ref([]);
const moduleOptions = ref([]);
const refreshTable = ref(true);
const isExpandAll = ref(true);

const data = reactive({
  form: {},
  queryParams: {
    suiteName: undefined,
    projectId: undefined,
    projectName: undefined,
    suiteDetailId: undefined,
    suiteId: undefined,
    caseId: undefined,
    caseName: undefined,
    moduleId: undefined,
    pageNum: 1,
    pageSize: 10,
    status: undefined
  },
  rules: {
    suiteName: [{required: true, message: "套件名称不能为空", trigger: "blur"}],
    orderNum: [{required: true, message: "显示排序不能为空", trigger: "blur"}]
  },
});

const openSuiteDetailDialog = defineModel("openSuiteDetailDialog");
const {queryParams, form, rules} = toRefs(data);

/** 展开/折叠操作 */
function toggleExpandAll() {
  refreshTable.value = false;
  isExpandAll.value = !isExpandAll.value;
  nextTick(() => {
    refreshTable.value = true;
  });
}

function handleSelectionChange(selection) {
  runIds.value = selection.map(item => item.suiteDetailId);
}

/** 表单重置 */
function reset() {
  form.value = {
    suiteDetailId: undefined,
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

/** 查询模块列表 */
function getModuleSelect() {
  selectModulList(queryParams.value).then(response => {
    moduleOptions.value = response.data;
  });
}

/**重置查询条件所属模块下拉框*/
function resetModule() {
  queryParams.value.moduleId = undefined;
  getModuleSelect();
}

/** 查询套件详情列表 */
function getList() {
  loading.value = true;
  console.log(queryParams.value);
  listDetailSuite(queryParams.value).then(response => {
    suiteDetailList.value = response.rows;
    total.value = response.total;
  }).finally(()=>{
    loading.value = false;
  });
}

getProjectSelect();
getList();

</script>

<style scoped lang="scss">

</style>
