<script setup name="Api">
import {ElMessage} from "element-plus";
import SplitWindow from "@/components/hrm/common/split-window.vue";
import TreeView from "@/components/hrm/common/tree-view.vue";
import EnvSelector from "@/components/hrm/common/env-selector.vue";
import {addApi, apiTree, getApi, updateApi} from "@/api/hrm/api.js";
import {list as configList} from "@/api/hrm/config.js";

import {initApiFormData, initStepData} from "@/components/hrm/data-template.js";
import {randomString} from "@/utils/tools.js";
import {CaseStepTypeEnum, HrmDataTypeEnum, RunTypeEnum} from "@/components/hrm/enum.js";
import {debugCase, getComparator} from "@/api/hrm/case.js";
import StepRequest from "@/components/hrm/case/step-request.vue";
import StepWebsocket from "@/components/hrm/case/step-websocket.vue";
import FullScreen from "@/components/hrm/common/fullscreen.vue";
import AceEditor from "@/components/hrm/common/ace-editor.vue";
import {Setting} from "@element-plus/icons-vue";


const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const {hrm_data_type} = proxy.useDict("hrm_data_type");

provide("hrm_data_type", hrm_data_type);
provide('sys_normal_disable', sys_normal_disable);

const treeDataSource = ref([]);
const hrm_comparator_dict = ref({});
const hrm_config_list = ref({});

const folderForm = ref({parentId: null, name: null})
const apiTabsData = ref([]);
const currentApiData = ref(apiTabsData.value[0] || null);
const selectedEnv = ref("");
const currentTab = ref(0);
const loadingApi = ref(false);
const onlySelf = ref(true);
const loading = ref({
  page: false,
  loadApiTree: false,
  loadApiInfo: false,
  saveApi: false,
  debugApi: false,
  preSaveDialog: false,
  preSaveFolderDialog: false,
  filter: false
})

const treeFilterText = ref("");
const treeRef = ref(null);

onMounted(() => {
  getApiTree();
  getComparator().then(response => {
    hrm_comparator_dict.value = response.data;
  });
  configList().then(response => {
    hrm_config_list.value = response.rows;
  });
});

provide("hrm_comparator_dict", hrm_comparator_dict);
provide("hrm_case_config_list", hrm_config_list);


function addApiStep() {
  let tmpStepData = JSON.parse(JSON.stringify(initStepData));
  tmpStepData.step_id = randomString(10);
  currentApiData.value.requestInfo.teststeps.push(tmpStepData);
}

function getApiInfo(apiId) {
  getApi(apiId).then(res => {
    const data = ref(res.data);
    apiTabsData.value.push(data);
    currentApiData.value = toRef(data);
  })
}

function saveApiInfo() {
  loading.value.saveApi = true;
  let data = toRaw(currentApiData.value);

  data.type = HrmDataTypeEnum.api

  if (data.id && data.apiId && !data.isNew) {
    updateApi(data).then(res => {
      ElMessage({message: "API保存成功", type: "success"});
      apiSaveSuccess(res, data.apiId);
    }).catch(error => {
      ElMessage({message: "API保存失败", type: "success"});
    }).finally(() => {
      loading.value.saveApi = false;
      loading.value.preSaveDialog = false;
    })
  } else {
    const oldApiId = data.apiId;
    delete data.isNew;
    delete data.apiId;
    delete data.id;
    addApi(data).then(res => {
      ElMessage({message: "API保存成功", type: "success"});
      apiSaveSuccess(res, oldApiId);
    }).finally(() => {
      loading.value.saveApi = false;
      loading.value.preSaveDialog = false;
    })
  }

}

function apiSaveSuccess(res, oldApiId) {
  let response = res;
  if (response) {
    console.log(response.data.apiId);
    let treeNode = treeRef.value.getNode(oldApiId);
    treeNode.data.apiId = response.data.apiId;
    treeNode.data.name = response.data.name;
    treeNode.data.isNew = false;
  }
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
  apiTree({onlySelf: onlySelf.value}).then(res => {
    treeDataSource.value = res.data;
  }).finally(() => {
    loadingApi.value = false;
  })
}

