<template>
  <el-dialog
      fullscreen
      :suiteId=suiteId
      v-model="openSuiteDetailDialog"
      append-to-body
      destroy-on-close
      @close="clearData"
      @open="getList"

  >
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
        、
        <el-form-item label="数据ID" prop="dataId">
          <el-input
              v-model="queryParams.dataId"
              placeholder="请输入数据ID"
              clearable
              style="width: 200px"
              @keyup.enter="handleQuery"
          />
        </el-form-item>
        <el-form-item label="数据名称" prop="dataName">
          <el-input
              v-model="queryParams.dataName"
              placeholder="请输入数据名称"
              clearable
              style="width: 200px"
              @keyup.enter="handleQuery"
          />
        </el-form-item>
        <el-form-item label="数据状态" prop="status">
          <el-select v-model="queryParams.status" placeholder="数据状态" clearable style="width: 200px">
            <el-option
                v-for="dict in qtr_case_status"
                :key="dict.value * 1"
                :label="dict.label"
                :value="dict.value * 1"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
          <el-button type="success" icon="Refresh" @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
      <el-row :gutter="10" class="mb8">
        <el-col :span="1.5">
          <el-button type="warning" icon="Plus" @click="handleSelectCase">选择数据</el-button>
        </el-col>
        <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
      </el-row>
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
      <el-table-column prop="suiteDetailId" label="ID" width="160" align="center"></el-table-column>
      <el-table-column prop="suiteId" label="套件ID" width="160" align="center"></el-table-column>
      <el-table-column prop="dataId" label="数据ID" width="160" align="center"></el-table-column>
      <el-table-column prop="dataType" label="数据类型" width="100" align="center">
        <template #default="scope">
          <dict-tag :options="qtr_data_type" :value="scope.row.dataType + ''"/>
        </template>
      </el-table-column>
      <el-table-column prop="dataName" label="数据名称"></el-table-column>
      <el-table-column prop="dataStatus" label="数据状态" width="100" align="center">
        <template #default="scope">
          <dict-tag :options="qtr_case_status" :value="scope.row.dataStatus + ''"/>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" width="160"
                       class-name="small-padding fixed-width">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" prop="updateTime" width="160"
                       class-name="small-padding fixed-width">
        <template #default="scope">
          <span>{{ parseTime(scope.row.updateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="170" align="center" class-name="small-padding fixed-width" fixed="right">
        <template #default="scope">
          <el-switch
              v-model="scope.row.status"
              :active-value="2"
              active-text="启用"
              :inactive-value="1"
              inactive-text="停用"
              @change="handleStatusChange(scope.row)"
              :loading="loadingSwitch"
          ></el-switch>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['qtr:suite:remove']"
                     title="删除"/>
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

    <!--  配置套件数据  -->
    <ConfigSuiteDataDialog
        :form-datas="form"
        :suiteId="configSuiteId"
        @closeDialog="getList"
        v-model:open-config-suite-data-dialog="openConfigSuiteDataDialog">
    </ConfigSuiteDataDialog>
  </el-dialog>

</template>

<script setup name="SuiteDetail">
import {getSuiteDetail, listDetailSuite, updateSuiteDetail} from "@/api/qtr/suite.js";
import {listProject} from "@/api/hrm/project.js";
import {selectModulList} from "@/api/hrm/module.js";
import ConfigSuiteDataDialog from "@/components/qtr/config-suite-data-dialog.vue";

const suiteId = defineModel("suiteId")
const {proxy} = getCurrentInstance();
const {qtr_case_status} = proxy.useDict("qtr_case_status");
const {qtr_data_type} = proxy.useDict("qtr_data_type");
const showSearch = ref(true);
const openConfigSuiteDataDialog = ref(false);
const loading = ref(false);
const loadingSwitch = ref(false);
const total = ref(0);
const configSuiteId = ref(0);
const suiteDetailList = ref([]);
const suiteDetailListData = ref([]);
const projectOptions = ref([]);
const moduleOptions = ref([]);
const refreshTable = ref(true);
const isExpandAll = ref(true);
const suiteDetailIds = ref([])

const data = reactive({
  form: {},
  queryParams: {
    dataName: undefined,
    projectId: undefined,
    suiteDetailId: undefined,
    suiteId: suiteId,
    dataId: undefined,
    moduleId: undefined,
    pageNum: 1,
    pageSize: 10,
    status: undefined
  }
});

const openSuiteDetailDialog = defineModel("openSuiteDetailDialog");
const {queryParams, form} = toRefs(data);

/** 展开/折叠操作 */
function toggleExpandAll() {
  refreshTable.value = false;
  isExpandAll.value = !isExpandAll.value;
  nextTick(() => {
    refreshTable.value = true;
  });
}

function handleSelectionChange(selection) {
  suiteDetailIds.value = selection.map(item => item.suiteDetailId);
}

/** 表单重置 */
function reset() {
  form.value = {
    suiteDetailId: 0,
    suiteName: undefined,
    suiteId: 0,
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
  configSuiteId.value = suiteId.value;
  // openProjectCaseDialog.value = true;
  openConfigSuiteDataDialog.value = true;
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
  listDetailSuite(queryParams.value).then(response => {
    suiteDetailList.value = response.rows;
    // suiteDetailListData.value = response.rows.map(group =>{
    //   let data_type = group.find(obj => obj.dataType !== undefined).dataType;
    //   let tmpCaseStatus = group.find(obj => obj.caseStatus !== undefined).caseStatus;
    //   let dataType = getKeyByValue(HrmDataTypeEnum, data_type);
    //   let projectObj = group.find(obj => obj.projectName !== undefined)
    //   let moduleObj = group.find(obj => obj.moduleName !== undefined)
    //   let caseObj = group.find(obj => obj.caseName !== undefined)
    //   let dataName = undefined;
    //   if (projectObj.projectName !== null){
    //     dataName = projectObj.projectName;
    //   } else if (moduleObj.moduleName !== null) {
    //     dataName = moduleObj.moduleName;
    //   } else if (caseObj.caseName !== null) {
    //     dataName = caseObj.caseName;
    //   }
    //   let newObject = {
    //     suiteDetailId: group.find(obj => obj.suiteDetailId !== undefined).suiteDetailId,
    //     suiteId: group.find(obj => obj.suiteId !== undefined).suiteId,
    //     dataId: group.find(obj => obj.dataId !== undefined).dataId,
    //     dataType: dataType,
    //     caseStatus: tmpCaseStatus,
    //     dataName: dataName,
    //     status: group.find(obj => obj.status !== undefined).status,
    //     createTime: group.find(obj => obj.createTime !== undefined).createTime,
    //     updateTime: group.find(obj => obj.updateTime !== undefined).updateTime,
    //     total: response.total
    //   }
    //   return newObject;
    // });
    total.value = response.total;
  }).finally(() => {
    loading.value = false;
  });
}

// 关闭dialog时清空列表数据
function clearData() {
  suiteDetailList.value = []
}

// 启用或停用套件中的数据
function handleStatusChange(row) {
  loadingSwitch.value = true;
  getSuiteDetail(row.suiteDetailId).then(response => {
    if (!response.data || Object.keys(response.data).length === 0) {
      alert("未查到对应数据！");
      return;
    }
    response.data.status = row.status
    updateSuiteDetail(response.data).then(response => {
      proxy.$modal.msgSuccess("修改成功");

    });
  }).finally(() => {
    loadingSwitch.value = false;
  });

}

getProjectSelect();
getList();

</script>

<style scoped lang="scss">

</style>
