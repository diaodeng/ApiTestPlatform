<script setup>

import {HrmDataTypeEnum, RunTypeEnum} from "@/components/hrm/enum.js";
import TestStep from "@/components/hrm/case/step.vue";
import CaseConfig from "@/components/hrm/case/case-config.vue";
import {debugCase, addCase, updateCase, getCase} from "@/api/hrm/case.js";
import {listEnv} from "@/api/hrm/env.js";
import {listProject} from "@/api/hrm/project.js";
import {initCaseFormData} from "@/components/hrm/data-template.js";


const {proxy} = getCurrentInstance();
const props = defineProps({
  dataType: {type: Number, default: HrmDataTypeEnum.case},
  formRules: {
    type: Object,
    default: {}
  },
  formDatas:{type: Object, default: initCaseFormData},
  openCaseEditDialog: {type: Boolean, default: false},
  title: {type: String, default: "编辑页面"}
});

// const formData = defineModel("formData");
const openCaseEditDialog = defineModel("openCaseEditDialog");

const formData = toRef(props.formDatas);
const selectedEnv = ref("");
const envOptions = ref([]);
const projectOptions = ref([]);
const activeCaseName = ref("caseConfig")
const responseData = ref("");

const dataName = computed(() => {
  return props.dataType === HrmDataTypeEnum.case ? "用例" : "配置";
});

watch(() => props.formDatas, () => {
  formData.value = props.formDatas;
  activeCaseName.value = "caseConfig"
})

/** 提交按钮 */
function submitForm() {
  proxy.$refs["postRef"].validate(valid => {
    if (valid) {
      const caseData = formData.value
      caseData.request.config.name = caseData.caseName;
      if (caseData.caseId !== undefined) {
        updateCase(caseData).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          openCaseEditDialog.value = false;
          // getList();
        });
      } else {
        addCase(caseData).then(response => {
          proxy.$modal.msgSuccess("新增成功");
          openCaseEditDialog.value = false;
          // getList();
        });
      }
    }
  });
}

function debugForm() {
  proxy.$refs["postRef"].validate(valid => {
    if (valid) {
      const caseData = formData.value;
      caseData.request.config.name = caseData.caseName;
      const req_data = {
        "env": selectedEnv.value,
        "runType": RunTypeEnum.case_debug,
        "caseData": caseData
      }
      debugCase(req_data).then(response => {
        proxy.$modal.msgSuccess(response.msg);
        responseData.value = response.data.log
        // open.value = false;
        // getList();
      });

    }
  });
}

function envList() {
  listEnv().then(response => {
    envOptions.value = response.data;
  });
}

/** 查询项目列表 */
function getProjectSelect() {
  listProject(null).then(response => {
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

reset();
getProjectSelect();
envList();
</script>

<template>
  <el-dialog fullscreen :title='title'
             v-model="openCaseEditDialog" append-to-body destroy-on-close>
    <el-form ref="postRef" :model="formData" :rules="formRules" label-width="100px" style="height: 100%">
      <el-container style="height: 100%">
        <el-header height="20px" border="2px" style="border-bottom-color: #97a8be;text-align: right">
          <el-button-group>
            <el-button type="primary" @click="submitForm" v-hasPermi="['hrm:case:edit']">保存</el-button>
            <el-button type="primary" @click="debugForm" v-hasPermi="['hrm:case:debug']"
                       v-if="dataType === HrmDataTypeEnum.case">调试
            </el-button>
            <el-select placeholder="Select" v-model="selectedEnv" style="width: 115px"
                       v-if="dataType === HrmDataTypeEnum.case">
              <el-option
                  v-for="option in envOptions"
                  :key="option.envId"
                  :label="option.envName"
                  :value="option.envId">
              </el-option>
            </el-select>
          </el-button-group>

        </el-header>
        <el-main style="max-height: calc(100vh - 95px);">
          <CaseConfig v-model:form-data="formData" :project-options="projectOptions"
                      v-if="dataType === HrmDataTypeEnum.config"
                      :data-type="dataType" :data-name="dataName"></CaseConfig>
          <el-tabs type="border-card" v-model="activeCaseName" style="height: 100%;"
                   v-else-if="dataType === HrmDataTypeEnum.case">
            <el-tab-pane label="config" name="caseConfig">
              <CaseConfig v-model:form-data="formData" :project-options="projectOptions"
                          :data-type="dataType"></CaseConfig>
            </el-tab-pane>
            <el-tab-pane label="teststeps" name="caseSteps">
              <el-container>
                <el-main>
                  <TestStep v-model:test-steps-data="formData.request.teststeps"
                            v-model:response-data="responseData"></TestStep>
                </el-main>
              </el-container>

            </el-tab-pane>
          </el-tabs>
        </el-main>
      </el-container>


    </el-form>
  </el-dialog>
</template>

<style scoped lang="scss">

</style>