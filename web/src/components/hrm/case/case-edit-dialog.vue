<script setup>

import {ElMessageBox} from "element-plus";
import {getComparator} from "@/api/hrm/case.js"
import {HrmDataTypeEnum, RunTypeEnum} from "@/components/hrm/enum.js";
import TestStep from "@/components/hrm/case/step.vue";
import CaseConfig from "@/components/hrm/case/case-config.vue";
import EnvSelector from "@/components/hrm/common/env-selector.vue";
import {debugCase, addCase, updateCase, getCase} from "@/api/hrm/case.js";
import {listEnv} from "@/api/hrm/env.js";
import {listProject} from "@/api/hrm/project.js";
import {initCaseFormData} from "@/components/hrm/data-template.js";
import {list as listConfig, allConfig} from "@/api/hrm/config.js";
import {useResizeObserver} from "@vueuse/core";


const {proxy} = getCurrentInstance();
const props = defineProps({
  dataType: {type: Number, default: HrmDataTypeEnum.case},
  formRules: {
    type: Object,
    default: {}
  },
  formDatas: {type: Object, default: initCaseFormData},
  openCaseEditDialog: {type: Boolean, default: false},
  title: {type: String, default: "编辑页面"}
});


const dataChange = ref(false);
// const formData = defineModel("formData");
const openCaseEditDialog = defineModel("openCaseEditDialog");

const formData = toRef(props.formDatas);
const selectedEnv = ref("");
const projectOptions = ref([]);
const activeCaseName = ref("caseConfig")
const responseData = ref("");
const hrm_comparator_dict = ref({});
const selectConfigList = ref([]);
const loading = ref({
  save: false,
  debug: false
})

const caseMainRef = ref();
const caseMainHeight = ref(0);

const dataName = computed(() => {
  return props.dataType === HrmDataTypeEnum.case ? "用例" : "配置";
});


provide("hrm_comparator_dict", hrm_comparator_dict);
provide("hrm_case_config_list", selectConfigList);

watch(() => props.formDatas, () => {
  formData.value = props.formDatas;
  activeCaseName.value = "caseConfig"
  getComparatorFromNetwork();
})

watch(() => props.openCaseEditDialog, () => {
  if (props.openCaseEditDialog === true) {
    getConfigSelect();
  }
})


/** 提交按钮 */
function submitForm(closeDialog) {

  proxy.$refs["postRef"].validate(valid => {
    if (valid) {
      loading.value.save = true;
      const caseData = formData.value
      caseData.request.config.name = caseData.caseName;
      caseData.request.config.result = {}
      caseData.type = props.dataType;
      for (let step of caseData.request.teststeps) {
        step.result = {}
      }
      if (caseData.caseId !== undefined) {
        updateCase(caseData).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          openCaseEditDialog.value = closeDialog;
          dataChange.value = false;
          // getList();
        }).finally(() => {
          loading.value.save = false;
        });
      } else {
        addCase(caseData).then(response => {
          proxy.$modal.msgSuccess("新增成功");
          openCaseEditDialog.value = closeDialog;
          dataChange.value = false;
          // getList();
        }).finally(() => {
          loading.value.save = false;
        });
      }
    }
  });
}

function debugForm() {
  proxy.$refs["postRef"].validate(valid => {
    if (valid) {
      loading.value.debug = true;
      const caseData = formData.value;
      caseData.request.config.name = caseData.caseName;
      caseData.request.config.result = null;
      for (let i = 0; i < caseData.request.teststeps.length; i++) {
        caseData.request.teststeps[i].result = null;
      }

      const req_data = {
        "env": selectedEnv.value,
        "runType": RunTypeEnum.case_debug,
        "caseData": caseData
      }
      debugCase(req_data).then(response => {
        proxy.$modal.msgSuccess(response.msg);
        for (const step_result_key in response.data) {
          formData.value.request.teststeps.find(dict => dict['step_id'] === step_result_key).result = response.data[step_result_key]
        }

        // responseData.value = response.data.log
        // open.value = false;
        // getList();
      }).finally(() => {
        loading.value.debug = false;
      });

    }
  });
}


/** 查询项目列表 */
function getProjectSelect() {
  listProject({isPage: false}).then(response => {
    projectOptions.value = response.data;
  });
}

