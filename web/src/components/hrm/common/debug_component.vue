<script setup name="debug_coomponent">

import EnvSelector from "@/components/hrm/common/env-selector.vue";
import {RunTypeEnum} from "@/components/hrm/enum";
import {debugCase} from "@/api/hrm/case";
import {ElMessage} from "element-plus";
import {all as getAllForwardRules} from "@/api/hrm/forward";
import {all as getAllAgent} from "@/api/hrm/agent";

const props = defineProps({
  caseData: {
    type: Object, default: null
  },
  runType: {type: Number, default: RunTypeEnum.case_debug}
});

const emits = defineEmits(["debugRun"])

const debugForm = ref({
  env: null,
  runType: props.runType,
  caseData: props.caseData,
  forwardConfig: {
    forward: true,
    agentId: undefined,
    forwardRuleIds: undefined,
  }
});

watch(props, (newData)=>{
  debugForm.value.runType = props.runType;
  debugForm.value.caseData = props.caseData;
}, {deep:true});

const allAgent = ref([]);
const allForwardRules = ref([]);

const loading = ref({
  debug: false
});

function getForwardRule() {
  getAllForwardRules().then(response => {
    allForwardRules.value = response.data;
  });
}

function getAgent() {
  getAllAgent().then(response => {
    allAgent.value = response.rows;
  });
}


function debug() {
  if (!debugForm.value.caseData){
    ElMessage.warning("没有可调试的数据");
    return;
  }
  loading.value.debug = true;
  const caseData = JSON.parse(JSON.stringify(toRaw(debugForm.value.caseData)));
  // let caseData = {
  //   request: dataSource.requestInfo,
  //   type: dataSource.type,
  //   name: dataSource.name,
  //   caseId: dataSource.apiId,
  // }
  delete caseData.request.config.result;
  delete caseData.request.teststeps[0].result;
  caseData.request.config.name = caseData.name;
  caseData.request.config.result = null;
  for (let i = 0; i < caseData.request.teststeps.length; i++) {
    caseData.request.teststeps[i].result = null;
  }

  debugForm.value.caseData = caseData;
  debugCase(debugForm.value).then(response => {
    ElMessage.success(response.msg);
    emits("debugRun", response);
  }).finally(() => {
    loading.value.debug = false;
  });
}

onMounted(() => {
  getForwardRule();
  getAgent();
});

</script>

<template>
  <div style="display: flex;flex-direction: row">
    <el-button
        @click="debug"
        :loading="loading.debug"
        :disabled="loading.debug"
        type="warning"
        style="margin-left: 5px;margin-right: 5px"
    >
      调试
    </el-button>
    <EnvSelector v-model:selected-env="debugForm.env" :disable="loading.debug"></EnvSelector>

    <el-select placeholder="请选择客户机"
               v-model="debugForm.forwardConfig.agentId"
               clearable
               style="width: 200px;margin-right: 5px;margin-left: 5px"
               :disabled="loading.debug"

    >
      <el-option
          v-for="item in allAgent"
          :key="item.agentId"
          :label="item.agentName"
          :value="item.agentId"
      />
    </el-select>

    <el-select multiple
               placeholder="请选择转发规则"
               v-model="debugForm.forwardConfig.forwardRuleIds"
               clearable
               style="width: 200px;"
               :disabled="loading.debug"

    >
      <el-option
          v-for="item in allForwardRules"
          :key="item.ruleId"
          :label="item.ruleName"
          :value="item.ruleId"
      />
    </el-select>
  </div>
</template>

<style scoped lang="scss">

</style>