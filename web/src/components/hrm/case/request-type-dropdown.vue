<script setup>

import {CaseStepTypeEnum} from "@/components/hrm/enum.js";
import {initStepData, initWebsocketData} from "@/components/hrm/data-template.js";
import {ElMessageBox} from "element-plus";
import {randomString} from "@/utils/tools.js";

defineEmits(["typeSelected"]);

const props = defineProps(["indexKey"]);

function getStepData(stepType) {
  if (!stepType) {
    ElMessageBox.alert("参数错误", "错误提示", {type: "error"});
    return;
  }
  if (stepType !== CaseStepTypeEnum.http && stepType !== CaseStepTypeEnum.websocket) {
    ElMessageBox.alert("不支持的测试步骤类型", "错误提示", {type: "error"});
    return;
  }
  let tapData = initStepData;
  if (stepType === CaseStepTypeEnum.http) {
    tapData = JSON.parse(JSON.stringify(initStepData));
  } else if (stepType === CaseStepTypeEnum.websocket) {
    let stepData = JSON.parse(JSON.stringify(initStepData));
    stepData.request = initWebsocketData;
    tapData = stepData;
  } else {
    return {};
  }
  tapData.step_id = randomString(10);

  tapData.step_type = stepType;
  return tapData;
}

</script>

<template>
  <el-dropdown trigger="click">
    <template #default>
      <slot name="default">
        <el-icon :size="15" color="green">
          <CirclePlus></CirclePlus>
        </el-icon>
      </slot>
    </template>

    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item>
          <el-button size="small"
                     type="primary"
                     @click.stop="$emit('typeSelected', indexKey, CaseStepTypeEnum.http, getStepData(CaseStepTypeEnum.http))">
            request
          </el-button>
        </el-dropdown-item>
        <el-dropdown-item>
          <el-button size="small"
                     type="warning"
                     @click.stop="$emit('typeSelected', indexKey, CaseStepTypeEnum.websocket, getStepData(CaseStepTypeEnum.websocket))">
            websocket
          </el-button>
        </el-dropdown-item>
        <el-dropdown-item disabled>
          <el-button size="small" type="info" disabled>webUI</el-button>
        </el-dropdown-item>
        <el-dropdown-item disabled>
          <el-button size="small" type="info" disabled>import API</el-button>
        </el-dropdown-item>
        <el-dropdown-item disabled>
          <el-button size="small" type="info" disabled>import CASE</el-button>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<style scoped lang="scss">

</style>