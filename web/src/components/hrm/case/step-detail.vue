<script setup>
import {CaseStepTypeEnum} from "@/components/hrm/enum";
import TableHooks from "@/components/hrm/table-hooks.vue";
import TableVariables from "@/components/hrm/table-variables.vue";
import TableValidate from "@/components/hrm/table-validate.vue";
import TableExtract from "@/components/hrm/table-extract.vue";
import {initStepData} from "@/components/hrm/data-template.js";
import StepRequest from "@/components/hrm/case/step-request.vue"
import StepWebsocket from "@/components/hrm/case/step-websocket.vue"

const currentStepDataRef = defineModel("stepData", {required: true, default: JSON.parse(JSON.stringify(initStepData))});
const loading = defineModel('loading');
const props = defineProps({tabsHeight: {type: Number}});
const activeRequestName = ref("stepRequest");
watch(()=>currentStepDataRef.value, async (newData)=>{
  await nextTick();
  loading.value = false;
});

</script>

<template>
  <el-tabs type="" v-model="activeRequestName">
    <el-tab-pane :label="$t('message.caseDetail.tabNames.request_base')" name="stepRunCondition">
      <div>
        <div>
          <el-text style="font-weight: bold">是否执行步骤：</el-text>
          <el-switch v-model="currentStepDataRef.run_condition.isRunInfo.enable"
                     inline-prompt
                     active-text="启用"
                     inactive-text="禁用"
          ></el-switch>
        </div>
        <div>
          <el-input v-model="currentStepDataRef.run_condition.isRunInfo.conditionSource">
            <template #prepend>判断条件：</template>
          </el-input>
        </div>
      </div>
      <div style="margin-top: 10px">
        <div>
          <el-text style="font-weight: bold">循环执行步骤：</el-text>
          <el-switch v-model="currentStepDataRef.run_condition.loopRunInfo.enable"
                     inline-prompt
                     active-text="启用"
                     inactive-text="禁用"
          ></el-switch>
        </div>

        <div style="margin-bottom: 10px">

          <el-input v-model="currentStepDataRef.run_condition.loopRunInfo.conditionSource">
            <template #prepend>循环条件：</template>
          </el-input>
        </div>
        <div>
          <el-input v-model="currentStepDataRef.run_condition.loopRunInfo.loopVar">
            <template #prepend>过程变量名：</template>
          </el-input>
        </div>
      </div>
    </el-tab-pane>
    <el-tab-pane :label="$t('message.caseDetail.tabNames.request')" name="stepRequest">
      <template v-if="currentStepDataRef.step_type === CaseStepTypeEnum.http">
        <StepRequest v-model:step-detail-data="currentStepDataRef"
                     :request-container-height="tabsHeight - 5"
        ></StepRequest>
      </template>
      <template v-if="currentStepDataRef.step_type === CaseStepTypeEnum.websocket">
        <StepWebsocket v-model:step-detail-data="currentStepDataRef"
                       :step-container-height="tabsHeight - 5"></StepWebsocket>
      </template>

    </el-tab-pane>
    <el-tab-pane :label="$t('message.caseDetail.tabNames.ev')" name="stepEv">
      <el-scrollbar :max-height="tabsHeight-55">
        <TableExtract v-model="currentStepDataRef.extract"
                      :table-title="$t('message.configTable.header.extract')"></TableExtract>
        <TableValidate v-model="currentStepDataRef.validate"
                       :table-title="$t('message.configTable.header.validate')"></TableValidate>
      </el-scrollbar>
    </el-tab-pane>
    <el-tab-pane :label="$t('message.caseDetail.tabNames.vh')" name="stepVh"
                 :class="['step-variables-hooks-stepVh' + currentStepDataRef.step_id]">
      <el-scrollbar :max-height="tabsHeight-55">
        <TableVariables v-model="currentStepDataRef.variables"
                        :table-title="$t('message.configTable.header.variables')"
        ></TableVariables>

        <TableHooks v-model="currentStepDataRef.setup_hooks"
                    :table-title="$t('message.configTable.header.setup_hooks')"></TableHooks>

        <TableHooks v-model="currentStepDataRef.teardown_hooks"
                    :table-title="$t('message.configTable.header.teardown_hooks')"></TableHooks>
      </el-scrollbar>
    </el-tab-pane>
    <el-tab-pane :label="$t('message.caseDetail.tabNames.other')" name="stepThinktime">
      <el-row>
        <el-input
            v-model="currentStepDataRef.think_time.limit"
            style="max-width: 600px"
            placeholder="Please input"
        >
          <template #prepend>
            <el-switch v-model="currentStepDataRef.think_time.enable"
                       size="small"
            ></el-switch>
            {{ $t('message.other.thinktime') }}
          </template>
        </el-input>
      </el-row>
      <el-row style="margin-top: 5px">

        <el-input
            v-model="currentStepDataRef.time_out.limit"
            style="max-width: 600px"
            placeholder="Please input"
        >
          <template #prepend>
            <el-switch v-model="currentStepDataRef.time_out.enable"
                       size="small"
            ></el-switch>
            {{ $t('message.other.timeout') }}
          </template>
        </el-input>
      </el-row>
      <el-row style="margin-top: 5px">

        <el-input
            v-model="currentStepDataRef.retry.limit"
            style="max-width: 600px"
            placeholder="Please input"
        >
          <template #prepend>
            <el-switch v-model="currentStepDataRef.retry.enable"
                       size="small"
            ></el-switch>
            {{ $t('message.other.retry') }}
          </template>
        </el-input>
      </el-row>
    </el-tab-pane>
  </el-tabs>
</template>

<style scoped lang="scss">

</style>