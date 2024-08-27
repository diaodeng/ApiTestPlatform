<script setup>

import SplitWindow from "@/components/hrm/common/split-window.vue";
import AceEditor from "@/components/hrm/common/ace-editor.vue";
import TableHeaders from "@/components/hrm/table-headers.vue";
import TableVariables from "@/components/hrm/table-variables.vue";
import DictSelect from "@/components/select/dict_select.vue";
import Fullscreen from "@/components/hrm/common/fullscreen.vue";
import {Json} from "@/utils/tools.js";


const {proxy} = getCurrentInstance();

const {sys_request_method} = proxy.useDict("sys_request_method");

const stepDetailData = defineModel("stepDetailData", {required: true});
const props = defineProps(["editHeight"]); // 编辑器高度，默认是100vh - 160px

const activeRequestDetailName = ref("requestHeader")
const activeResultTab = ref("response")

const calcResponse = computed({
  get() {
    if (stepDetailData.value.result && stepDetailData.value.result.response) {
      const data = stepDetailData.value.result.response.body || stepDetailData.value.result.response.text || "";
      try {
        return Json.beautifulJson(data);
      } catch (e) {
        return data;
      }
    } else {
      return "";
    }
  },
  set(newValue) {
    stepDetailData.value.result.response.body = newValue
  }
})

const calcLogs = computed(() => {
  if (stepDetailData.value.result && stepDetailData.value.result.logs) {
    return (stepDetailData.value.result.logs.before_request || "")
        + "\n"
        + (stepDetailData.value.result.logs.after_response || "")
        + "\n"
        + (stepDetailData.value.result.logs.error || "");
  } else {
    return "";
  }
})

const calcErrorLogs = computed(() => {
  if (stepDetailData.value.result && stepDetailData.value.result.logs) {
    return stepDetailData.value.result.logs.error || "";
  } else {
    return "";
  }
})

</script>

<template>
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
    <SplitWindow left-width="50%">
      <template #left>
        <el-tabs v-model="activeRequestDetailName"
                 style="width: 100%;"
                 class="request-detail">
          <el-tab-pane label="header" name="requestHeader">
            <TableHeaders v-model:self-data="stepDetailData.request.headers"
                          v-model:include="stepDetailData.include"
                          show-include="true"></TableHeaders>
          </el-tab-pane>
          <el-tab-pane label="json" name="requestJson">
            <AceEditor v-model:content="stepDetailData.request.json" can-set="true" :height="editHeight"></AceEditor>
          </el-tab-pane>
          <el-tab-pane label="data" name="requestData">
            <TableVariables v-model="stepDetailData.request.data"></TableVariables>
          </el-tab-pane>
          <el-tab-pane label="param" name="requestParam">
            <TableVariables v-model="stepDetailData.request.params"></TableVariables>
          </el-tab-pane>
        </el-tabs>
      </template>
      <template #right>
        <el-tabs v-model="activeResultTab" class="request-detail">
          <el-tab-pane label="响应" name="response">
            <AceEditor v-model:content="calcResponse" can-set="true" can-search="true"
                       :height="editHeight"></AceEditor>
          </el-tab-pane>
          <el-tab-pane label="日志" name="logs">
            <AceEditor v-model:content="calcLogs" can-set="true" :height="editHeight"></AceEditor>
          </el-tab-pane>
          <el-tab-pane label="异常" name="errorLogs">
            <AceEditor v-model:content="calcErrorLogs" can-set="true" :height="editHeight"></AceEditor>
          </el-tab-pane>
        </el-tabs>
      </template>
    </SplitWindow>

  </el-row>
</template>

<style scoped lang="scss">
:deep(.el-tabs.request-detail .el-tabs__content) {
  height: calc(100vh - 300px) !important;
  //display: flex;
  //flex-grow: 1;
  overflow-y: auto;
}
</style>