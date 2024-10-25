<script setup>
// variables、data、param使用
import { useI18n } from "vue-i18n";
import CommonTable from './table-config-common.vue';

const { t } = useI18n();
const selfData = defineModel();
const props = defineProps({
  tableTitle: {type: String, default: ""},
  toolFixTarget: {type: String, default: ""}
})
const tableCols = [{
  name: t('message.configTable.header.key'),
  prop: "key",
  width: 300
},{
    name: t('message.configTable.header.desc'),
    prop: "desc",
    width: ""
  }]

</script>

<template>
  <CommonTable :cols="tableCols" v-model="selfData" :table-title="tableTitle"></CommonTable>
</template>

<style scoped lang="scss">

</style>