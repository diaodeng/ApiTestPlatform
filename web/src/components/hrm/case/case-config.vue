<script setup>

import {inject} from "vue";
import {decompressText, compressData, Json, parseHeightValue, randomString} from "@/utils/tools.js"
import TableHeaders from "@/components/hrm/table-headers.vue";
import TableHooks from "@/components/hrm/table-hooks.vue";
import TableVariables from "@/components/hrm/table-variables.vue";
import {selectModulList} from "@/api/hrm/module.js";
import {list as listConfig, allConfig} from "@/api/hrm/config.js";
import {HrmDataTypeEnum} from "@/components/hrm/enum.js";
import {getComparator, uploadParamsFileToServer, listCaseParams, delCaseParams} from "@/api/hrm/case.js";
import ParamsDalog from "@/components/hrm/common/edite-table.vue";
import {ElMessage, ElMessageBox} from "element-plus";
import {useResizeObserver} from "@vueuse/core";
import {useI18n} from "vue-i18n";

const {t} = useI18n();

const qtr_case_status = inject("qtr_case_status");

const props = defineProps({
  projectOptions: {
    type: Object,
    default: () => ([])
  },
  dataName: {
    type: String,
    default: "用例"
  },
  dataType: {
    type: Number,
    default: HrmDataTypeEnum.case
  },
  configContainerHeight: {
    default: 100
  }
})
// const selectConfigList = ref([]);
const selectConfigList = inject("hrm_case_config_list");
const formData = defineModel("formData", {required: true});

const activeTabName = ref("caseMessages");
// const projectOptions = ref([]);
const moduleOptions = ref([]);

const hrm_comparator_dict = inject("hrm_comparator_dict");

const parameterDialogShow = ref(false);
const uploadParameterDialogShow = ref(false);
const parameterInfo = ref({tableHeaders: [], tableDatas: []});

const paramsCount = ref(0);

const loading = ref({
  initParameter: false,
  save: false,
  debug: false,
  updateData: false,
  import: false,
  searchParam: false
});

const configContainerRef = ref();
const configContainerCurrentHeight = ref(0);


const handleFileChange = (event) => {
  file.value = event.target.files[0];
};
const file = ref(null);
const uploadFile = () => {
  if (file.value) {
    loading.value.import = true;
    ElMessage.success("上传中...");
    const uploadFormData = new FormData();
    uploadFormData.append('file', file.value);
    uploadFormData.append('caseId', formData.value.caseId);
    // 发送请求到后端
    uploadParamsFileToServer(uploadFormData).then(response => {
      // 处理上传成功的逻辑
      ElMessage.success("导入成功");
      getCaseParamsList();
    }).catch(error => {
      // 处理上传失败的逻辑
      ElMessage.error("导入失败");
    }).finally(() => {
      loading.value.import = false;
    });
  }
};

// 删除用例参数
const delCaseParamsCall = () => {
  loading.value.import = true;
  let data = {
    caseId: formData.value.caseId
  }
  delCaseParams(data).then(response => {
    if (response.code === 200) {
      ElMessage.success("删除成功");
      getCaseParamsList();
    }
  }).finally(() => {
    loading.value.import = false;
  });
}

// 查询用例参数列表
const getCaseParamsList = () => {
  loading.value.searchParam = true;
  let data = {
    caseId: formData.value.caseId
  }
  listCaseParams(data).then(response => {
    if (response.code === 200) {
      paramsCount.value = response.total;
      // parameterInfo.value.tableDatas = response.data;

    }
  }).finally(() => {
    loading.value.searchParam = false;
  });
}

function getModuleSelect() {
  selectModulList(formData.value).then(response => {
    moduleOptions.value = response.data;
  });
}

const getVariableTabName = computed(() => {
  return props.dataType === HrmDataTypeEnum.config ? t('message.caseDetail.tabNames.vphc') : t('message.caseDetail.tabNames.vph');
})

function getConfigSelect() {
  if (props.dataType === HrmDataTypeEnum.case) {
    let data = {
      projectId: formData.value.projectId,
      moduleId: formData.value.moduleId,
      type: HrmDataTypeEnum.config
    }
    allConfig(data).then(response => {
      selectConfigList.value = response.data;
    });
  }
}

function resetModule() {
  formData.value.moduleId = undefined;
  formData.value.request.config.include.configId = null;
  // getModuleSelect();
  let projectId = "";
  if (formData.value && formData.value.projectId) {
    projectId = formData.value.projectId;
  }

  getComparator({projectId: projectId}).then(response => {
    hrm_comparator_dict.value = response.data;
  });
}

function resetConfig() {
  formData.value.request.config.include.configId = null;
  // getConfigSelect();
}

function startParameterDialog() {
  loading.value.initParameter = true;
  let parameterData = formData.value.request.config.parameters.value;
  let parameterDataObj = parameterData ? Json.parse(decompressText(parameterData)) : {};
  parameterInfo.value.tableHeaders = parameterDataObj.tableHeaders || [];
  parameterInfo.value.tableDatas = parameterDataObj.tableDatas || [];
  parameterInfo.value.tableDatas.forEach(value => {
    if (!value.__row_key) {
      value.__row_key = randomString(10);
    }
  });
  parameterDialogShow.value = true;
}