function nodeDbClick(event, node, data) {
  if (node.data.isParent) {
    node.expanded = !node.expanded;
  } else {
    const nodeId = node.data.apiId;
    const nodeTabIndex = apiTabsData.value.findIndex(dict => dict.apiId === nodeId);
    if (nodeTabIndex !== -1) {
      currentTab.value = nodeId;
      currentApiData.value = apiTabsData.value[nodeTabIndex];
    } else {
      loadingApi.value = true;

      if (node.data.isNew) {
        const emptyData = JSON.parse(JSON.stringify(initApiFormData));
        // currentApiData.value.apiId = nodeId;
        emptyData.isNew = true;
        emptyData.type = HrmDataTypeEnum.api;
        emptyData.requestInfo.api_name = node.name;
        emptyData.parentId = node.data.parentId;
        emptyData.apiId = node.data.apiId;

        apiTabsData.value.push(emptyData);
        currentApiData.value = apiTabsData.value[apiTabsData.value.length - 1];
        currentTab.value = emptyData.apiId;

        if (apiTabsData.value[0].isEmpty) {
          apiTabsData.value.splice(0, 1);
        }

        loadingApi.value = false
        return;
      }

      getApi(node.data.apiId).then(res => {
        // const data = ref(res.data);
        apiTabsData.value.push(res.data);
        currentApiData.value = apiTabsData.value[apiTabsData.value.length - 1];
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


// currentApiData.isEmpty = true;

function delTab(event, tabId) {
  const currentTabIndex = apiTabsData.value.findIndex(dict => dict.apiId === tabId);
  if (currentTabIndex === -1) {
    return;
  }
  if (apiTabsData.value.length === 1) {
    currentApiData.value = false;

    // apiTabsData.value.push(JSON.parse(JSON.stringify(initApiFormData)));
    // currentApiData = apiTabsData.value[1];
    //
    // currentTab.value = currentApiData.apiId;

  } else if (apiTabsData.value.length - 1 === currentTabIndex) {
    currentApiData.value = apiTabsData.value[currentTabIndex - 1];
    currentTab.value = currentApiData.apiId;
  } else {
    currentApiData.value = apiTabsData.value[currentTabIndex + 1];
    currentTab.value = currentApiData.apiId;
  }
  apiTabsData.value.splice(currentTabIndex, 1);
  // apiTabsData.value.splice(tabId, 1);
  console.log("删除了tab:" + tabId)
}

function clickTab(tab, event) {
  const currentTabIndex = apiTabsData.value.findIndex(dict => dict.apiId === tab.paneName);
  currentApiData.value = apiTabsData.value[currentTabIndex];
  currentTab.value = tab.paneName;
  console.log("点击了tab:" + tab.paneName + " " + "当前tab：" + currentTab.value)
}

function activeTabChange(tabName) {
  console.log("tab切换了:" + tabName + "  " + "当前tab：" + currentTab.value)
  // currentApiData = apiTabsData.value[tabName];
}

function debug() {
  loading.value.debugApi = true;
  const apiData = toRaw(currentApiData.value);
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
      currentApiData.value.requestInfo.teststeps.find(dict => dict['step_id'] === step_result_key).result = response.data[step_result_key]
    }

    // responseData.value = response.data.log
    // open.value = false;
    // getList();
  }).finally(() => {
    loading.value.debugApi = false;
  });
}

function apiTreeFilter() {
  loading.value.filter = true;
  treeRef.value.filter(treeFilterText.value);
  loading.value.filter = false;
}

</script>

<template>
  <div class="app-container" v-loading="loadingApi">
    <el-row>
      <el-button size="small" @click="getApiTree" icon="RefreshRight"></el-button>
      <el-button size="small" @click="loading.preSaveFolderDialog = true" type="primary">新增文件夹</el-button>
      <span style="flex-grow: 1"></span>
      <el-dropdown size="small" split-button type="primary" @click="loading.preSaveDialog = true"
                   v-loading="loading.saveApi" :disabled="loading.saveApi">
        保存
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="console.log('另存为用例')">另存为用例</el-dropdown-item>
            <el-dropdown-item @click="console.log('复制API')">复制</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-button size="small" @click="debug" :loading="loading.debugApi" :disabled="loading.debugApi" type="warning">
        调试
      </el-button>
      <EnvSelector v-model:selected-env="selectedEnv" size="small" :disable="loading.debugApi"></EnvSelector>
    </el-row>

    <el-container>
      <split-window left-width="250px" window-height="calc(100vh - 156px)">
        <template v-slot:left>
          <el-row>
            <!--                <el-icon><setting></setting></el-icon>-->
            <el-checkbox v-model="onlySelf" @change="getApiTree">仅自己的数据</el-checkbox>
          </el-row>
          <el-row>
            <el-col :span="24">
              <el-input v-model="treeFilterText" clearable placeholder="输入名称或者接口或者path">
                <template #suffix>
                  <el-button icon="Search"
                             type="text"
                             @click="apiTreeFilter"
                             :loading="loading.filter"
                             :disabled="loading.filter"></el-button>
                  <!--                  <el-icon @click="apiTreeFilter"><search></search></el-icon>-->
                </template>
              </el-input>
            </el-col>

          </el-row>
          <el-row>
            <el-col :span="24">
              <el-input v-model="treeFilterText" clearable placeholder="输入名称或者接口或者path">
                <template #suffix>
                  <el-button icon="Search"
                             type="text"
                             @click="apiTreeFilter"
                             :loading="loading.filter"
                             :disabled="loading.filter"></el-button>
                  <!--                  <el-icon @click="apiTreeFilter"><search></search></el-icon>-->
                </template>
              </el-input>
            </el-col>

          </el-row>
          <el-scrollbar height="calc(100% - 70px)">
            <div style="display: flex">
              <TreeView v-model:data-source="treeDataSource"
                        @node-db-click="nodeDbClick"
                        v-model:filter-text="treeFilterText"
                        v-model:tree-ref="treeRef"
              ></TreeView>
            </div>
          </el-scrollbar>

        </template>
        <template v-slot:right>
          <el-container style="display:flex;flex-direction: column;height: 100%; padding-left: 5px;">
            <el-tabs type="card"
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
            <template v-if="currentApiData">
              <div v-if="currentApiData" style="flex-grow: 1;display: flex;flex-direction: column;">
                <template v-if="currentApiData.requestInfo.teststeps[0].step_type === CaseStepTypeEnum.http">
                  <StepRequest v-model:step-detail-data="currentApiData.requestInfo.teststeps[0]"
                               edit-height="calc(100vh - 332px)"
                  ></StepRequest>
                </template>
                <template v-if="currentApiData.requestInfo.teststeps[0].step_type === CaseStepTypeEnum.websocket">
                  <StepWebsocket v-model:step-detail-data="currentApiData.requestInfo.teststeps[0]"
                                 edit-height="calc(100vh - 332px)"></StepWebsocket>
                </template>
              </div>
            </template>
            <template v-else>
              <el-text type="warning" size="large">请选择api或者新增api</el-text>
            </template>


          </el-container>

        </template>
      </split-window>
    </el-container>
    <el-dialog :title="currentApiData?.name" @close="loading.preSaveDialog = false" v-model="loading.preSaveDialog">
      <el-main>
        <el-input v-model="currentApiData.name" placeholder="请输入名称">
          <template #prepend>
            <el-text>API名称:</el-text>
          </template>
        </el-input>
      </el-main>
      <el-button type="info" @click="loading.preSaveDialog = false">取消</el-button>
      <el-button type="primary" @click="saveApiInfo" :disabled="loading.saveApi" :loading="loading.saveApi">保存
      </el-button>
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
