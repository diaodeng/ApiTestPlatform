<script setup name="Api">
import {ElMessage} from "element-plus";
import SplitWindow from "@/components/hrm/common/split-window.vue";
import TreeView from "@/components/hrm/common/tree-view.vue";
import EnvSelector from "@/components/hrm/common/env-selector.vue";
import {addApi, apiTree, getApi} from "@/api/hrm/api.js";
import {initApiFormData, initStepData} from "@/components/hrm/data-template.js";
import {randomString} from "@/utils/tools.js";
import {CaseStepTypeEnum, HrmDataTypeEnum, RunTypeEnum} from "@/components/hrm/enum.js";
import {debugCase, getComparator} from "@/api/hrm/case.js";
import StepRequest from "@/components/hrm/case/step-request.vue";
import StepWebsocket from "@/components/hrm/case/step-websocket.vue";
import FullScreen from "@/components/hrm/common/fullscreen.vue";
import AceEditor from "@/components/hrm/common/ace-editor.vue";


const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const {hrm_data_type} = proxy.useDict("hrm_data_type");

provide("hrm_data_type", hrm_data_type);
provide('sys_normal_disable', sys_normal_disable);

const treeDataSource = ref([]);
const hrm_comparator_dict = ref({});

const folderForm = ref({parentID: null, name: null})
const apiTabsData = ref([initApiFormData]);
let currentApiData = apiTabsData.value[0];
const selectedEnv = ref("");
const currentTab = ref(0);
const loadingApi = ref(false);
const loading = ref({
  page: false,
  loadApiTree: false,
  loadApiInfo: false,
  saveApi: false,
  debugApi: false,
  preSaveDialog: false,
  preSaveFolderDialog: false
})

onMounted(() => {
  getApiTree();
  getComparator().then(response => {
    hrm_comparator_dict.value = response.data;
  });
});

provide("hrm_comparator_dict", hrm_comparator_dict);


function addApiStep() {
  let tmpStepData = JSON.parse(JSON.stringify(initStepData));
  tmpStepData.step_id = randomString(10);
  currentApiData.value.requestInfo.teststeps.push(tmpStepData);
}

function getApiInfo(apiId) {
  getApi(apiId).then(res => {
    const data = ref(res.data);
    apiTabsData.value.push(data);
    currentApiData = toRef(data);
  })
}

function saveApiInfo() {
  loading.value.saveApi = true;
  let data = toRaw(currentApiData);
  data.type = HrmDataTypeEnum.api
  addApi(data).then(res => {
    ElMessage({message: "API保存成功", type: "success"});
  }).finally(() => {
    loading.value.saveApi = false;
    loading.value.preSaveDialog = false;
  })
}

function saveFolderInfo() {
  loading.value.preSaveFolderDialog = true;
  let data = folderForm.value;
  data.type = HrmDataTypeEnum.folder
  addApi(data).then(res => {
    ElMessage({message: "Folder保存成功", type: "success"});
  }).finally(() => {
    loading.value.preSaveFolderDialog = false;
  })
}

function getApiTree() {
  loadingApi.value = true;
  apiTree({private: false}).then(res => {
    treeDataSource.value = res.data;
  }).finally(() => {
    loadingApi.value = false;
  })
}

function nodeDbClick(event, node, data) {
  if (node.data.isParent) {
    node.expanded = !node.expanded;
  } else {
    const nodeId = node.data.api_id;
    const nodeTabIndex = apiTabsData.value.findIndex(dict => dict.apiId === nodeId);
    if (nodeTabIndex !== -1) {
      currentTab.value = nodeId;
      currentApiData = apiTabsData.value[nodeTabIndex];
    } else {
      loadingApi.value = true;
      getApi(node.data.api_id).then(res => {
        // const data = ref(res.data);
        apiTabsData.value.push(res.data);
        currentApiData = apiTabsData.value[apiTabsData.value.length - 1];
        currentTab.value = res.data.apiId;

        if (apiTabsData.value[0].isEmpty) {
          apiTabsData.value.splice(0, 1);
        }
        console.log("当前tab：" + currentTab.value)
      }).catch(() => {

      }).finally(() => {
        loadingApi.value = false
      })

    }
  }

}


currentApiData.isEmpty = true;

function delTab(event, tabId) {
  const currentTabIndex = apiTabsData.value.findIndex(dict => dict.apiId === tabId);
  if (currentTabIndex === -1) {
    return;
  }
  if (apiTabsData.value.length === 1) {
    apiTabsData.value.push(JSON.parse(JSON.stringify(initApiFormData)));
    currentApiData = apiTabsData.value[1];

    currentTab.value = currentApiData.apiId;
    // currentTab.value = 0;
  } else if (apiTabsData.value.length - 1 === currentTabIndex) {
    currentApiData = apiTabsData.value[currentTabIndex - 1];
    currentTab.value = currentApiData.apiId;
  } else {
    currentApiData = apiTabsData.value[currentTabIndex + 1];
    currentTab.value = currentApiData.apiId;
  }
  apiTabsData.value.splice(currentTabIndex, 1);
  // apiTabsData.value.splice(tabId, 1);
  console.log("删除了tab:" + tabId)
}

