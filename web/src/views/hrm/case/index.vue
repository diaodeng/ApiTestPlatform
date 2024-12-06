<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="所属项目" prop="projectId">
        <el-select v-model="queryParams.projectId" placeholder="请选择" @change="resetModule" clearable filterable
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
        <el-select v-model="queryParams.moduleId" placeholder="请选择" clearable filterable style="width: 150px">
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
            :placeholder="'请输入'+dataName+'名称'"
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
              v-for="dict in qtr_case_status"
              :key="dict.value"
              :label="dict.label"
              :value="dict.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="onlySelf" @change="handleQuery">仅自己的数据</el-checkbox>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery" :loading="loading.page" :disabled="loading.page">
          搜索
        </el-button>
        <el-button type="default" icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button
            type="primary"
            plain
            icon="Plus"
            @click="handleAdd"
            v-hasPermi="['hrm:case:add']"
        >新增
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
            type="success"
            plain
            icon="Edit"
            :disabled="single"
            @click="handleUpdate"
            v-hasPermi="['hrm:case:edit']"
        >修改
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
            type="danger"
            plain
            icon="Delete"
            :disabled="multiple"
            @click="handleDelete"
            v-hasPermi="['hrm:case:remove']"
        >删除
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
            type="warning"
            plain
            icon="Download"
            @click="handleExport"
            v-hasPermi="['hrm:case:export']"
        >导出
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="warning"
                   icon="CaretRight"
                   @click="runTest"
                   v-hasPermi="['hrm:case:run']"
                   title="运行"
                   v-if="dataType === HrmDataTypeEnum.case"
                   :disabled="multiple"
        >
          执行
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading.page" :data="caseList"
              @selection-change="handleSelectionChange"
              border
              table-layout="fixed"
              max-height="calc(100vh - 280px)"
    >
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column :label="dataName+'ID'" prop="caseId" width="150px"/>
      <el-table-column :label="dataName+'名称'" prop="caseName" width="auto" min-width="200px"/>
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
      <el-table-column label="状态" align="center" prop="status" width="120px">
        <template #default="scope">
          <TagSelector v-model:selected-value="scope.row.status"
                       :options="qtr_case_status"
                       selector-width="90px"
                       :source-data="scope.row"
                       @selectChanged="lineStatusChange"
          ></TagSelector>
          <!--          <el-select v-model="scope.row.status" @change="changeStatus(scope.row)">-->
          <!--            <el-option v-for="item in qtr_case_status"-->
          <!--                       :key="item.value * 1"-->
          <!--                       :value="item.value * 1"-->
          <!--                       :label="item.label"></el-option>-->
          <!--          </el-select>-->
          <!--                    <dict-tag :options="qtr_case_status" :value="scope.row.status"/>-->
        </template>
      </el-table-column>
      <el-table-column label="创建人" align="center" prop="createBy" width="80px"></el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" class-name="small-padding fixed-width"
                       width="150px">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" prop="createTime" class-name="small-padding fixed-width"
                       width="150px">
        <template #default="scope">
          <span>{{ parseTime(scope.row.updateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="170" align="center" class-name="small-padding fixed-width" fixed="right">
        <template #default="scope">
          <el-button link type="primary" icon="Histogram" @click="showHistory(scope.row)"
                     v-hasPermi="['hrm:case:history']"
                     title="执行历史" v-if="dataType === HrmDataTypeEnum.case">

          </el-button>
          <!--          <el-button link type="primary" icon="View" @click="handleUpdate(scope.row)" v-hasPermi="['hrm:case:detail']"-->
          <!--                     title="查看">-->

          <!--          </el-button>-->
          <el-button link type="warning" icon="Edit" :loading="loading.edite" @click="handleUpdate(scope.row)"
                     v-hasPermi="['hrm:case:edit']" title="编辑">
          </el-button>
          <el-button link type="warning" icon="CaretRight" :loading="loading.run" @click="runTest(scope.row)"
                     v-hasPermi="['hrm:case:run']" title="运行" v-if="dataType === HrmDataTypeEnum.case">
          </el-button>
          <el-button link type="warning" icon="CopyDocument" :loading="loading.copy" @click="showCopyDialog(scope.row)"
                     v-hasPermi="['hrm:case:copy']" title="复制">
          </el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)"
                     v-hasPermi="['hrm:case:remove']" title="删除">
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

    <!-- 添加或修改用例对话框 -->
    <CaseEditDialog :form-datas="form"
                    :data-type="dataType"
                    :form-rules="formRules"
                    v-model:open-case-edit-dialog="open"
                    :title=caseEditDialogTitle

    ></CaseEditDialog>


    <el-dialog fullscreen :title="'【' + currentCaseInfo?.caseId + '】' + currentCaseInfo?.caseName"
               v-model="showHistoryDialog" append-to-body
               v-if="dataType===HrmDataTypeEnum.case" destroy-on-close>
      <el-container style="height: 100%">
        <!--          <el-header height="20px" border="2px" style="border-bottom-color: #97a8be;text-align: right">-->
        <!--          </el-header>-->
        <el-main style="max-height: calc(100vh - 95px);">
          <RunDetail :run-id="currentRunId" :view-type="runDetailViewTypeEnum.case"></RunDetail>
        </el-main>
      </el-container>
    </el-dialog>


    <el-dialog :title="copyCaseInfo?.caseName" v-model="copyDialog" append-to-body destroy-on-close>
      <el-container style="height: 100%">
        <!--          <el-header height="20px" border="2px" style="border-bottom-color: #97a8be;text-align: right">-->
        <!--          </el-header>-->
        <el-main style="max-height: calc(100vh - 95px);">
          <el-input placeholder="请输入用例名称" v-model="copyCaseInfo.caseName">
            <template #suffix>
              <el-button @click="copyCaseHandle">保存</el-button>
            </template>
          </el-input>
        </el-main>
      </el-container>
    </el-dialog>

    <!-- 运行用例对话框 -->
    <RunDialog v-model:dialog-visible="runDialogShow" :run-type="RunTypeEnum.case" :run-ids="runIds"></RunDialog>
  </div>
</template>

<script setup name="Case">
import {changeCaseStatus, copyCase, delCase, getCase, listCase} from "@/api/hrm/case";
import {selectModulList} from "@/api/hrm/module";
import {listProject} from "@/api/hrm/project";
import TagSelector from "@/components/hrm/common/tag-selector.vue";
import CaseEditDialog from "@/components/hrm/case/case-edit-dialog.vue"
import {initCaseFormData} from "@/components/hrm/data-template.js";
import RunDetail from '@/components/hrm/common/run-detail.vue';
import RunDialog from '@/components/hrm/common/run_dialog.vue';
import {HrmDataTypeEnum, runDetailViewTypeEnum, RunTypeEnum} from "@/components/hrm/enum.js";
import {ElMessage, ElMessageBox} from "element-plus";
// import JsonEditorVue from "json-editor-vue3";

const showTestDIalog = ref(false);
const testDialogContent = ref("久啊联发科打了飞机啊漏打卡飞机啦电极法立卡登记说法法兰对接法拉克束带结发法拉第会计法垃圾");

const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const {sys_request_method} = proxy.useDict("sys_request_method");
const {hrm_data_type} = proxy.useDict("hrm_data_type");
const {qtr_case_status} = proxy.useDict("qtr_case_status");


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
provide('qtr_case_status', qtr_case_status);


const caseList = ref([]);
const projectOptions = ref([]);
const moduleOptions = ref([]);
const open = ref(false);
// const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const onlySelf = ref(true);

const runDialogShow = ref(false);
const runIds = ref([]);

const showHistoryDialog = ref(false);
const currentCaseInfo = ref(null);
const currentRunId = ref();

const copyDialog = ref(false);
const copyCaseInfo = ref(initCaseFormData);

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
const loading = ref({
  page: false,
  edite: false,
  run: false,
  copy: false
});

function nameOrGlob(val) {
  return val ? val : "全局";
}

const caseEditDialogTitle = computed(() => {
  const caseId = form.value.caseId ? '【' + form.value.caseId + '】' : ""
  return title.value + '>> ' + caseId + form.value.caseName;
});


function lineStatusChange(selectValue, dataSource) {
  changeCaseStatus({caseId: dataSource.caseId, status: selectValue}).then((response) => {
    ElMessage.success("修改成功");
  }).catch(() => {
    ElMessage.error("修改失败");
  });
}


/*
* 行执行用例
* **/
function runTest(row) {
  if (row && "caseId" in row && row.caseId) {
    runIds.value = [row.caseId];
  }
  if (!runIds.value || runIds.value.length === 0) {
    ElMessageBox.alert('请选择要运行的用例', "提示！", {type: "warning"});
    return;
  }
  runDialogShow.value = true;

}


/*
* 换起用例复制弹窗
* */
function showCopyDialog(data) {
  copyDialog.value = true;
  copyCaseInfo.value = structuredClone(toValue(toRaw(data)));
}


/*
* 复制用例
* */
function copyCaseHandle() {
  copyDialog.value = true;
  let data = {
    caseId: copyCaseInfo.value.caseId,
    caseName: copyCaseInfo.value.caseName,
  }
  copyCase(data).then(response => {
    ElMessage.success("复制成功");
  }).finally(() => {
    copyDialog.value = false;
  });
}


/** 查询用例列表 */
function getList() {
  loading.value.page = true;
  listCase(queryParams.value).then(response => {
    caseList.value = response.rows;
    total.value = response.total;
  }).finally(() => {
    loading.value.page = false;
  });
}

/** 查询项目列表 */
function getProjectSelect() {
  listProject({isPage: false}).then(response => {
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
  runIds.value = ids.value;
  single.value = selection.length !== 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {

  title.value = "添加" + dataName.value;
  form.value = JSON.parse(JSON.stringify(initCaseFormData));
  open.value = true;
}

/** 修改按钮操作 */
function handleUpdate(row) {
  loading.value.edite = true;
  const caseId = row.caseId || ids.value;
  getCase(caseId).then(response => {
    if (!response.data || Object.keys(response.data).length === 0) {
      ElMessage.warning("未查到对应数据！");
      return;
    }
    form.value = response.data;

    title.value = "修改" + dataName.value;
    open.value = true;
  }).finally(() => {
    loading.value.edite = false;
  });
}

/*
* 更新用例状态
* */
function changeStatus(row) {

  changeCaseStatus({caseId: row.caseId, status: row.status}).then((response) => {
    ElMessage.success("修改成功");
  }).catch(() => {
    ElMessage.error("修改失败");
  });
}

function showHistory(row) {
  const caseId = row.caseId || ids.value;
  currentCaseInfo.value = row;
  currentRunId.value = caseId;
  showHistoryDialog.value = true;
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

onMounted(() => {
  getProjectSelect();
  getList();
})

</script>