function startUploadParameterDialog() {
  loading.value.initParameter = true;
  uploadParameterDialogShow.value = true;
}

function replacer(key, value) {
  // 如果值是 undefined，则返回空字符串，否则返回原始值
  return value === undefined ? "" : value;
}

function saveParameters(header, data) {
  let parameterData = {
    tableHeaders: parameterInfo.value.tableHeaders,
    tableDatas: parameterInfo.value.tableDatas
  }
  formData.value.request.config.parameters.value = compressData(JSON.stringify(parameterData, replacer));
  parameterDialogShow.value = false;
  loading.value.initParameter = false;

}

onMounted(() => {
  nextTick(() => {
    getModuleSelect();
    getConfigSelect();
    useResizeObserver(configContainerRef, (entries) => {
      const entry = entries[0]
      const {width, height} = entry?.contentRect;
      nextTick(() => {
        configContainerCurrentHeight.value = height;
      });
    });
  });

});

watch(()=>formData.value.projectId, ()=>{
  // resetModule();
  getModuleSelect()
});

watch(()=>formData.value.moduleId, ()=>{
  nextTick(()=>{
    // resetConfig();
    getConfigSelect();
  });
});

function beforeColseDialog(done) {
  done();
  loading.value.initParameter = false;
  return;
  ElMessageBox.confirm("退出前请保存数据", "关闭确认", {
    type: "warning",
    cancelButtonText: "返回保存",
    confirmButtonText: "继续退出"
  }).then(() => {
    done();
    loading.value.initParameter = false;
  }).catch(() => {

  });
}

const calcConfigContainerHeight = computed(() => {
  return parseHeightValue(props.configContainerHeight);

})


</script>

