<script setup>
import CommonTable from './table-common.vue';

const props = defineProps(["data"])
const selfData = defineModel();
const tableCols = [{
  name: "check",
  prop: "check",
  width: 300
},
  {
    name: "Comparator",
    prop: "assert",
    width: 100
  }, {
    name: "Type",
    prop: "type",
    width: 115,
    type: "select"
  }, {
    name: "Expected",
    prop: "expect",
    width: ""
  }, {
    name: "msg",
    prop: "msg",
    width: ""
  }]
</script>

<template>
  <CommonTable :cols="tableCols" v-model="selfData"></CommonTable>
</template>

<style scoped lang="scss">

</style>