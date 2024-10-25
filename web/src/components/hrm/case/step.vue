<script setup>
import {ElMessageBox} from "element-plus";
import TableExtract from "@/components/hrm/table-extract.vue";
import EditLabel from "@/components/hrm/common/edite-label.vue";
import TableHooks from "@/components/hrm/table-hooks.vue";
import TableValidate from "@/components/hrm/table-validate.vue";
import TableVariables from "@/components/hrm/table-variables.vue";
import StepRequest from "@/components/hrm/case/step-request.vue";
import StepWebsocket from "@/components/hrm/case/step-websocket.vue";
import {randomString} from "@/utils/tools.js";
import {initStepData, initWebsocketData} from "@/components/hrm/data-template.js";
import {CaseStepTypeEnum} from "@/components/hrm/enum.js";
import {useResizeObserver} from "@vueuse/core";


const testStepsData = defineModel('testStepsData', {required: true});
const props = defineProps(["stepsHeight"]);


// const {proxy} = getCurrentInstance();
const activeRequestName = ref("stepRequest");
const activeTestStepName = ref(0);
const tabsHeight = ref(0);
const tabsRef = ref();

// const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
// const {hrm_data_type} = proxy.useDict("hrm_data_type");
// const {sys_request_method} = proxy.useDict("sys_request_method");


function editTabs(action, paneName, tapType, initTabData) {
  if (action === "remove") {
    const oldActiveStep = activeTestStepName.value;

    const currentTabIndex = paneName !== undefined ? paneName : activeTestStepName.value;

    testStepsData.value.splice(currentTabIndex, 1);
    if (testStepsData.value.length <= 0) {
      let tmpStepData = JSON.parse(JSON.stringify(initStepData));
      tmpStepData.step_id = randomString(10);
      testStepsData.value.push(tmpStepData);
      activeTestStepName.value = 0;
      return;
    }

    if (oldActiveStep >= currentTabIndex) {
      if (oldActiveStep === 0) {
        activeTestStepName.value = 0;
        return;
      }
      activeTestStepName.value = oldActiveStep - 1;
    }

  } else if (action === "add") {

    let newTabName = paneName !== undefined ? paneName + 1 : activeTestStepName.value + 1;

    testStepsData.value.splice(newTabName, 0, initTabData)
    activeTestStepName.value = newTabName
  } else {
    console.log("other")
  }
}


useResizeObserver(tabsRef, (entries) => {
  const entry = entries[0]
  const {width, height} = entry.contentRect;
  nextTick(() => {
    tabsHeight.value = height;
  })

})

</script>

<template>
  <el-scrollbar :height="stepsHeight" ref="tabsRef">
    <el-tabs tab-position="left" class="demo-tabs"
             v-model="activeTestStepName">
      <el-tab-pane v-for="(step, index) in testStepsData" :key="step.step_id" :name="index"
                   :style="{height: tabsHeight + 'px'}">
        <template #label>
          <EditLabel v-model="step.name" :index-key="index" :type="step.step_type" @edit-element="editTabs"></EditLabel>
        </template>
        <el-tabs type="" v-model="activeRequestName">
          <el-tab-pane :label="$t('message.caseDetail.tabNames.request')" name="stepRequest">
            <template v-if="step.step_type === CaseStepTypeEnum.http">
              <StepRequest v-model:step-detail-data="testStepsData[index]"
                           :request-container-height="tabsHeight - 5"
              ></StepRequest>
            </template>
            <template v-if="step.step_type === CaseStepTypeEnum.websocket">
              <StepWebsocket v-model:step-detail-data="testStepsData[index]"
                             :step-container-height="tabsHeight - 5"></StepWebsocket>
            </template>

          </el-tab-pane>
          <el-tab-pane :label="$t('message.caseDetail.tabNames.ev')" name="stepEv">
            <el-scrollbar :max-height="tabsHeight-55">
              <TableExtract v-model="step.extract" :table-title="$t('message.configTable.header.extract')"></TableExtract>
              <TableValidate v-model="step.validate" :table-title="$t('message.configTable.header.validate')"></TableValidate>
            </el-scrollbar>
          </el-tab-pane>
          <el-tab-pane :label="$t('message.caseDetail.tabNames.vh')" name="stepVh" :class="['step-variables-hooks-stepVh' + step.step_id]">
            <el-scrollbar :max-height="tabsHeight-55">
              <TableVariables v-model="step.variables"
                              :table-title="$t('message.configTable.header.variables')"
              ></TableVariables>

              <TableHooks v-model="step.setup_hooks" :table-title="$t('message.configTable.header.setup_hooks')"></TableHooks>

              <TableHooks v-model="step.teardown_hooks" :table-title="$t('message.configTable.header.teardown_hooks')"></TableHooks>
            </el-scrollbar>
          </el-tab-pane>
          <el-tab-pane :label="$t('message.caseDetail.tabNames.other')" name="stepThinktime">
            <el-row>
              <el-input
                  v-model="step.think_time.limit"
                  style="max-width: 600px"
                  placeholder="Please input"
              >
                <template #prepend>
                  <el-switch v-model="step.think_time.enable"
                             size="small"
                  ></el-switch>
                  {{ $t('message.other.thinktime') }}
                </template>
              </el-input>
            </el-row>
            <el-row style="margin-top: 5px">

              <el-input
                  v-model="step.time_out.limit"
                  style="max-width: 600px"
                  placeholder="Please input"
              >
                <template #prepend>
                  <el-switch v-model="step.time_out.enable"
                             size="small"
                  ></el-switch>
                  {{ $t('message.other.timeout') }}
                </template>
              </el-input>
            </el-row>
            <el-row style="margin-top: 5px">

              <el-input
                  v-model="step.retry.limit"
                  style="max-width: 600px"
                  placeholder="Please input"
              >
                <template #prepend>
                  <el-switch v-model="step.retry.enable"
                             size="small"
                  ></el-switch>
                  {{ $t('message.other.retry') }}
                </template>
              </el-input>
            </el-row>
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>
    </el-tabs>
  </el-scrollbar>

</template>

<style scoped lang="scss">

</style>