/** 表单重置 */
function reset() {
  activeCaseName.value = "caseConfig"
  // activeRequestName.value = "stepRequest"
  // activeRequestDetailName.value = "requestHeader"
  // activeTestStepName.value = 0
  // formData.value = JSON.parse(JSON.stringify(initCaseFormData));
  // formData.value.type = props.dataType
  proxy.resetForm("postRef");
}

function getComparatorFromNetwork() {
  let data = "";
  if (formData.value && formData.value.caseId) {
    data = formData.value.caseId;
  }
  getComparator({caseId: data}).then(response => {
    hrm_comparator_dict.value = response.data;
  });
}

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

onMounted(() => {
  reset();
  getProjectSelect();
  // getConfigSelect();

  watch(() => formData.value, () => {
    dataChange.value = true;
  }, {deep: true});

  nextTick(() => {
    dataChange.value = false;
  });

})

function beforeCloseDialog(done) {
  if (props.dataType === HrmDataTypeEnum.run_detail || !dataChange.value) {
    done();
    return;
  }

  ElMessageBox.confirm("退出前请保存数据", "确认退出", {
    type: "warning",
    cancelButtonText: "返回保存",
    confirmButtonText: "继续退出"
  }).then(() => {
    done();
  }).catch(() => {
  })
}

useResizeObserver(caseMainRef, (entries) => {
  const entry = entries[0]
  const {width, height} = entry.contentRect;
  nextTick(() => {
    caseMainHeight.value = height;
  })

})

</script>

<template>
  <el-dialog fullscreen :title='title'
             v-model="openCaseEditDialog"
             :before-close="beforeCloseDialog"
             append-to-body destroy-on-close>
    <el-form ref="postRef" :model="formData" :rules="formRules" label-width="100px" style="height: 100%">
      <el-container style="height: 100%; overflow-y: hidden">
        <el-header height="40px" border="2px" style="border-bottom-color: #97a8be;text-align: right">
          <el-button type="success"
                     @click="submitForm(true)"
                     v-hasPermi="['hrm:case:edit']"
                     v-if="dataType !== HrmDataTypeEnum.run_detail"
                     :loading="loading.save"
          >保存
          </el-button>
          <el-button type="primary"
                     @click="submitForm(false)"
                     v-hasPermi="['hrm:case:edit']"
                     v-if="dataType !== HrmDataTypeEnum.run_detail"
                     :loading="loading.save"
          >保存并返回
          </el-button>
          <el-button-group style="padding-left: 10px">
            <el-button type="warning"
                       @click="debugForm"
                       v-hasPermi="['hrm:case:debug']"
                       v-if="dataType !== HrmDataTypeEnum.config"
                       :loading="loading.debug"
            >调试
            </el-button>
            <EnvSelector v-model:selected-env="selectedEnv"
                         v-if="dataType !== HrmDataTypeEnum.config"
            ></EnvSelector>
          </el-button-group>

        </el-header>
        <el-main style="height: calc(100vh - 112px);" ref="caseMainRef">
          <CaseConfig v-model:form-data="formData"
                      :project-options="projectOptions"
                      v-if="dataType === HrmDataTypeEnum.config"
                      :data-type="dataType"
                      :data-name="dataName"
                      :config-container-height="caseMainHeight"
          ></CaseConfig>
          <el-tabs type="border-card" v-model="activeCaseName" style="height: 100%;"
                   v-else-if="dataType !== HrmDataTypeEnum.config">
            <el-tab-pane :label="$t('message.caseDetail.tabNames.configLabel')" name="caseConfig">
              <CaseConfig v-model:form-data="formData"
                          :project-options="projectOptions"
                          :data-type="dataType"
                          :config-container-height="caseMainHeight - 57"

              ></CaseConfig>
            </el-tab-pane>
            <el-tab-pane :label="$t('message.caseDetail.tabNames.stepsLabel')" name="caseSteps">
              <TestStep v-model:test-steps-data="formData.request.teststeps"
                        :steps-height="caseMainHeight - 57"
              ></TestStep>
            </el-tab-pane>
          </el-tabs>
        </el-main>
      </el-container>


    </el-form>
  </el-dialog>
</template>

<style scoped lang="scss">

</style>