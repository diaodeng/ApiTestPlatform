<script setup>
// header、extract使用
import CommonTable from './table-config-common.vue';

const selfData = defineModel("selfData");
const include = defineModel("include");
const props = defineProps({showInclude: {type: Boolean, default: false}})
const tableCols = [
  {
    name: "启用",
    prop: "enable",
    width: 60,
    type: 'switch'
  }, {
    name: "key",
    prop: "key",
    width: 300
  },
  {
    name: "value",
    prop: "value",
    width: 300,
  }, {
    name: "desc",
    prop: "desc",
    width: ""
  }]

</script>

<template>
  <CommonTable :cols="tableCols" v-model="selfData">
    <template #tableHeader v-if="showInclude">
      <el-select style="flex-grow: 1;padding-right: 5px;padding-left: 5px;"
                 placeholder="请选择配置">
        <el-option>jjj</el-option>
      </el-select>
      <el-checkbox checked>允许扩展</el-checkbox>
    </template>
  </CommonTable>
</template>

<style scoped lang="scss">

</style>