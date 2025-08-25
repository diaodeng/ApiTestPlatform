<script setup>
import {useI18n} from "vue-i18n";
import CommonTable from './table-config-common.vue';
import {AssertOriginalEnum} from "@/components/hrm/enum.js";

const {t} = useI18n();
const props = defineProps({
  tableTitle: {type: String, default: ""},
  toolFixTarget: {type: String, default: ""}
})
const selfData = defineModel();
const tableCols = [
  {
    name: t('message.configTable.header.enable'),
    type: "switch",
    prop: "enable",
    width: 60
  },
  {
    name: t('message.configTable.header.sourceWay'),
    prop: "sourceWay",
    type: "select",
    width: "120px",
    options: Object.values(AssertOriginalEnum)
  },
  {
    name: t('message.configTable.header.check'),
    prop: "check",
    width: ""
  },
  {
    name: t('message.configTable.header.comparator'),
    prop: "assert",
    type: "compaList",
    width: 230
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
  <CommonTable :cols="tableCols" v-model="selfData" :table-title="tableTitle"
               :tool-fix-target="toolFixTarget"></CommonTable>
</template>

<style scoped lang="scss">

</style>