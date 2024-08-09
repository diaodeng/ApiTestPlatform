<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="ID" prop="runId" v-if="viewType === runDetailViewTypeEnum.report">
        <el-input
            v-model="queryParams.runId"
            placeholder="请输入用例ID"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="用例名称" prop="runName" v-if="viewType === runDetailViewTypeEnum.report">
        <el-input
            v-model="queryParams.runName"
            placeholder="请输入用例名称"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="用例状态" clearable style="width: 100px">
          <el-option
              v-for="dict in hrm_run_status"
              :key="dict.value"
              :label="dict.label"
              :value="dict.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button type="default" icon="Refresh" @click="resetQuery">重置</el-button>
        <el-button type="danger" icon="Refresh" @click="handleDelete" v-hasPermi="['hrm:history:delete']">删除</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="runDetailList"
              @selection-change="handleSelectionChange"
              border
    >
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column label="ID" align="center" prop="detailId"/>
      <el-table-column label="执行ID" align="center" prop="runId"/>
      <el-table-column label="名称" align="center" prop="runName"/>
      <!--      <el-table-column label="所属项目" align="center" prop="projectName"/>-->
      <!--      <el-table-column label="所属模块" align="center" prop="moduleName"/>-->
      <el-table-column label="状态" align="center" prop="status">
        <template #default="scope">
          <dict-tag :options="hrm_run_status" :value="scope.row.status"/>
        </template>
      </el-table-column>
      <el-table-column label="执行开始时间" align="center" prop="createTime" class-name="small-padding fixed-width">
        <template #default="scope">
          <span>{{ parseTime(scope.row.runStartTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="执行时长(S)" align="center" prop="createTime" class-name="small-padding fixed-width">
        <template #default="scope">
          <span>{{ scope.row.runDuration }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" align="center" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="handleView(scope.row)" v-hasPermi="['hrm:history:detail']"
                     title="查看">
          </el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)"
                     v-hasPermi="['hrm:history:delete']" title="删除">
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

    <CaseEditDialog v-model:open-case-edit-dialog="showCaseEdit" :form-datas="caseDetailData"></CaseEditDialog>
  </div>
</template>

<script setup name="RunDetail">
import * as ApiRunDetail from "@/api/hrm/run_detail.js";
import {listProject} from "@/api/hrm/project";
import CaseEditDialog from "@/components/hrm/case/case-edit-dialog.vue"
import {runDetailViewTypeEnum} from "@/components/hrm/enum.js";
import DictTag from "@/components/DictTag/index.vue";
import {initCaseFormData} from "@/components/hrm/data-template.js";
// import JsonEditorVue from "json-editor-vue3";


const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const {hrm_run_status} = proxy.useDict("hrm_run_status");
const {sys_request_method} = proxy.useDict("sys_request_method");
const {hrm_data_type} = proxy.useDict("hrm_data_type");
const props = defineProps(["runId", "viewType", "reportId"]);


provide("hrm_data_type", hrm_data_type);

const runDetailList = ref([]);
const projectOptions = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);

const showCaseEdit = ref(false);
const caseDetailData = ref(JSON.parse(JSON.stringify(initCaseFormData)));


const queryParams = ref({
    pageNum: 1,
    pageSize: 10,
    runId: props.runId,
    reportId: props.reportId,
    runName: undefined,
    projectId: undefined,
    moduleId: undefined,
    status: undefined
  });

watch(() => props.runId, () => {
  queryParams.value.runId = props.runId;
  handleQuery();
});

watch(() => props.reportId, () => {
  queryParams.value.reportId = props.reportId;
  handleQuery();
});

/** 查询用例列表 */
function getList() {
  loading.value = true;
  queryParams.value.runId = props.runId;
  queryParams.value.reportId = props.reportId;
  ApiRunDetail.list(queryParams.value).then(response => {
    runDetailList.value = response.rows;
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
  ids.value = selection.map(item => item.detailId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}


/** 删除按钮操作 */
function handleDelete(row) {
  let detailIds = [];
  if (row.detailId) {
    detailIds = [row.detailId];
  } else {
    detailIds = ids.value
  }
  proxy.$modal.confirm('是否确认删除ID为"' + detailIds + '"的数据项？').then(function () {
    return ApiRunDetail.del({detailIds: detailIds});
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {
  });
}

function handleView(row) {
  let detailIds = row.detailId;
  ApiRunDetail.detail(detailIds).then(response => {
    caseDetailData.value.caseId = response.data;
    caseDetailData.value.projectId = response.data;
    caseDetailData.value.moduleId = response.data;
    caseDetailData.value.request.teststeps = response.data;
    showCaseEdit.value = true;
    // alert(JSON.stringify(response, null, 4));
  });
}


getProjectSelect();
// getModuleShow();
handleQuery();
getList();
</script>
