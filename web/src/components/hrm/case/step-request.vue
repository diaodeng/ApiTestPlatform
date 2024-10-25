<script setup>

import SplitWindow from "@/components/hrm/common/split-window.vue";
import AceEditor from "@/components/hrm/common/ace-editor.vue";
import DebugResult from "@/components/hrm/common/debug_result.vue";
import TableHeaders from "@/components/hrm/table-headers.vue";
import TableVariables from "@/components/hrm/table-variables.vue";
import DictSelect from "@/components/select/dict_select.vue";
import {useResizeObserver} from '@vueuse/core'
import {parseHeightValue} from "@/utils/tools.js";


const {proxy} = getCurrentInstance();

const {sys_request_method} = proxy.useDict("sys_request_method");
const stepRef = ref(null);

const stepDetailData = defineModel("stepDetailData", {required: true});
const props = defineProps({
  editHeight: {
    default: "calc(100vh - 160px)"
  },
  requestContainerHeight: {
    default: "calc(100vh - 160px)"
  }
}); // 编辑器高度，默认是100vh - 160px

const activeRequestDetailName = ref("requestHeader")
const activeResultTab = ref("response")

const containerHeight = ref(0);
const tabsMaxHeight = ref(0);


useResizeObserver(stepRef, (entries) => {
  const entry = entries[0]
  const {width, height} = entry.contentRect;

  containerHeight.value = height;

  tabsMaxHeight.value = containerHeight.value - 133;
})


const calcRequestContainerHeight = computed(()=>{
  return parseHeightValue(props.requestContainerHeight);
});

</script>

<template>
  <div ref="stepRef" :style="{height: calcRequestContainerHeight}">
    <el-row :gutter="10" type="flex" class="row-bg">
      <el-col style="display: flex">
        <DictSelect :options-dict="sys_request_method" v-model="stepDetailData.request.method"
                    style="width: 110px"></DictSelect>

        <div style="flex-grow: 1;padding-left: 5px">
          <el-input
              v-model="stepDetailData.request.url"
              placeholder="Please input"
          >
            <template #prepend>URL</template>
            <template #append>
              <el-dropdown>
              <span class="el-dropdown-link">
                <el-icon class="el-icon--right">
                  <arrow-down/>
                </el-icon>
              </span>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item disabled>111</el-dropdown-item>
                    <el-dropdown-item disabled>222</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-input>
        </div>
      </el-col>
    </el-row>
    <el-row type="flex" class="row-bg" justify="start" style="flex-grow: 1; ">
      <SplitWindow left-width="50%" :window-height="containerHeight - 80 + 'px'">
        <template #left>
          <el-tabs v-model="activeRequestDetailName"
                   style="width: 100%;"
                   class="request-detail">
            <el-tab-pane label="header" name="requestHeader">
              <el-scrollbar :max-height="tabsMaxHeight">
                <TableHeaders v-model:self-data="stepDetailData.request.headers"
                              v-model:include="stepDetailData.include"
                              :show-include="true"></TableHeaders>
              </el-scrollbar>
            </el-tab-pane>
            <el-tab-pane label="json" name="requestJson">
              <AceEditor v-model:content="stepDetailData.request.json" :can-set="true"
                         :height="tabsMaxHeight - 25 + 'px'"></AceEditor>
            </el-tab-pane>
            <el-tab-pane label="data" name="requestData">
              <el-scrollbar :max-height="tabsMaxHeight">
                <TableVariables v-model="stepDetailData.request.data"></TableVariables>
              </el-scrollbar>

            </el-tab-pane>
            <el-tab-pane label="param" name="requestParam">
              <el-scrollbar :max-height="tabsMaxHeight">
                <TableVariables v-model="stepDetailData.request.params"></TableVariables>
              </el-scrollbar>

            </el-tab-pane>
          </el-tabs>
        </template>
        <template #right>
          <DebugResult v-model:active-tab="activeResultTab"
                       v-model:step-detail-data="stepDetailData"
                       :tab-height="tabsMaxHeight"
          ></DebugResult>
          <!--        <el-tabs v-model="activeResultTab" class="request-detail">-->
          <!--          <el-tab-pane label="响应" name="response">-->
          <!--            <AceEditor v-model:content="calcResponse" can-set="true" can-search="true"-->
          <!--                       :height="editHeight"></AceEditor>-->
          <!--          </el-tab-pane>-->
          <!--          <el-tab-pane label="日志" name="logs">-->
          <!--            <AceEditor v-model:content="calcLogs" can-set="true" :height="editHeight"></AceEditor>-->
          <!--          </el-tab-pane>-->
          <!--          <el-tab-pane label="异常" name="errorLogs">-->
          <!--            <AceEditor v-model:content="calcErrorLogs" can-set="true" :height="editHeight"></AceEditor>-->
          <!--          </el-tab-pane>-->
          <!--        </el-tabs>-->
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