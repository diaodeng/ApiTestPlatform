<script setup>

import {ElMessageBox} from "element-plus";
import {addCase, getComparator, updateCase} from "@/api/hrm/case.js"
import {HrmDataTypeEnum, RunTypeEnum} from "@/components/hrm/enum.js";
import TestStep from "@/components/hrm/case/step.vue";
import CaseConfig from "@/components/hrm/case/case-config.vue";
import {listProject} from "@/api/hrm/project.js";
import {initCaseFormData} from "@/components/hrm/data-template.js";
import {allConfig} from "@/api/hrm/config.js";
import {useResizeObserver} from "@vueuse/core";
import DebugComponent from "@/components/hrm/common/debug_component.vue";


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
const openCaseEditDialog = defineModel("openCaseEditDialog");

const formData = toRef(props.formDatas);
const projectOptions = ref([]);
const activeCaseName = ref("caseConfig")
const hrm_comparator_dict = ref({});
const selectConfigList = ref([]);
const loading = ref({
  save: false,
  debug: false,
  init: false
});

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
  // getComparatorFromNetwork();
});

// watch(() => props.openCaseEditDialog, () => {
//   if (props.openCaseEditDialog === true) {
//     getConfigSelect();
//   }
// })


/** 提交按钮 */
function submitForm(closeDialog) {

  proxy.$refs["postRef"].validate(valid => {
    if (valid) {
      loading.value.save = true;
      let caseData = toRaw(formData.value);
      caseData = JSON.parse(JSON.stringify(caseData));
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
          formData.value.caseId = response.data.caseId;
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

function debugToRun(response) {

  for (const step_result_key in response.data) {
    formData.value.request.teststeps.find(dict => dict['step_id'] === step_result_key).result = response.data[step_result_key];
  }
}


/** 查询项目列表 */
async function getProjectSelect() {
  await listProject({isPage: false}).then(response => {
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

async function getComparatorFromNetwork() {
  let data = "";
  if (formData.value && formData.value.caseId) {
    data = formData.value.caseId;
  }
  await getComparator({caseId: data}).then(response => {
    hrm_comparator_dict.value = response.data;
  });
}

async function getConfigSelect() {
  if (props.dataType === HrmDataTypeEnum.case) {
    let data = {
      projectId: formData.value.projectId,
      moduleId: formData.value.moduleId,
      type: HrmDataTypeEnum.config
    }
    await allConfig(data).then(response => {
      selectConfigList.value = response.data;
    });
  }
}


onMounted(async () => {
  loading.value.init = true;
  reset();
  await getProjectSelect();
  await getConfigSelect();
  await getComparatorFromNetwork();

  watch(() => formData.value, () => {
    dataChange.value = true;
  }, {deep: true});
  dataChange.value = false;

  // nextTick(() => {
  //   dataChange.value = false;
  // });
  loading.value.init = false;
});

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
  });
}

useResizeObserver(caseMainRef, (entries) => {
  const entry = entries[0]
  const {width, height} = entry.contentRect;
  nextTick(() => {
    caseMainHeight.value = height;
  });

});

</script>

<template>
  <el-dialog fullscreen :title='title'
             v-model="openCaseEditDialog"
             :before-close="beforeCloseDialog"
             append-to-body destroy-on-close>
    <el-form ref="postRef" :model="formData" :rules="formRules" label-width="100px" style="height: 100%" v-loading="loading.init">
      <el-container style="height: 100%; overflow-y: hidden">
        <el-header height="40px" border="2px" style="border-bottom-color: #97a8be;text-align: right">
          <el-button-group>
            <div style="display: flex;flex-direction: row">
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
              <DebugComponent :case-data="formData"
                              :run-type="RunTypeEnum.case_debug"
                              @debug-run="debugToRun"
                              v-show="dataType !== HrmDataTypeEnum.config"
              ></DebugComponent>
            </div>
          </el-button-group>


        </el-header>
        <el-main style="height: calc(100vh - 112px); padding-top: 0;padding-bottom: 0" ref="caseMainRef">
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