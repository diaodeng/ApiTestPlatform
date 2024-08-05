<script setup>

import SplitWindow from "@/components/hrm/common/split-window.vue";
import AceEditor from "@/components/hrm/common/ace-editor.vue";
import TableHeaders from "@/components/hrm/table-headers.vue";
import TableVariables from "@/components/hrm/table-variables.vue";
import DictSelect from "@/components/select/dict_select.vue";


const {proxy} = getCurrentInstance();

const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const {hrm_data_type} = proxy.useDict("hrm_data_type");
const {sys_request_method} = proxy.useDict("sys_request_method");

const requestDetailData = defineModel("requestDetailData", {required:true});
const responseData = defineModel("responseData");

const activeRequestDetailName = ref("requestHeader")
</script>

<template>
  <el-row :gutter="10" type="flex" class="row-bg">
    <el-col :span="2">
      <DictSelect :options-dict="sys_request_method" v-model="requestDetailData.method"
                  style="width: 130px"></DictSelect>
    </el-col>
    <el-col :span="22">
      <div>
        <el-input
            v-model="requestDetailData.url"
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
            <TableHeaders v-model="requestDetailData.headers"></TableHeaders>
          </el-tab-pane>
          <el-tab-pane label="json" name="requestJson">
            <div style="width: 100%">
              <AceEditor v-model:content="requestDetailData.json" can-set="true" height="600px" ></AceEditor>
            </div>
          </el-tab-pane>
          <el-tab-pane label="data" name="requestData">data
            <TableVariables v-model="requestDetailData.data"></TableVariables>
          </el-tab-pane>
          <el-tab-pane label="param" name="requestParam">param
            <TableVariables v-model="requestDetailData.params"></TableVariables>
          </el-tab-pane>
        </template>
        <template #right>
          <AceEditor v-model:content="responseData" can-set="true"></AceEditor>
        </template>
      </SplitWindow>
    </el-tabs>
  </el-row>
</template>

<style scoped lang="scss">

</style>