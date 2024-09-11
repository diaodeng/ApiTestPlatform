<script setup>

import {inject} from "vue";
import {decompressText, compressData, Json} from "@/utils/tools.js"
import TableHeaders from "@/components/hrm/table-headers.vue";
import TableHooks from "@/components/hrm/table-hooks.vue";
import TableVariables from "@/components/hrm/table-variables.vue";
import {selectModulList} from "@/api/hrm/module.js";
import {list as listConfig} from "@/api/hrm/config.js";
import {HrmDataTypeEnum} from "@/components/hrm/enum.js";
import {getComparator} from "@/api/hrm/case.js";
import ParamsDalog from "@/components/hrm/common/edite-table.vue";

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

const parameterDialogShow = ref(false);
const parameterInfo = ref({tableHeaders: [], tableDatas: []});


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

function startParameterDialog() {
  let parameterData = formData.value.request.config.parameters.value;
  let parameterDataObj = parameterData?Json.parse(decompressText(parameterData)):{};
  parameterInfo.value.tableHeaders = parameterDataObj.tableHeaders || [];
  parameterInfo.value.tableDatas = parameterDataObj.tableDatas || [];
  parameterDialogShow.value = true;
}

function saveParameters(header, data) {
  let parameterData = {
    tableHeaders: parameterInfo.value.tableHeaders,
    tableDatas: parameterInfo.value.tableDatas
  }
  formData.value.request.config.parameters.value = compressData(JSON.stringify(parameterData));
  parameterDialogShow.value = false;

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
        <el-select v-model="formData.request.config.include.config.id" placeholder="请选择" clearable>
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
      <el-row>
        <el-select placeholder="请选择" style="width: 120px;" v-model="formData.request.config.parameters.type">
          <el-option :value="3" :key="3" label="本地表格"></el-option>
          <el-option :value="4" :key="4" label="本地数据" disabled></el-option>
          <el-option :value="1" :key="1" label="文件" disabled></el-option>
          <el-option :value="2" :key="2" label="数据库" disabled></el-option>
        </el-select>
        <el-button @click="startParameterDialog" style="padding-left: 5px">设置</el-button>
      </el-row>
      <el-row style="padding-bottom: 10px">
        <template v-if="formData.request.config.parameters">
          <el-text>点击设置数据</el-text>
        </template>
        <template v-else>
          <el-text>暂无数据</el-text>
        </template>
      </el-row>
      <!--      <TableVariables v-model="formData.request.config.parameters"></TableVariables>-->
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
  <el-dialog fullscreen :title="'参数化配置' + '【' +formData.caseName + '】'" v-model="parameterDialogShow" append-to-body destroy-on-close>
    <el-container style="height: 100%">
      <el-main style="max-height: calc(100vh - 95px);">
        <ParamsDalog v-model:columns-ref="parameterInfo.tableHeaders"
                     v-model:table-datas-ref="parameterInfo.tableDatas"
                     @submit="saveParameters"
        ></ParamsDalog>
      </el-main>
    </el-container>
  </el-dialog>
</template>

<style scoped lang="scss">

</style>