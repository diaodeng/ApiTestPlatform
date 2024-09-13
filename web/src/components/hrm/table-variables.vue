<script setup>
// variables、data、param使用
import CommonTable from './table-config-common.vue';

const selfData = defineModel();
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
  }, {
    name: "type",
    prop: "type",
    width: 115,
    type: 'select'
  }, {
    name: "value",
    prop: "value",
    width: ""
  }, {
    name: "desc",
    prop: "desc",
    width: ""
  }]

</script>

<template>
  <CommonTable :cols="tableCols" v-model="selfData"></CommonTable>
</template>

<style scoped lang="scss">

</style>