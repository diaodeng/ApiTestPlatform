<template>
  <el-dialog
      v-model="openProjectCaseDialog"
      width="950"
      title="用例选择"
      :suiteId=configSuiteId
      append-to-body
      destroy-on-close
      draggable
      overflow
      :close-on-click-modal="false"
  >
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
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
      <el-form-item :label="dataName+'ID'" prop="caseId">
        <el-input
            v-model="queryParams.caseId"
            :placeholder="'请输入'+dataName+'ID'"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item :label="dataName+'名称'" prop="caseName">
        <el-input
            v-model="queryParams.caseName"
            :placeholder="'请输入'+dataName+'名称'"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" :placeholder="dataName+'状态'" clearable style="width: 100px">
          <el-option
              v-for="dict in sys_normal_disable"
              :key="dict.value"
              :label="dict.label"
              :value="dict.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item><el-checkbox v-model="onlySelf" @change="handleQuery">仅自己的数据</el-checkbox></el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button type="default" icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>
    <el-table v-loading="loading" :data="caseList"
              @selection-change="handleSelectionChange"
              border
              table-layout="fixed"
              max-height="calc(100vh - 280px)"
    >
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column :label="dataName+'ID'" prop="caseId" width="150px"/>
      <el-table-column :label="dataName+'名称'" prop="caseName" width="auto"/>
      <el-table-column label="所属项目" prop="projectName">
        <template #default="scope">
          <span>{{ nameOrGlob(scope.row.projectName) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="所属模块" prop="moduleName">
        <template #default="scope">
          <span>{{ nameOrGlob(scope.row.moduleName) }}</span>
        </template>
      </el-table-column>
      <!--         <el-table-column label="用例排序" align="center" prop="sort" />-->
      <el-table-column label="状态" align="center" prop="status" width="70px">
        <template #default="scope">
          <dict-tag :options="sys_normal_disable" :value="scope.row.status"/>
        </template>
      </el-table-column>
      <el-table-column label="创建人" align="center" prop="createBy"></el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" class-name="small-padding fixed-width" width="150px">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" prop="createTime" class-name="small-padding fixed-width" width="150px">
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
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="openProjectCaseDialog = false">取消</el-button>
        <el-button type="primary" @click="saveConfigSuite">
          保存
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import {initCaseFormData} from "@/components/hrm/data-template.js";
import {ElMessage, ElMessageBox} from "element-plus";
import {copyCase, delCase, getCase, listCase} from "@/api/hrm/case.js";
import {listProject} from "@/api/hrm/project.js";
import {selectModulList} from "@/api/hrm/module.js";
import {HrmDataTypeEnum} from "@/components/hrm/enum.js";

const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const {sys_request_method} = proxy.useDict("sys_request_method");
const {hrm_data_type} = proxy.useDict("hrm_data_type");
const configSuiteId = defineModel("suiteId");

const props = defineProps({
  dataType: {type: Number, default: HrmDataTypeEnum.case},
  formRules: {
    type: Object,
    default: {
      caseName: [{required: true, message: "用例名称不能为空", trigger: "blur"}],
      projectId: [{required: true, message: "所属项目不能为空", trigger: "blur"}],
      moduleId: [{required: true, message: "所属模块不能为空", trigger: "blur"}]
    }
  }
});

const dataName = computed(() => {
  return props.dataType === HrmDataTypeEnum.case ? "用例" : "配置";
});



provide("hrm_data_type", hrm_data_type);
provide('sys_normal_disable', sys_normal_disable);
const openProjectCaseDialog = defineModel("openProjectCaseDialog");
const caseList = ref([]);
const projectOptions = ref([]);
const moduleOptions = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const onlySelf = ref(true);

const caseIds = ref([]);

const history = ref(false);

const queryParams = toRef({
  pageNum: 1,
  pageSize: 10,
  type: props.dataType,
  caseId: undefined,
  caseName: undefined,
  projectId: undefined,
  moduleId: undefined,
  status: undefined,
  onlySelf: onlySelf
});

const form = ref(initCaseFormData);

function nameOrGlob(val) {
  return val ? val : "全局";

}

/** 查询用例列表 */
function getList() {
  loading.value = true;
  listCase(queryParams.value).then(response => {
    caseList.value = response.rows;
    total.value = response.total;
  }).finally(()=>{
    loading.value = false;
  });
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
  ids.value = selection.map(item => item.caseId);
  caseIds.value = ids.value;
  single.value = selection.length !== 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {
  open.value = true;
  title.value = "添加" + dataName.value;
  form.value = JSON.parse(JSON.stringify(initCaseFormData));
}

/** 修改按钮操作 */
function handleUpdate(row) {
  const caseId = row.caseId || ids.value;
  getCase(caseId).then(response => {
    if (!response.data || Object.keys(response.data).length === 0) {
      alert("未查到对应数据！");
      return;
    }
    form.value = response.data;
    open.value = true;
    title.value = "修改" + dataName.value;
  });
}

/** 保存套件配置 **/
function saveConfigSuite(row) {
  if (row && "caseId" in row && row.caseId){
    caseIds.value = [row.caseId];
  }
  if (!caseIds.value || caseIds.value.length === 0) {
    ElMessageBox.alert('请选择用例', "提示！", {type: "warning"});
      return;
  }
  alert(configSuiteId.value);
  alert(caseIds.value);
}

/** 删除按钮操作 */
function handleDelete(row) {
  const caseIds = row.caseId || ids.value;
  proxy.$modal.confirm('是否确认删除ID为"' + caseIds + '"的数据项？').then(function () {
    return delCase(caseIds);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {
  });
}

/** 导出按钮操作 */
function handleExport() {
  proxy.download("hrm/case/export", {
    ...queryParams.value
  }, `Case_${new Date().getTime()}.xlsx`);
}

getProjectSelect();
getList();
</script>

<style scoped lang="scss">

</style>
