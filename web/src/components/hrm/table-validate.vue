<script setup>
import CommonTable from './table-common.vue';

const props = defineProps(["data"])
const tableCols = [{
  name: "check",
  prop: "key",
  width: 300
},
  {
    name: "Comparator",
    prop: "value",
    width: 100
  }, {
    name: "Type",
    prop: "desc",
    width: 115,
    type: "select"
  }, {
    name: "Expected",
    prop: "desc",
    width: ""
  }]
</script>

<template>
  <CommonTable :cols="tableCols" :data="data"></CommonTable>
</template>

<style scoped lang="scss">

</style>