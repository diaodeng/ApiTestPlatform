<script setup>
// header、extract使用
import CommonTable from './table-config-common.vue';

const selfData = defineModel();
const tableCols = [
  {
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
  <CommonTable :cols="tableCols" v-model="selfData"></CommonTable>
</template>

<style scoped lang="scss">

</style>