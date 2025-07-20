<template>
  <div class="app-container">
    <MockTableQuery @select-change="handleSelectionChange" :data-type="dataType" ref="mockQueryViewRef">
      <template #table-tool>
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
      </template>
      <template #caseStatus="{scope}">
        <TagSelector v-model:selected-value="scope.row.status"
                     :options="qtr_case_status"
                     selector-width="90px"
                     :source-data="scope.row"
                     @selectChanged="lineStatusChange"
        ></TagSelector>
      </template>
      <template #tableOperate="{scope}">
        <el-button link type="primary" icon="Histogram" @click="showHistory(scope.row)"
                   v-hasPermi="['hrm:case:history']"
                   title="执行历史" v-if="dataType === HrmDataTypeEnum.case">
        </el-button>
        <el-button link type="warning" icon="Edit" :loading="loading.edite" @click="handleUpdate(scope.row)"
                   v-hasPermi="['hrm:case:edit']" title="编辑">
        </el-button>
        <el-button link type="warning" icon="CopyDocument" :loading="loading.copy" @click="showCopyDialog(scope.row)"
                   v-hasPermi="['hrm:case:copy']" title="复制">
        </el-button>
        <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)"
                   v-hasPermi="['hrm:case:remove']" title="删除">
        </el-button>
      </template>
    </MockTableQuery>

    <!-- 添加或修改用例对话框 -->
    <MockRuleDetailDialog :form-datas="form"
                    :data-type="dataType"
                    :form-rules="formRules"
                    v-model:open-dialog="open"
                    :title=caseEditDialogTitle

    ></MockRuleDetailDialog>

    <!-- 复制用例对话框 -->
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

  </div>
</template>

<script setup>
import {changeCaseStatus, copyCase, delCase, getCase, listCase} from "@/api/hrm/case";
import TagSelector from "@/components/hrm/common/tag-selector.vue";
import CaseEditDialog from "@/components/hrm/case/case-edit-dialog.vue"
import MockRuleDetailDialog from "@/components/hrm/mock/rule_detail.vue"
import {initCaseFormData} from "@/components/hrm/data-template.js";
import RunDetail from '@/components/hrm/common/run/run-detail.vue';
import RunDialog from '@/components/hrm/common/run/run_dialog.vue';
import {HrmDataTypeEnum, runDetailViewTypeEnum, RunTypeEnum} from "@/components/hrm/enum.js";
import {ElMessage, ElMessageBox} from "element-plus";
import MockTableQuery from "@/components/hrm/util-data-table/mock-table-query.vue";
// import JsonEditorVue from "json-editor-vue3";

const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
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

const mockQueryViewRef = ref(null);
const projectOptions = ref([]);
const open = ref(false);
// const loading = ref(true);
const showSearch = ref(true);
const selectIds = ref([]);
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

const caseEditDialogTitle = computed(() => {
  const caseId = form.value.caseId ? '【' + form.value.caseId + '】' : "";
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

/** 新增按钮操作 */
function handleAdd() {
  title.value = "添加" + dataName.value;
  form.value = JSON.parse(JSON.stringify(initCaseFormData));
  open.value = true;
}

/** 修改按钮操作 */
function handleUpdate(row) {
  loading.value.edite = true;
  const caseId = row.caseId || selectIds.value;
  getCase(caseId).then((response) => {
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

function showHistory(row) {
  const caseId = row.caseId || selectIds.value;
  currentCaseInfo.value = row;
  currentRunId.value = caseId;
  showHistoryDialog.value = true;
}

/** 删除按钮操作 */
function handleDelete(row) {
  const caseIds = row.caseId || selectIds.value;
  proxy.$modal.confirm('是否确认删除ID为"' + caseIds + '"的数据项？').then(function () {
    return delCase(caseIds);
  }).then(() => {
    if (mockQueryViewRef.value){
      mockQueryViewRef.value.handleQuery();
    }
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

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  selectIds.value = selection.map(item => item.caseId);
  single.value = selection.length !== 1;
  multiple.value = !selection.length;
}

</script>
