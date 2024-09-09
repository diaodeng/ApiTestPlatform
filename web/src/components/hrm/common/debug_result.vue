<script setup>

import AceEditor from "@/components/hrm/common/ace-editor.vue";
import {Json, decompressText} from "@/utils/tools.js";


const activeTab = defineModel("activeTab", {required: true, default: "response"})
const stepDetailData = defineModel("stepDetailData", {required: true})
const props = defineProps({editHeight: {default: 'calc(100vh - 160px)'}})

const calcResponse = computed({
  get() {
    if (stepDetailData.value.result && stepDetailData.value.result.response) {
      let response = stepDetailData.value.result.response;
      if (typeof response === "string") {
        response = Json.parse(decompressText(response));
        stepDetailData.value.result.response = response;
      }
      const data = response.body || response.text || "";
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
    let logs = stepDetailData.value.result.logs;
    if (typeof logs === "string") {
      logs = Json.parse(decompressText(logs));
    }
    return (logs.before_request || "")
        + "\n"
        + (logs.after_response || "")
        + "\n"
        + (logs.error || "");
  } else {
    return "";
  }
})

const calcErrorLogs = computed(() => {
  if (stepDetailData.value.result && stepDetailData.value.result.logs) {
    let logs = stepDetailData.value.result.logs;
    if (typeof logs === "string") {
      logs = Json.parse(decompressText(logs));
    }
    return logs.error || "";
  } else {
    return "";
  }
})
</script>

<template>
  <el-tabs v-model="activeTab" class="request-detail">
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

<style scoped lang="scss">

</style>