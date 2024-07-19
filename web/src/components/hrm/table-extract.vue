<script setup>
// header、extract使用
import CommonTable from './table-common.vue';

const props = defineProps(["data"])
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
  <CommonTable :cols="tableCols" :data="data" @data-change="(newData) => {props.data = newData}"></CommonTable>
</template>

<style scoped lang="scss">

</style>