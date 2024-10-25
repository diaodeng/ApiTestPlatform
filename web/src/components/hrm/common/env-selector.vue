<script setup>

import {allEnv} from "@/api/hrm/env.js";

const selectedEnv = defineModel("selectedEnv");
const props = defineProps({
  disable: {type: Boolean, default: false},
  selectorWidth: {default: "200px"}
});
const envOptions = ref([]);

function envList() {
  allEnv().then(response => {
    envOptions.value = response.data;
  });
}

onMounted(() => {
  envList();
})

</script>

<template>
  <el-select placeholder="选择环境" v-model="selectedEnv" :style="{width: selectorWidth}" :disabled="disable" filterable>
    <template #label="{ label, value }">
      <template v-for="item in envOptions">
        <template v-if="item.envId === value">
          <el-tag round size="small" type="success" v-if="item.isSelf">可管理</el-tag>
          <el-tag round size="small" type="info" v-if="!item.isSelf">可使用</el-tag>
        </template>
      </template>
      {{ label }}
    </template>
    <template #loading>加载中。。。</template>
    <el-option
        v-for="option in envOptions"
        :key="option.envId"
        :label="option.envName"
        :value="option.envId">
      <template #default>
        <el-tag round size="small" type="success" v-if="option.isSelf">可管理</el-tag>
        <el-tag round size="small" type="info" v-if="!option.isSelf">可使用</el-tag>
        {{ option.envName }}
      </template>
    </el-option>
  </el-select>
</template>

<style scoped lang="scss">

</style>