function clickTab(tab, event) {
  const currentTabIndex = apiTabsData.value.findIndex(dict => dict.apiId === tab.paneName);
  currentApiData = apiTabsData.value[currentTabIndex];
  currentTab.value = tab.paneName;
  console.log("点击了tab:" + tab.paneName + " " + "当前tab：" + currentTab.value)
}

function activeTabChange(tabName) {
  console.log("tab切换了:" + tabName + "  " + "当前tab：" + currentTab.value)
  // currentApiData = apiTabsData.value[tabName];
}

function debug() {
  loading.value.debugApi = true;
  const apiData = toRaw(currentApiData);
  let caseData = {
    request: apiData.requestInfo,
    type: apiData.type,
    name: apiData.name
  }
  delete caseData.request.config.result;
  delete caseData.request.teststeps[0].result;
  caseData.request.config.name = caseData.name;
  const req_data = {
    "env": selectedEnv.value,
    "runType": RunTypeEnum.api,
    "caseData": caseData
  }
  debugCase(req_data).then(response => {
    ElMessage.success(response.msg);
    for (const step_result_key in response.data) {
      currentApiData.requestInfo.teststeps.find(dict => dict['step_id'] === step_result_key).result = response.data[step_result_key]
    }

    // responseData.value = response.data.log
    // open.value = false;
    // getList();
  }).finally(()=>{
    loading.value.debugApi = false;
  });
}

</script>

<template>
  <div class="app-container" v-loading="loadingApi">
    <el-button size="small" @click="getApiTree" icon="RefreshRight"></el-button>
    <el-button size="small" @click="loading.preSaveFolderDialog = true">新增文件夹</el-button>
    <el-button size="small" @click="loading.preSaveDialog = true" v-loading="loading.saveApi">保存</el-button>
    <el-button size="small" @click="debug" v-loading="loading.debugApi">调试</el-button>
    <EnvSelector v-model:selected-env="selectedEnv" size="small"></EnvSelector>

    <el-container>
      <split-window left-width="250px" window-height="calc(100vh - 156px)">
        <template v-slot:left>
          <el-scrollbar>
            <div style="display: flex;">
              <TreeView v-model="treeDataSource" @node-db-click="nodeDbClick"></TreeView>
            </div>

          </el-scrollbar>

        </template>
        <template v-slot:right>
          <el-container style="display:flex;flex-direction: column;height: 100%; padding-left: 5px;">
            <el-tabs addable type="card"
                     v-model="currentTab"
                     @tab-click="clickTab"
                     @tab-change="activeTabChange"
            >
              <el-tab-pane v-for="(apiData, index) in apiTabsData" :label="apiData.name"
                           :key="apiData.requestInfo.teststeps[0].step_id" :name="apiData.apiId">
                <template #label size="small">
                  <el-badge is-dot :hidden="!apiData.modify">
                    <span style="margin: 0px; padding: 0px">
                      <span>{{ apiData.name }}</span>
                      <el-button @click.stop="(event) => {delTab(event, apiData.apiId)}" icon="Close" link></el-button>
                    </span>
                  </el-badge>
                </template>
              </el-tab-pane>
            </el-tabs>
            <div v-if="currentApiData" style="flex-grow: 1;display: flex;flex-direction: column;">
              <template v-if="currentApiData.requestInfo.teststeps[0].step_type === CaseStepTypeEnum.http">
                <StepRequest v-model:request-detail-data="currentApiData.requestInfo.teststeps[0].request"
                             v-model:response-data="currentApiData.requestInfo.teststeps[0].result"
                             edit-height="calc(100vh - 332px)"
                ></StepRequest>
              </template>
              <template v-if="currentApiData.requestInfo.teststeps[0].step_type === CaseStepTypeEnum.websocket">
                <StepWebsocket v-model:request-detail-data="currentApiData.requestInfo.teststeps[0].request"
                               v-model:response-data="currentApiData.requestInfo.teststeps[0].result"></StepWebsocket>
              </template>
            </div>

          </el-container>

        </template>
      </split-window>
    </el-container>
    <el-dialog :title="currentApiData.name" @close="loading.preSaveDialog = false" v-model="loading.preSaveDialog">
      <el-main>
        <el-input v-model="currentApiData.name" placeholder="请输入名称">
          <template #prepend>
            <el-text>API名称:</el-text>
          </template>
        </el-input>
      </el-main>
      <el-button type="info" @click="loading.preSaveDialog = false">取消</el-button>
      <el-button type="primary" @click="saveApiInfo" :disabled="loading.saveApi">保存</el-button>
    </el-dialog>

    <el-dialog :title="folderForm.name" @close="loading.preSaveFolderDialog = false"
               v-model="loading.preSaveFolderDialog">
      <el-main>
        <el-input v-model="folderForm.name" placeholder="请输入文件夹名称">
          <template #prepend>
            <el-text>文件夹名称:</el-text>
          </template>
        </el-input>
      </el-main>
      <el-button type="info" @click="loading.preSaveFolderDialog = false">取消</el-button>
      <el-button type="primary" @click="saveFolderInfo" :disabled="loading.saveApi">保存</el-button>
    </el-dialog>
  </div>

</template>

<style scoped lang="scss">

</style>