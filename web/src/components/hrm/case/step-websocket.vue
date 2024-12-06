<script setup>

import SplitWindow from "@/components/hrm/common/split-window.vue";
import DebugResult from "@/components/hrm/common/debug_result.vue";
import AceEditor from "@/components/hrm/common/ace-editor.vue";
import TableHeaders from "@/components/hrm/table-headers.vue";
import {useResizeObserver} from "@vueuse/core";
import {parseHeightValue} from "@/utils/tools.js";


const {proxy} = getCurrentInstance();

const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const {hrm_data_type} = proxy.useDict("hrm_data_type");
const {sys_request_method} = proxy.useDict("sys_request_method");

const stepDetailData = defineModel("stepDetailData", {required: true});
const props = defineProps({stepContainerHeight: {default: "calc(100vh-160px)"}}); // 编辑器高度，默认是100vh - 160px

const activeRequestDetailName = ref("requestHeader")
const activeResultTab = ref("response")

const stepContainerRef = ref();
const containerHeight = ref(0);

useResizeObserver(stepContainerRef, (entries) => {
  const entry = entries[0]
  const {width, height} = entry.contentRect;

  containerHeight.value = height;
  console.log(containerHeight.value)

})

const calcStepContainerHeight = computed(()=>{
  return parseHeightValue(props.stepContainerHeight);
});

</script>

<template>
  <div :style="{height:calcStepContainerHeight}" ref="stepContainerRef">
    <el-row :gutter="10" type="flex" class="row-bg">
      <el-col :span="24">
        <div>
          <el-input
              v-model="stepDetailData.request.url"
              placeholder="Please input"
          >
            <template #prepend>URL</template>
          </el-input>
        </div>
      </el-col>
    </el-row>
    <el-row class="row-bg" justify="start">

      <SplitWindow left-width="50%" :window-height="containerHeight + 'px'">

        <template #left>
          <el-tabs v-model="activeRequestDetailName" style="width: 100%">
            <el-tab-pane label="header" name="requestHeader">
              <el-scrollbar :height="containerHeight - 55">
                <TableHeaders
                    v-model:self-data="stepDetailData.request.headers"
                    v-model:include="stepDetailData.include"
                    :show-include="true"
                ></TableHeaders>
              </el-scrollbar>
            </el-tab-pane>
            <el-tab-pane label="data" name="requestJson">
              <div style="width: 100%">
                <AceEditor v-model:content="stepDetailData.request.data" :can-set="true"
                           :height="containerHeight - 80 + 'px'"></AceEditor>
              </div>
            </el-tab-pane>
          </el-tabs>
        </template>
        <template #right>
          <!--          <AceEditor v-model:content="stepDetailData.result" can-set="true" height="calc(100vh - 410px)"></AceEditor>-->
          <DebugResult
              v-model:active-tab="activeResultTab"
              v-model:step-detail-data="stepDetailData"
              :tab-height="containerHeight - 52"></DebugResult>
        </template>

      </SplitWindow>

    </el-row>
  </div>

</template>

<style scoped lang="scss">
//:deep(.el-tabs.request-detail .el-tabs__content) {
//  height: calc(100vh - 300px) !important;
//  //display: flex;
//  //flex-grow: 1;
//  overflow-y: auto;
//}
</style>