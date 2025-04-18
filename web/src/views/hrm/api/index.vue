<script setup name="Api">
import {ElMessage} from "element-plus";
import SplitWindow from "@/components/hrm/common/split-window.vue";
import TreeView from "@/components/hrm/common/tree-view.vue";
import {addApi, apiTree, copyApiAsCase, getApi, updateApi} from "@/api/hrm/api.js";
import {allConfig} from "@/api/hrm/config.js";

import {initStepData} from "@/components/hrm/data-template.js";
import {randomString} from "@/utils/tools.js";
import {CaseStepTypeEnum, HrmDataTypeEnum, runDetailViewTypeEnum, RunTypeEnum} from "@/components/hrm/enum.js";
import StepRequest from "@/components/hrm/case/step-request.vue";
import StepWebsocket from "@/components/hrm/case/step-websocket.vue";
import {getApiFormDataByType} from "@/components/hrm/case/case-utils.js";
import RunDetail from "@/components/hrm/common/run/run-detail.vue";
import DebugComponent from "@/components/hrm/common/debug_component.vue";


const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const {hrm_data_type} = proxy.useDict("hrm_data_type");

provide("hrm_data_type", hrm_data_type);
provide('sys_normal_disable', sys_normal_disable);

const treeDataSource = ref([]);
const hrm_config_list = ref({});

const folderForm = ref({parentId: null, name: null})
const apiTabsData = ref([]);
const currentApiData = ref(apiTabsData.value[0] || null);
const currentTab = ref(0);  // 当前选中的tab，是apiId
const viewShow = ref({
  runHistoryDialog: false
});
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
});

const treeFilterText = ref("");
const treeRef = ref(null);
const currentSelectParentNode = ref();  // 当前可以使用的父节点


onMounted(() => {
  getApiTree();
  allConfig().then(response => {
    hrm_config_list.value = response.data;
  });
});

const debugFromCaseData = ref(null);

watch(() => currentApiData.value, (newData) => {
  const apiData = toRaw(newData);

  const data = apiData ? {
    request: apiData.requestInfo,
    type: apiData.type,
    name: apiData.name,
    caseId: apiData.apiId,
  } : {};
  debugFromCaseData.value = data;
});

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

function saveApiInfo(type) {

  loading.value.saveApi = true;
  let data = toRaw(currentApiData.value);
  data = structuredClone(data);

  data.type = HrmDataTypeEnum.api

  data.requestInfo.teststeps.forEach((step) => {
    step.result = null;
  });

  if (data.id && data.apiId && !data.isNew) {
    if (type === 'copy2case') {
      copyApiAsCase(data).then(res => {
        ElMessage({message: "API成功另存为CASE", type: "success"});
      }).catch(error => {
        ElMessage.error("API另存为CASE失败");
      }).finally(() => {
        loading.value.saveApi = false;
        loading.value.preSaveDialog = false;
      })
    } else {
      updateApi(data).then(res => {
        ElMessage({message: "API保存成功", type: "success"});
        apiSaveSuccess(res, data.apiId);
      }).catch(error => {
        ElMessage({message: "API保存失败", type: "success"});
      }).finally(() => {
        loading.value.saveApi = false;
        loading.value.preSaveDialog = false;
      })
    }

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
    });
  }

}

/*
* 保存成功后更新apiTabsData和treeDataSource、当前选中的tabid
* */
function apiSaveSuccess(res, oldApiId) {
  if (res && res.data && res.data.apiId) {
    currentApiData.value.apiId = res.data.apiId;
  }
  let response = res;
  if (response) {
    let treeNode = treeRef.value.getNode(oldApiId);
    treeNode.data.apiId = response.data.apiId;
    treeNode.data.name = response.data.name;
    treeNode.data.isNew = false;

    treeNode.apiId = response.data.apiId;
    treeNode.name = response.data.name;

    apiTabsData.value.forEach(apiInfo => {
      if (apiInfo.apiId === oldApiId) {
        apiInfo.apiId = response.data.apiId;
        currentTab.value = response.data.apiId;
      }
    })
  }
}

