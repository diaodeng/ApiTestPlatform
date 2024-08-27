<script setup>

import {listEnv} from "@/api/hrm/env.js";

const selectedEnv = defineModel("selectedEnv");
const envOptions = ref([]);

function envList() {
  listEnv().then(response => {
    envOptions.value = response.data;
  });
}
onMounted(()=>{
  envList();
})

</script>

<template>
  <el-select placeholder="选择环境" v-model="selectedEnv" style="width: 115px">
    <el-option
        v-for="option in envOptions"
        :key="option.envId"
        :label="option.envName"
        :value="option.envId">
    </el-option>
  </el-select>
</template>

<style scoped lang="scss">

</style>