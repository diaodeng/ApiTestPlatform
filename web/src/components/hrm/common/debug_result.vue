<script setup>

import AceEditor from "@/components/hrm/common/ace-editor.vue";
import {Json, decompressText} from "@/utils/tools.js";
import {useResizeObserver} from "@vueuse/core";


const activeTab = defineModel("activeTab", {required: true, default: "response"})
const stepDetailData = defineModel("stepDetailData", {required: true})
const props = defineProps({
  editHeight: {default: 'calc(100vh - 160px)'},
  tabHeight: {default: 'calc(100vh - 160px)'}
})

const debugContainerRef = ref();
const containerHeight = ref(0);

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
        return data ? Json.beautifulJson(data) : "";
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
});

const calcLogs = computed({
  get() {
    if (stepDetailData.value.result && stepDetailData.value.result.logs) {
      let logs = stepDetailData.value.result.logs;
      if (typeof logs === "string") {
        logs = Json.parse(decompressText(logs));
      }
      return (logs.before_request || "")
          + "\n"
          + (logs.after_response || "");
    } else {
      return "";
    }
  },
  set(newValue) {

  }

});

const calcErrorLogs = computed({
  get() {
    if (stepDetailData.value.result && stepDetailData.value.result.logs) {
      let logs = stepDetailData.value.result.logs;
      if (typeof logs === "string") {
        logs = Json.parse(decompressText(logs));
      }
      return logs.error || "";
    } else {
      return "";
    }
  },
  set(newValue) {

  }

});

const responseEditHeight = computed(() => {
  return (containerHeight.value - 35) + 'px';
})

const logEditHeight = computed(() => {
  return (containerHeight.value - 27) + 'px';
})

useResizeObserver(debugContainerRef, (entries) => {
  const entry = entries[0]
  const {width, height} = entry.contentRect;
  containerHeight.value = height;
})


</script>

<template>
  <div :style="{height: tabHeight + 'px'}" ref="debugContainerRef">
    <div v-if="!calcResponse">{{ calcResponse }}</div>
    <el-tabs v-model="activeTab" class="request-detail">
      <el-tab-pane label="响应" name="response" key="tab_response">
        <AceEditor v-model:content="calcResponse" :can-set="true" :can-search="true"
                   :height="responseEditHeight" key="edit_response"></AceEditor>
      </el-tab-pane>
      <el-tab-pane label="日志" name="logs" key="tab_logs">
        <AceEditor v-model:content="calcLogs"
                   :can-set="true"
                   :height="logEditHeight"
                   key="edit_logs"
                   lang="text"
                   :read-only="true"
                   :enable-basic-autocompletion="false"
                   :enable-live-autocompletion="false"
                   :enable-snippets="false"
        ></AceEditor>
      </el-tab-pane>
      <el-tab-pane label="异常" name="errorLogs" key="tab_errorLogs">
        <AceEditor v-model:content="calcErrorLogs"
                   :can-set="true"
                   :height="logEditHeight"
                   key="edit_errorLogs"
                   :read-only="true"
                   :enable-basic-autocompletion="false"
                   :enable-live-autocompletion="false"
                   :enable-snippets="false"
        ></AceEditor>
      </el-tab-pane>
    </el-tabs>
  </div>


</template>

<style scoped lang="scss">

</style>