function saveFolderInfo() {
  let parentId = null;
  if (currentSelectParentNode.value) {
    parentId = currentSelectParentNode.apiId;
    parentId = treeRef.value.getNode(parentId) ? parentId : null
  }
  loading.value.preSaveFolderDialog = true;
  let data = folderForm.value;
  data.type = HrmDataTypeEnum.folder
  data.apiType = CaseStepTypeEnum.folder
  data.parentId = parentId;
  addApi(data).then(res => {
    if (!parentId) {
      treeDataSource.value.splice(0, 0, res.data);
    } else {
      let parentNode = treeRef.value.getNode(parentId);
      parentNode.data.children.splice(0, 0, res.data);
    }

    ElMessage({message: "Folder保存成功", type: "success"});
  }).finally(() => {
    loading.value.preSaveFolderDialog = false;
  })
}

function getApiTree() {
  treeRef.value.setCurrentKey(null, false);
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
      loadingApi.value = false;
    } else {
      loadingApi.value = true;

      if (node.data.isNew) {
        let emptyData = getApiFormDataByType(node.data.apiType);
        // currentApiData.value.apiId = nodeId;
        emptyData.isNew = true;
        emptyData.type = node.data.type;
        emptyData.apiType = node.data.apiType;
        emptyData.requestInfo.name = node.name;
        emptyData.parentId = node.data.parentId;
        emptyData.apiId = node.data.apiId;
        apiTabsData.value.push(emptyData);

        currentApiData.value = apiTabsData.value[apiTabsData.value.length - 1];
        currentTab.value = emptyData.apiId;

        if (apiTabsData.value[0].isEmpty) {
          apiTabsData.value.splice(0, 1);
        }

        loadingApi.value = false;
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


function delTreeNode(data) {
  const dataIndex = apiTabsData.value.findIndex(dict => dict.apiId === data.apiId)
  if (dataIndex !== -1) {
    apiTabsData.value.splice(dataIndex, 1);
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
    currentTab.value = currentApiData.value.apiId;
  } else {
    currentApiData.value = apiTabsData.value[currentTabIndex + 1];
    currentTab.value = currentApiData.value.apiId;
  }
  apiTabsData.value.splice(currentTabIndex, 1);
  // apiTabsData.value.splice(tabId, 1);
  console.log("删除了tab:" + tabId)
}

function clickTab(tab, event) {
  // console.log("点击了tab:" + tab.paneName + " " + "当前tab：" + currentTab.value)
}

function activeTabChange(tabName) {
  const currentTabIndex = apiTabsData.value.findIndex(dict => dict.apiId === tabName);
  currentApiData.value = apiTabsData.value[currentTabIndex];
  currentTab.value = tabName;
  treeRef.value.setCurrentKey(tabName);
  // console.log("tab切换了:" + tabName + "  " + "当前tab：" + currentTab.value)
}

function debug(response) {
  for (const step_result_key in response.data) {
    currentApiData.value.requestInfo.teststeps.find(dict => dict['step_id'] === step_result_key).result = response.data[step_result_key]
  }

}

function apiTreeFilter() {
  loading.value.filter = true;
  treeRef.value.filter(treeFilterText.value);
  loading.value.filter = false;
}

const handelMoveNode = (parentId, nodeId, index) => {
  updateApi({parentId: parentId, apiId: nodeId}).then(res => {
    ElMessage.success("移动节点成功");
  }).catch(err => {
  })
}

const handleEditNode = (evt, data, node) => {
  updateApi({name: data.name, apiId: data.apiId}).then(res => {
    ElMessage.success("修改成功");
  }).catch(err => {
  })
}

const handleAddNode = (type, newData, parentNodeData) => {
  if (type !== CaseStepTypeEnum.folder) {
    return;
  }
  let dataType = type === CaseStepTypeEnum.folder ? HrmDataTypeEnum.folder : HrmDataTypeEnum.api;
  addApi({type: dataType, apiType: type, name: newData.name, parentId: parentNodeData.apiId}).then(res => {
    ElMessage.success("文件夹【" + newData.name + "】新增成功");
  }).catch(err => {
  });

}

const copyAsCase = () => {
  copyApi({apiId: data.apiId}).then(res => {
    ElMessage.success("复制成功");
  }).catch(err => {
  });
}

function showRunHistory() {
  if (!currentApiData.value) {
    ElMessage.warning("请先选择一个接口");
    return;
  }
  viewShow.value.runHistoryDialog = true;
}

function handleNodeChange(nodeData, node) {
  if (!nodeData) {
    return;
  }
  if (nodeData && nodeData.type === HrmDataTypeEnum.folder) {
    return;
  }
  const currentIndex = apiTabsData.value.findIndex(dict => dict.apiId === nodeData.apiId)
  if (currentIndex === -1) {
    return;
  }
  currentTab.value = nodeData.apiId;
  activeTabChange(nodeData.apiId);

}

function showFolderDialog() {
  loading.value.preSaveFolderDialog = true;
  let currentNodeObj = treeRef.value.getCurrentNode();
  if (currentNodeObj && !currentNodeObj.isParent) {
    currentNodeObj = treeRef.value.getNode(currentNodeObj.patentId)
  }
  if (currentNodeObj) {
    currentSelectParentNode.value = currentNodeObj;
  } else {
    currentSelectParentNode.value = null;
  }

}


</script>

<template>
  <div class="app-container" v-loading="loadingApi" style="height: 100%">
    <el-row :gutter="10">
      <el-button @click="getApiTree" icon="RefreshRight"></el-button>
      <el-button @click="showFolderDialog" type="primary">新增文件夹</el-button>
      <span style="flex-grow: 1"></span>
      <el-dropdown split-button type="primary" @click="loading.preSaveDialog = true"
                   v-loading="loading.saveApi" :disabled="loading.saveApi">
        保存
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="saveApiInfo('copy2case');">另存为用例</el-dropdown-item>
            <el-dropdown-item disabled @click="console.log('复制API')">复制</el-dropdown-item>
            <el-dropdown-item @click="showRunHistory">执行历史</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <DebugComponent :run-type="RunTypeEnum.api"
                      :case-data="debugFromCaseData"
                      @debug-run="debug"
      ></DebugComponent>

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
                             type="info"
                             @click="apiTreeFilter"
                             :loading="loading.filter"
                             :disabled="loading.filter" link></el-button>
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
                        @del-node="delTreeNode"
                        @move-node="handelMoveNode"
                        @edit-node="handleEditNode"
                        @add-node="handleAddNode"
                        @current-node-change="handleNodeChange"
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
                      <span @dblclick="activeTabChange(apiData.apiId);">{{ apiData.name }}</span>
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
                               request-container-height="calc(100vh - 165px)"
                  ></StepRequest>
                </template>
                <template v-if="currentApiData.requestInfo.teststeps[0].step_type === CaseStepTypeEnum.websocket">
                  <StepWebsocket v-model:step-detail-data="currentApiData.requestInfo.teststeps[0]"
                                 step-container-height="calc(100vh - 245px)"></StepWebsocket>
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
        <el-input :model-value="currentSelectParentNode?currentSelectParentNode.name:'根目录'"
                  placeholder="请输入文件夹名称" disabled>
          <template #prepend>
            <el-text>父级目录:</el-text>
          </template>
        </el-input>
        <el-input v-model="folderForm.name" placeholder="请输入文件夹名称" style="padding-top: 5px">
          <template #prepend>
            <el-text>文件夹名称:</el-text>
          </template>
        </el-input>
      </el-main>
      <el-button type="info" @click="loading.preSaveFolderDialog = false">取消</el-button>
      <el-button type="primary" @click="saveFolderInfo" :disabled="loading.saveApi">保存</el-button>
    </el-dialog>

    <el-dialog fullscreen :title="'【' + currentApiData?.apiId + '】' + currentApiData?.name"
               v-model="viewShow.runHistoryDialog" append-to-body destroy-on-close>
      <el-container style="height: 100%">
        <!--          <el-header height="20px" border="2px" style="border-bottom-color: #97a8be;text-align: right">-->
        <!--          </el-header>-->
        <el-main style="max-height: calc(100vh - 95px);">
          <RunDetail :run-id="currentApiData.apiId" :view-type="runDetailViewTypeEnum.api"></RunDetail>
        </el-main>
      </el-container>
    </el-dialog>
  </div>

</template>

<style scoped lang="scss">

</style>
