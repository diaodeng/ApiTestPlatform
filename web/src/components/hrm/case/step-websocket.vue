<script setup>

import SplitWindow from "@/components/hrm/common/split-window.vue";
import AceEditor from "@/components/hrm/common/ace-editor.vue";
import DebugResult from "@/components/hrm/common/debug_result.vue";
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

const stepContainerRef = ref(null);
const containerHeight = ref(0);
const tabsMaxHeight = ref(0);


useResizeObserver(stepContainerRef, (entries) => {
  const entry = entries[0];
  const {width, height} = entry.contentRect;
  containerHeight.value = height;
  tabsMaxHeight.value = containerHeight.value - 133;
});

const calcStepContainerHeight = computed(() => {
  return parseHeightValue(props.stepContainerHeight);
});

</script>

<template>
  <div :style="{height:calcStepContainerHeight}" style="display: flex;flex-direction: column" ref="stepContainerRef">
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
    <el-row type="flex" class="row-bg" justify="start" style="flex-grow: 1; ">

      <SplitWindow left-width="50%" :window-height="containerHeight + 'px'">

        <template #left>
          <el-tabs v-model="activeRequestDetailName" style="width: 100%">
            <el-tab-pane label="header" name="requestHeader">
              <el-scrollbar :max-height="tabsMaxHeight">
                <TableHeaders
                    v-model:self-data="stepDetailData.request.headers"
                    v-model:include="stepDetailData.include"
                    :show-include="true"
                ></TableHeaders>
              </el-scrollbar>
            </el-tab-pane>
            <el-tab-pane label="data" name="requestJson">
              <AceEditor v-model:content="stepDetailData.request.data"
                         :can-set="true"
                         :height="tabsMaxHeight - 25 + 'px'"
              ></AceEditor>
            </el-tab-pane>
          </el-tabs>
        </template>
        <template #right>
          <!--          <AceEditor v-model:content="stepDetailData.result" can-set="true" height="calc(100vh - 410px)"></AceEditor>-->
          <DebugResult
              v-model:active-tab="activeResultTab"
              v-model:step-detail-data="stepDetailData"
              :tab-height="tabsMaxHeight"
          ></DebugResult>
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