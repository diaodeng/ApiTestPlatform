<script setup>

import SplitWindow from "@/components/hrm/common/split-window.vue";
import AceEditor from "@/components/hrm/common/ace-editor.vue";
import TableHeaders from "@/components/hrm/table-headers.vue";


const {proxy} = getCurrentInstance();

const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const {hrm_data_type} = proxy.useDict("hrm_data_type");
const {sys_request_method} = proxy.useDict("sys_request_method");

const stepDetailData = defineModel("stepDetailData", {required:true});

const activeRequestDetailName = ref("requestHeader")
</script>

<template>
  <el-row :gutter="10" type="flex" class="row-bg">
    <el-col :span="24">
      <div>
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
  <el-row type="flex" class="row-bg" justify="start">
    <el-tabs v-model="activeRequestDetailName" style="width: 100%">
      <SplitWindow>
        <template #left>
          <el-tab-pane label="header" name="requestHeader">header
            <TableHeaders
                v-model:self-data="stepDetailData.request.headers"
                v-model:include="stepDetailData.include"
            ></TableHeaders>
          </el-tab-pane>
          <el-tab-pane label="data" name="requestJson">
            <div style="width: 100%">
              <AceEditor v-model:content="stepDetailData.request.data" can-set="true" height="calc(100vh - 410px)"></AceEditor>
            </div>
          </el-tab-pane>
        </template>
        <template #right>
          <AceEditor v-model:content="stepDetailData.result" can-set="true" height="calc(100vh - 410px)"></AceEditor>
        </template>
      </SplitWindow>
    </el-tabs>
  </el-row>
</template>

<style scoped lang="scss">

</style>