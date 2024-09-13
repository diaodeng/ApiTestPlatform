<script setup>
import CommonTable from './table-config-common.vue';

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
    type: "compaList",
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