<template>
  <div :style="{height:calcConfigContainerHeight}" ref="configContainerRef">
    <el-tabs type="" v-model="activeTabName">
      <el-tab-pane :label="$t('message.caseDetail.tabNames.message')" name="caseMessages">
        <el-scrollbar :height="configContainerCurrentHeight - 55">
          <el-form-item :label="dataName+'名称'" prop="caseName">
            <el-input v-model="formData.caseName" placeholder="请输入用例名称" clearable/>
          </el-form-item>
          <el-form-item label="所属项目" prop="projectId">
            <el-select v-model="formData.projectId" placeholder="请选择" @change="resetModule">
              <el-option
                  v-for="option in projectOptions"
                  :key="option.projectId"
                  :label="option.projectName"
                  :value="option.projectId">
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="所属模块" prop="moduleId">
            <el-select v-model="formData.moduleId" placeholder="请选择" @change="resetConfig">
              <el-option
                  v-for="option in moduleOptions"
                  :key="option.moduleId"
                  :label="option.moduleName"
                  :value="option.moduleId">
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="可选配置" v-if="dataType === HrmDataTypeEnum.case">
            <el-select v-model="formData.request.config.include.config.id"
                       placeholder="请选择"
                       clearable
                       filterable
            >
              <template #label="{ label, value }">
                <template v-for="item in selectConfigList">
                  <template v-if="item.caseId === value">
                    <el-tag round size="small" type="success" v-if="item.isSelf">可管理</el-tag>
                    <el-tag round size="small" type="info" v-if="!item.isSelf">可使用</el-tag>
                    <el-tag round size="small" type="warning" v-if="item.global">全局</el-tag>
                    <el-tag round size="small" type="primary" v-else-if="!item.global">局部</el-tag>
                  </template>
                </template>
                {{ label }}
              </template>
              <el-option
                  v-for="option in selectConfigList"
                  :key="option.caseId"
                  :label="option.caseName"
                  :value="option.caseId">
                <template #default>
                  <el-tag round size="small" type="success" v-if="option.isSelf">可管理</el-tag>
                  <el-tag round size="small" type="info" v-if="!option.isSelf">可使用</el-tag>
                  <el-tag round size="small" type="warning" v-if="option.global">全局</el-tag>
                  <el-tag round size="small" type="primary" v-else-if="!option.global">局部</el-tag>
                  {{ option.caseName }}
                </template>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="注释" prop="notes">
            <el-input v-model="formData.notes" type="textarea" :rows="2" placeholder="注释"/>
          </el-form-item>
          <el-form-item label="用例顺序" prop="sort">
            <el-input-number v-model="formData.sort" controls-position="right" :min="0"/>
          </el-form-item>
          <el-form-item label="用例状态" prop="status">
            <el-radio-group v-model="formData.status">
              <el-radio
                  v-for="dict in qtr_case_status"
                  :key="dict.value * 1"
                  :label="dict.label"
                  :value="dict.value * 1"
              ></el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="备注" prop="remark">
            <el-input v-model="formData.remark" type="textarea" :rows="9" placeholder="请输入内容"/>
          </el-form-item>
        </el-scrollbar>

      </el-tab-pane>
      <el-tab-pane :label="$t('message.caseDetail.tabNames.headers')" name="caseHeaders">
        <el-scrollbar :height="configContainerCurrentHeight - 55">
          <TableHeaders v-model="formData.request.config.headers"></TableHeaders>
        </el-scrollbar>

      </el-tab-pane>
      <el-tab-pane :label="getVariableTabName" name="caseVph">
        <el-scrollbar :height="configContainerCurrentHeight - 55">
          <TableVariables v-model="formData.request.config.variables"
                          :tableTitle="$t('message.configTable.header.variables')"></TableVariables>

          <template v-if="dataType !== HrmDataTypeEnum.config">
            {{ $t('message.configTable.header.parameters') }}
            <el-row v-if="formData.request.config.parameters" v-loading="loading.initParameter">
              <el-select placeholder="请选择" style="width: 120px;" v-model="formData.request.config.parameters.type">
                <el-option :value="3" :key="3" label="本地表格"></el-option>
                <el-option :value="4" :key="4" label="本地数据" disabled></el-option>
                <el-option :value="1" :key="1" label="文件" disabled></el-option>
                <el-option :value="2" :key="2" label="数据库"></el-option>
              </el-select>
              <el-button @click="startParameterDialog" style="padding-left: 5px" type="primary" :disabled="formData.request.config.parameters.type !== 3">设置</el-button>
              <el-button @click="startUploadParameterDialog" style="padding-left: 5px" type="primary" :disabled="formData.request.config.parameters.type !== 2">上传CSV文件</el-button>

            </el-row>
            <el-row style="padding-bottom: 10px" v-if="formData.request.config.parameters">
              <template v-if="formData.request.config.parameters.value">
                <el-text type="success">点击“设置”修改数据</el-text>
              </template>
              <template v-else>
                <el-text type="warning">暂无数据</el-text>
              </template>
            </el-row>
          </template>

          <!--      <TableVariables v-model="formData.request.config.parameters"></TableVariables>-->

          <TableHooks v-model="formData.request.config.setup_hooks"
                      v-if="dataType !== HrmDataTypeEnum.config"
                      :table-title="$t('message.configTable.header.setup_hooks')"></TableHooks>

          <TableHooks v-model="formData.request.config.teardown_hooks"
                      v-if="dataType !== HrmDataTypeEnum.config"
                      :table-title="$t('message.configTable.header.teardown_hooks')"></TableHooks>
        </el-scrollbar>

      </el-tab-pane>
      <el-tab-pane :label="$t('message.caseDetail.tabNames.other')" name="caseThinktime">
        <el-row>
          <el-input
              v-model="formData.request.config.think_time.limit"
              style="max-width: 600px"
              placeholder="Please input"
          >
            <template #prepend>
              <el-switch v-model="formData.request.config.think_time.enable"
                         size="small"
              ></el-switch>
              {{ $t('message.other.thinktime') }}
            </template>
          </el-input>
        </el-row>
        <el-row style="margin-top: 5px">

          <el-input
              v-model="formData.request.config.time_out.limit"
              style="max-width: 600px"
              placeholder="Please input"
          >
            <template #prepend>
              <el-switch v-model="formData.request.config.time_out.enable"
                         size="small"
              ></el-switch>
              {{ $t('message.other.timeout') }}
            </template>
          </el-input>
        </el-row>
        <el-row style="margin-top: 5px">

          <el-input
              v-model="formData.request.config.retry.limit"
              style="max-width: 600px"
              placeholder="Please input"
          >
            <template #prepend>
              <el-switch v-model="formData.request.config.retry.enable"
                         size="small"
              ></el-switch>
              {{ $t('message.other.retry') }}
            </template>
          </el-input>
        </el-row>
      </el-tab-pane>
    </el-tabs>
    <el-dialog fullscreen :title="'参数化配置' + '【' +formData.caseName + '】'"
               v-model="parameterDialogShow"
               :before-close="beforeColseDialog"
               append-to-body destroy-on-close>
      <el-container style="height: 100%">
        <el-main style="max-height: calc(100vh - 95px);">
          <ParamsDalog v-model:columns-ref="parameterInfo.tableHeaders"
                       v-model:table-datas-ref="parameterInfo.tableDatas"
                       @submit="saveParameters"
          ></ParamsDalog>
        </el-main>
      </el-container>
    </el-dialog>
  </div>

  <el-dialog fullscreen :title="'上传参数化文件' + '【' +formData.caseName + '】'"
               v-model="uploadParameterDialogShow"
               :before-close="beforeColseDialog"
               append-to-body destroy-on-close>
      <el-container style="height: 100%">
        <el-main style="max-height: calc(100vh - 95px);">
          <div>
            <input type="file" @change="handleFileChange" />
            <el-button @click="uploadFile" :disabled="!file" :loading="loading.import">上传</el-button>
            <el-button @click="delCaseParamsCall" type="danger" :disabled="loading.import">删除</el-button>

            <el-text>当前参数数量：{{ paramsCount }}</el-text>
            <el-button @click="getCaseParamsList" type="primary" :disabled="loading.searchParam">查询</el-button>

          </div>
        </el-main>
      </el-container>
    </el-dialog>

</template>

<style scoped lang="scss">

</style>
