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
      <template #rulePriority="{scope}">
        <el-input v-model="scope.row.priority" @blur="linePriorityChange(scope.row)" type="number" max="999" step="1" min="1" />
      </template>
      <template #ruleStatus="{scope}">
        <TagSelector v-model:selected-value="scope.row.status"
                     :options="qtr_data_status"
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

    <!-- 添加或修改mock规则对话框 -->
    <MockRuleDetailDialog :form-datas="form"
                          :data-type="dataType"
                          :form-rules="formRules"
                          v-model:open-dialog="open"
                          :rule-id="editingRuleId"
                          :title=ruleEditDialogTitle
                          :is-add="isAdd"

    ></MockRuleDetailDialog>

    <!-- 复制mock规则对话框 -->
    <el-dialog :title="copyMockRuleInfo?.name" v-model="copyDialog" append-to-body destroy-on-close>
      <el-container style="height: 100%">
        <!--          <el-header height="20px" border="2px" style="border-bottom-color: #97a8be;text-align: right">-->
        <!--          </el-header>-->
        <el-main style="max-height: calc(100vh - 95px);">
          <el-input placeholder="请输入名称" v-model="copyMockRuleInfo.name">
            <template #suffix>
              <el-button @click="copyMockRuleHandle">保存</el-button>
            </template>
          </el-input>
        </el-main>
      </el-container>
    </el-dialog>

  </div>
</template>

<script setup>
import {getMockRule, copyMockRule, delMockRule, updateMockRule, updateMockRuleInfo} from "@/api/hrm/mock.js";
import TagSelector from "@/components/hrm/common/tag-selector.vue";
import MockRuleDetailDialog from "@/components/hrm/mock/rule_detail.vue"
import { initMockRuleFormData } from "@/components/hrm/data-template.js";
import { HrmDataTypeEnum } from "@/components/hrm/enum.js";
import { ElMessage } from "element-plus";
import MockTableQuery from "@/components/hrm/util-data-table/mock-table-query.vue";
// import JsonEditorVue from "json-editor-vue3";

const {proxy} = getCurrentInstance();
const {hrm_data_type} = proxy.useDict("hrm_data_type");
const {qtr_data_status} = proxy.useDict("qtr_data_status");


const props = defineProps({
  dataType: {type: Number, default: 2},
  formRules: {
    type: Object,
    default: {
      name: [{required: true, message: "mock规则名称不能为空", trigger: "blur"}],
      projectId: [{required: true, message: "所属项目不能为空", trigger: "blur"}],
      moduleId: [{required: true, message: "所属模块不能为空", trigger: "blur"}]
    }
  }
});

const dataName = computed(() => {
  return "mock规则";
});

provide("hrm_data_type", hrm_data_type);


const mockQueryViewRef = ref(null);
const projectOptions = ref([]);
const open = ref(false);
const showSearch = ref(true);
const selectIds = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const onlySelf = ref(true);
const editingRuleId = ref(null);
const isAdd = ref(false);

const runIds = ref([]);

const showHistoryDialog = ref(false);
const currentCaseInfo = ref(null);
const currentRunId = ref();

const copyDialog = ref(false);
const copyMockRuleInfo = ref(initMockRuleFormData);

const queryParams = toRef({
  pageNum: 1,
  pageSize: 10,
  type: props.dataType,
  ruleId: undefined,
  name: undefined,
  projectId: undefined,
  moduleId: undefined,
  status: undefined,
  onlySelf: onlySelf
});

const form = ref(initMockRuleFormData);
const loading = ref({
  page: false,
  edite: false,
  run: false,
  copy: false
});

const ruleEditDialogTitle = computed(() => {
  const ruleId = form.value.ruleId ? '【' + form.value.ruleId + '】' : "";
  return title.value + '>> ' + ruleId + form.value.name;
});

function lineStatusChange(selectValue, dataSource) {
  updateMockRuleInfo({ruleId: dataSource.ruleId, status: selectValue}).then((response) => {
    ElMessage.success("修改成功");
  }).catch(() => {
    ElMessage.error("修改失败");
  });
}

function linePriorityChange(row) {
  updateMockRuleInfo({ruleId: row.ruleId, priority: row.priority}).then((response) => {
    ElMessage.success("修改成功");
  }).catch(() => {
    ElMessage.error("修改失败");
  });
}


/*
* 换起mock规则复制弹窗
* */
function showCopyDialog(data) {
  copyDialog.value = true;
  copyMockRuleInfo.value = structuredClone(toValue(toRaw(data)));
}

/*
* 复制mock规则
* */
function copyMockRuleHandle() {
  copyDialog.value = true;
  let data = {
    ruleId: copyMockRuleInfo.value.ruleId,
    name: copyMockRuleInfo.value.name,
  }
  copyMockRule(data).then(response => {
    ElMessage.success("复制成功");
  }).finally(() => {
    copyDialog.value = false;
  });
}


/** 新增按钮操作 */
function handleAdd() {
  title.value = "添加" + dataName.value;
  editingRuleId.value = null;
  isAdd.value = true;
  form.value = JSON.parse(JSON.stringify(initMockRuleFormData));
  open.value = true;
}

/** 修改按钮操作 */
function handleUpdate(row) {
  loading.value.edite = true;
  isAdd.value = false;
  const ruleId = row.ruleId || selectIds.value;
  editingRuleId.value = ruleId;
  open.value = true;
  loading.value.edite = false;
  return;
  getMockRule(ruleId).then((response) => {
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
  const ruleId = row.ruleId || selectIds.value;
  currentCaseInfo.value = row;
  currentRunId.value = ruleId;
  showHistoryDialog.value = true;
}

/** 删除按钮操作 */
function handleDelete(row) {
  let ruleIds = [];
  if (row.ruleId){
    ruleIds = [row.ruleId];
  }else {
    ruleIds = selectIds.value;
  }

  proxy.$modal.confirm('是否确认删除ID为"' + ruleIds + '"的数据项？').then(function () {
    return delMockRule({ruleIds: ruleIds});
  }).then(() => {
    if (mockQueryViewRef.value) {
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
  selectIds.value = selection.map(item => item.ruleId);
  single.value = selection.length !== 1;
  multiple.value = !selection.length;
}

</script>
