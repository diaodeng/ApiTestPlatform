<template>
  <el-dialog fullscreen :title='title'
             v-model="openSuiteDetailDialog" append-to-body destroy-on-close>
<!--    <el-form ref="postRef" :model="formData" :rules="formRules" label-width="100px" style="height: 100%">-->
<!--      <el-container style="height: 100%; overflow-y: hidden">-->
<!--        <el-header height="20px" border="2px" style="border-bottom-color: #97a8be;text-align: right">-->
<!--          <el-button-group>-->
<!--            <el-button type="primary" @click="submitForm" v-hasPermi="['hrm:case:edit']"-->
<!--                       v-if="dataType !== HrmDataTypeEnum.run_detail"-->
<!--            >保存-->
<!--            </el-button>-->
<!--            <el-button type="primary" @click="debugForm" v-hasPermi="['hrm:case:debug']"-->
<!--                       v-if="dataType !== HrmDataTypeEnum.config">调试-->
<!--            </el-button>-->
<!--            <EnvSelector v-model:selected-env="selectedEnv"></EnvSelector>-->
<!--          </el-button-group>-->

<!--        </el-header>-->
<!--        <el-main style="max-height: calc(100vh - 95px);">-->
<!--          <CaseConfig v-model:form-data="formData" :project-options="projectOptions"-->
<!--                      v-if="dataType === HrmDataTypeEnum.config"-->
<!--                      :data-type="dataType" :data-name="dataName"></CaseConfig>-->
<!--          <el-tabs type="border-card" v-model="activeCaseName" style="height: 100%;"-->
<!--                   v-else-if="dataType !== HrmDataTypeEnum.config">-->
<!--            <el-tab-pane label="config" name="caseConfig">-->
<!--              <CaseConfig v-model:form-data="formData" :project-options="projectOptions"-->
<!--                          :data-type="dataType"></CaseConfig>-->
<!--            </el-tab-pane>-->
<!--            <el-tab-pane label="teststeps" name="caseSteps">-->
<!--              <el-container style="max-height: calc(100vh - 207px)">-->
<!--                <el-main>-->
<!--                  <TestStep v-model:test-steps-data="formData.request.teststeps"></TestStep>-->
<!--                </el-main>-->
<!--              </el-container>-->

<!--            </el-tab-pane>-->
<!--          </el-tabs>-->
<!--        </el-main>-->
<!--      </el-container>-->


<!--    </el-form>-->
  </el-dialog>
</template>

<!--<script setup>-->
<!--import {HrmDataTypeEnum} from "@/components/hrm/enum.js";-->
<!--import {initCaseFormData} from "@/components/hrm/data-template.js";-->
<!--import EnvSelector from "@/components/hrm/common/env-selector.vue";-->
<!--import CaseConfig from "@/components/hrm/case/case-config.vue";-->
<!--import TestStep from "@/components/hrm/case/step.vue";-->

<!--const props = defineProps({-->
<!--  dataType: {type: Number, default: HrmDataTypeEnum.case},-->
<!--  formRules: {-->
<!--    type: Object,-->
<!--    default: {}-->
<!--  },-->
<!--  formDatas: {type: Object, default: initCaseFormData},-->
<!--  openCaseEditDialog: {type: Boolean, default: false},-->
<!--  title: {type: String, default: "编辑页面"}-->
<!--});-->


<!--const openSuiteDetailDialog = defineModel("openSuiteDetailDialog");-->


<!--/** 提交按钮 */-->
<!--function submitForm() {-->
<!--  proxy.$refs["postRef"].validate(valid => {-->
<!--    if (valid) {-->
<!--      const caseData = formData.value-->
<!--      caseData.request.config.name = caseData.caseName;-->
<!--      caseData.request.config.result = {}-->
<!--      for (let step of caseData.request.teststeps) {-->
<!--        step.result = {}-->
<!--      }-->

<!--      if (caseData.caseId !== undefined) {-->
<!--        updateCase(caseData).then(response => {-->
<!--          proxy.$modal.msgSuccess("修改成功");-->
<!--          openCaseEditDialog.value = false;-->
<!--          // getList();-->
<!--        });-->
<!--      } else {-->
<!--        addCase(caseData).then(response => {-->
<!--          proxy.$modal.msgSuccess("新增成功");-->
<!--          openCaseEditDialog.value = false;-->
<!--          // getList();-->
<!--        });-->
<!--      }-->
<!--    }-->
<!--  });-->
<!--}-->


<!--</script>-->

<style scoped lang="scss">

</style>
