<script setup>

import TableExtract from "@/components/hrm/table-extract.vue";
import EditLabel from "@/components/hrm/common/edite-label.vue";
import TableHooks from "@/components/hrm/table-hooks.vue";
import TableValidate from "@/components/hrm/table-validate.vue";
import TableVariables from "@/components/hrm/table-variables.vue";
import StepRequest from "@/components/hrm/case/step-request.vue";
import StepWebsocket from "@/components/hrm/case/step-websocket.vue";
import {randomString} from "@/utils/tools.js";
import {initStepData, initWebsocketData} from "@/components/hrm/data-template.js";

// const {proxy} = getCurrentInstance();
const activeRequestName = ref("stepRequest")
const activeTestStepName = ref(0)

// const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
// const {hrm_data_type} = proxy.useDict("hrm_data_type");
// const {sys_request_method} = proxy.useDict("sys_request_method");

const testStepsData = defineModel('testStepsData', {required: true});
const responseData = defineModel('responseData')


function editTabs(paneName, action, tapType) {
  if (action === "remove") {
    const oldActiveStep = activeTestStepName.value;

    const currentTabIndex = paneName !== undefined ? paneName : activeTestStepName.value;

    testStepsData.value.splice(currentTabIndex, 1);
    if (testStepsData.value.length <= 0) {
      let tmpStepData = JSON.parse(JSON.stringify(initStepData))
      tmpStepData.step_id = randomString(10);
      testStepsData.value.push(tmpStepData);
      activeTestStepName.value = 0;
      return
    }

    if (oldActiveStep >= currentTabIndex) {
      if (oldActiveStep === 0) {
        activeTestStepName.value = 0;
        return;
      }
      activeTestStepName.value = oldActiveStep - 1;
    }

  } else if (action === "add") {
    if (!tapType) {
      alert("参数错误")
    }
    let newTabName = paneName !== undefined ? paneName + 1 : activeTestStepName.value + 1;
    const tapData = JSON.parse(JSON.stringify(initStepData));
    if (tapType === 2){
      tapData.request = JSON.parse(JSON.stringify(initWebsocketData));
    }
    tapData.step_id = randomString(10);

    tapData.step_type = tapType;
    testStepsData.value.splice(newTabName, 0, tapData)
    activeTestStepName.value = newTabName
  } else {
    console.log("other")
  }
}


</script>

<template>
  <el-tabs tab-position="left" class="demo-tabs"
           v-model="activeTestStepName" style="height: 100%">
    <el-tab-pane v-for="(step, index) in testStepsData" :key="step.step_id" :name="index">
      <template #label>
        <EditLabel v-model="step.name" :index-key="index" :type="step.step_type" @edit-element="editTabs"></EditLabel>
      </template>
      <el-tabs type="" v-model="activeRequestName">
        <el-tab-pane label="request" name="stepRequest">
          <template v-if="step.step_type === 1">
            <StepRequest v-model:request-detail-data="step.request" v-model:response-data="responseData"></StepRequest>
          </template>
          <template v-if="step.step_type === 2">
            <StepWebsocket v-model:request-detail-data="step.request"
                           v-model:response-data="responseData"></StepWebsocket>
          </template>

        </el-tab-pane>
        <el-tab-pane label="extract/validate" name="stepEv">
          extract
          <TableExtract v-model="step.extract"></TableExtract>
          validate
          <TableValidate v-model="step.validate"></TableValidate>
        </el-tab-pane>
        <el-tab-pane label="variables/hooks" name="stepVh">
          variables
          <TableVariables v-model="step.variables"></TableVariables>
          setup_hooks
          <TableHooks v-model="step.setup_hooks"></TableHooks>
          teardown_hooks
          <TableHooks v-model="step.teardown_hooks"></TableHooks>
        </el-tab-pane>
        <el-tab-pane label="thinktime" name="stepThinktime">
          <div>
            <el-input
                v-model="step.think_time.limit"
                style="max-width: 600px"
                placeholder="Please input"
            >
              <template #prepend>thinktime</template>
            </el-input>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-tab-pane>
  </el-tabs>
</template>

<style scoped lang="scss">

</style>