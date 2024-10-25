<script setup>
import { useI18n } from "vue-i18n";
import CommonTable from './table-config-common.vue';

const { t } = useI18n();
const props = defineProps({
  tableTitle: {type: String, default: ""},
  toolFixTarget: {type: String, default: ""}
})
const selfData = defineModel();
const tableCols = [{
  name: t('message.configTable.header.check'),
  prop: "check",
  width: ""
},
  {
    name: t('message.configTable.header.comparator'),
    prop: "assert",
    type: "compaList",
    width: 110
  }, {
    name: t('message.configTable.header.type'),
    prop: "type",
    width: 115,
    type: "select"
  }, {
    name: t('message.configTable.header.expected'),
    prop: "expect",
    width: 300
  }, {
    name: t('message.configTable.header.msg'),
    prop: "msg",
    width: ""
  }]
</script>

<template>
  <CommonTable :cols="tableCols" v-model="selfData" :table-title="tableTitle" :tool-fix-target="toolFixTarget"></CommonTable>
</template>

<style scoped lang="scss">

</style>