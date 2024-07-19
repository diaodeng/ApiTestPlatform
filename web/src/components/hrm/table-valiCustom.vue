<script setup>
import CommonTable from './table-common.vue';

const props = defineProps(["data"])
const tableCols = [{
      name: "Comparator",
      prop: "key",
      width: 300
    },
      {
        name: "Check",
        prop: "value",
        width: 100
      }, {
        name: "Expected",
        prop: "desc"
      }]
</script>

<template>
  <CommonTable :cols="tableCols" :data="data"></CommonTable>
</template>

<style scoped lang="scss">

</style>