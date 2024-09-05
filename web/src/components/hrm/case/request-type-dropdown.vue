<script setup>

import {CaseStepTypeEnum} from "@/components/hrm/enum.js";
import {getStepDataByType} from "@/components/hrm/case/case-utils.js";

defineEmits(["typeSelected"]);

const props = defineProps(["indexKey"]);

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
                     @click.stop="$emit('typeSelected', indexKey, CaseStepTypeEnum.http, getStepDataByType(CaseStepTypeEnum.http))">
            request
          </el-button>
        </el-dropdown-item>
        <el-dropdown-item>
          <el-button size="small"
                     type="warning"
                     @click.stop="$emit('typeSelected', indexKey, CaseStepTypeEnum.websocket, getStepDataByType(CaseStepTypeEnum.websocket))">
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