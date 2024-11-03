<script setup>
import { useI18n } from "vue-i18n";
// variables、data、param使用
import CommonTable from './table-config-common.vue';

const { t } = useI18n();
const selfData = defineModel();
const props = defineProps({
  tableTitle:{type: String},
  toolFixTarget: {type: String, default: ""},
  toolFixOffset: {type: Number, default: 0}
});
const tableCols = [
  {
    name: t('message.configTable.header.enable'),
    prop: "enable",
    width: 60,
    type: 'switch'
  }, {
    name: t('message.configTable.header.originUrl'),
    prop: "key",
    width: 150
  }, {
    name: t('message.configTable.header.targetUrl'),
    prop: "value",
    width: ""
  }, {
    name: t('message.configTable.header.desc'),
    prop: "desc",
    width: ""
  }]

</script>

<template>
  <CommonTable :cols="tableCols"
               :table-title="tableTitle"
               :tool-fix-target="toolFixTarget"
               :tool-fix-offset="toolFixOffset"
               v-model="selfData"></CommonTable>
</template>

<style scoped lang="scss">

</style>