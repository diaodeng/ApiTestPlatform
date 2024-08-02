<script setup>

import {inject} from "vue";
import TableHeaders from "@/components/hrm/table-headers.vue";
import TableHooks from "@/components/hrm/table-hooks.vue";
import TableVariables from "@/components/hrm/table-variables.vue";
import {selectModulList} from "@/api/hrm/module.js";

const sys_normal_disable = inject("sys_normal_disable");

const props = defineProps({
    projectOptions: {
        type: Object,
        default: () => ([])
    }
})
const formData = defineModel("formData", {required: true});

const activeTabName = ref("caseMessages");
// const projectOptions = ref([]);
const moduleOptions = ref([]);


function getModuleSelect() {
  selectModulList(formData.value).then(response => {
    moduleOptions.value = response.data;
  });
}

function resetModule() {
  formData.value.moduleId = undefined;
  getModuleSelect();
}

getModuleSelect();
</script>

<template>
  <el-tabs type="" v-model="activeTabName">
    <el-tab-pane label="messages" name="caseMessages">
      <el-form-item label="用例名称" prop="caseName">
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
        <el-select v-model="formData.moduleId" placeholder="请选择">
          <el-option
              v-for="option in moduleOptions"
              :key="option.moduleId"
              :label="option.moduleName"
              :value="option.moduleId">
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