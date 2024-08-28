<script setup>

import {inject} from "vue";
import TableHeaders from "@/components/hrm/table-headers.vue";
import TableHooks from "@/components/hrm/table-hooks.vue";
import TableVariables from "@/components/hrm/table-variables.vue";
import {selectModulList} from "@/api/hrm/module.js";
import {list as listConfig} from "@/api/hrm/config.js";
import {HrmDataTypeEnum} from "@/components/hrm/enum.js";
import {getComparator} from "@/api/hrm/case.js";

const sys_normal_disable = inject("sys_normal_disable");

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
  }
})
const selectConfigList = ref([]);
const formData = defineModel("formData", {required: true});

const activeTabName = ref("caseMessages");
// const projectOptions = ref([]);
const moduleOptions = ref([]);

const hrm_comparator_dict = inject("hrm_comparator_dict");


function getModuleSelect() {
  selectModulList(formData.value).then(response => {
    moduleOptions.value = response.data;
  });
}

function getConfigSelect() {
  if (props.dataType === HrmDataTypeEnum.case) {
    let data = {
      projectId: formData.value.projectId,
      moduleId: formData.value.moduleId,
      type: HrmDataTypeEnum.config
    }
    listConfig(data).then(response => {
      selectConfigList.value = response.rows;
    });
  }
}

function resetModule() {
  formData.value.moduleId = undefined;
  formData.value.request.config.include.configId = null;
  getModuleSelect();
  let projectId = "";
  if (formData.value && formData.value.projectId) {
    projectId = formData.value.projectId;
  }

  getComparator({projectId: projectId}).then(response => {
    hrm_comparator_dict.value = response.data
  })
}

function resetConfig() {
  formData.value.request.config.include.configId = null;
  getConfigSelect();
}

onMounted(() => {
  getModuleSelect();
  getConfigSelect();
})


</script>

<template>
  <el-tabs type="" v-model="activeTabName">
    <el-tab-pane label="messages" name="caseMessages">
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
        <el-select v-model="formData.request.config.include.configId" placeholder="请选择" clearable>
          <el-option
              v-for="option in selectConfigList"
              :key="option.caseId"
              :label="option.caseName"
              :value="option.caseId">
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item label="注释" prop="notes">
        <el-input v-model="formData.notes" placeholder="注释"/>
      </el-form-item>
      <el-form-item label="用例顺序" prop="sort">
        <el-input-number v-model="formData.sort" controls-position="right" :min="0"/>
      </el-form-item>
      <el-form-item label="用例状态" prop="status">
        <el-radio-group v-model="formData.status">
          <el-radio
              v-for="dict in sys_normal_disable"
              :key="dict.value"
              :label="dict.label"
              :value="dict.value"
          ></el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="备注" prop="remark">
        <el-input v-model="formData.remark" type="textarea" placeholder="请输入内容"/>
      </el-form-item>
    </el-tab-pane>
    <el-tab-pane label="headers" name="caseHeaders">
      <TableHeaders v-model="formData.request.config.headers"></TableHeaders>
    </el-tab-pane>
    <el-tab-pane label="variables/parameters/hooks" name="caseVph">
      variables
      <TableVariables v-model="formData.request.config.variables"></TableVariables>
      parameters
      <TableVariables v-model="formData.request.config.parameters"></TableVariables>
      setup_hooks
      <TableHooks v-model="formData.request.config.setup_hooks"></TableHooks>
      teardown_hooks
      <TableHooks v-model="formData.request.config.teardown_hooks"></TableHooks>
    </el-tab-pane>
    <el-tab-pane label="thinktime" name="caseThinktime">
      <div>
        <el-input
            v-model="formData.request.config.think_time.limit"
            style="max-width: 600px"
            placeholder="Please input"
        >
          <template #prepend>thinktime</template>
        </el-input>
      </div>
    </el-tab-pane>
  </el-tabs>
</template>

<style scoped lang="scss">

</style>