<script setup>
/*
* 获取测试执行的数据id和类型
* */
import {RunTypeEnum} from "@/components/hrm/enum.js";
import CaseTableQuery from "@/components/hrm/util-data-table/case-table-query.vue";
import ModuleTableQuery from "@/components/hrm/util-data-table/module-table-query.vue";
import ProjectTableQuery from "@/components/hrm/util-data-table/project-table-query.vue";
import SuiteTableQuery from "@/components/qtr/util-data-table/suite-table-query.vue";

const runType = defineModel("runType", {default: RunTypeEnum.case});
const runIds = defineModel("runIds", {default: []});
// const runType = ref(RunTypeEnum.case);
const dialogVisible = ref(false);
const caseDataDialog = ref(false);

const dataTableRef = ref(null);
const tipsContent = computed(()=>{
  return runIds.value ? runIds.value.join(","): "";
});

const dialogTitle = computed(()=>{
  if(runType.value === RunTypeEnum.case){
    return "配置用例数据";
  }else if (runType.value === RunTypeEnum.module){
    return "配置模块数据";
  }else if(runType.value === RunTypeEnum.project){
    return "配置项目数据";
  }else if(runType.value === RunTypeEnum.suite){
    return "配置套件数据";
  }
  return ""
});

function changeType() {
  runIds.value = [];
  // if (runIds.value && runIds.value.length > 0){
  //   dialogVisible.value = true;
  // }
}

function selectChangeHandle(selected) {
  runIds.value = selected.map(item => item.suiteId);
}

function dataChange() {
  runIds.value = dataTableRef.value.getSelectedIds();
  caseDataDialog.value = false;
}

</script>

<template>
  <el-dialog
      v-model="dialogVisible"
      title="数据类型变更提醒"
      width="500"
  >
    <span>只能选择一种数据类型，修改数据类型将删除原有数据，确定修改？</span>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="dialogVisible = false">
          确定
        </el-button>
      </div>
    </template>
  </el-dialog>
  <el-radio-group v-model="runType" @change="changeType">
    <el-radio :value="RunTypeEnum.case">用例</el-radio>
    <el-radio :value="RunTypeEnum.module">模块</el-radio>
    <el-radio :value="RunTypeEnum.project">项目</el-radio>
    <el-radio :value="RunTypeEnum.suite">套件</el-radio>
  </el-radio-group>
  <el-tooltip
      class="box-item"
      effect="dark"
      :content="tipsContent"
      placement="top-start"
  >
    <el-button style="margin-left: 10px" round type="success" @click="()=>{caseDataDialog=true}">配置数据</el-button>
  </el-tooltip>

  <el-dialog v-model="caseDataDialog"
             :title="dialogTitle"
             width="90%"
             destroy-on-close>
    <el-container style="display: flex;overflow-x: auto">
      <template v-if="runType === RunTypeEnum.case">
        <CaseTableQuery ref="dataTableRef" :checked-ids="runIds"></CaseTableQuery>
      </template>
      <template v-else-if="runType === RunTypeEnum.module">
        <ModuleTableQuery ref="dataTableRef" :checked-ids="runIds"></ModuleTableQuery>
      </template>
      <template v-else-if="runType === RunTypeEnum.project">
        <ProjectTableQuery ref="dataTableRef" :checked-ids="runIds"></ProjectTableQuery>
      </template>
      <template v-else-if="runType === RunTypeEnum.suite">
        <SuiteTableQuery ref="dataTableRef" :checked-ids="runIds"></SuiteTableQuery>
      </template>
    </el-container>
    <template #footer>
      <div class="dialog-footer">
        <el-button type="primary" @click="dataChange">确定</el-button>
      </div>
    </template>
    <el-footer>

    </el-footer>
  </el-dialog>

</template>

<style scoped lang="scss">

</style>