<script setup>
// header、extract使用
import {useI18n} from "vue-i18n";
import CommonTable from './table-config-common.vue';
import {ScopeEnum} from "@/components/hrm/enum.js";

const {t} = useI18n();
const selfData = defineModel();
const props = defineProps({
  tableTitle: {type: String, default: ""}
})
const tableCols = [
  {
    name: t('message.configTable.header.enable'),
    type: "switch",
    prop: "enable",
    width: 60
  },
  {
    name: t('message.configTable.header.scope'),
    type: "select",
    prop: "scope",
    options: [
      {label: "全局", value: ScopeEnum.global.value, disabled: false},
      {label: "项目", value: ScopeEnum.project.value, disabled: true},
      {label: "模块", value: ScopeEnum.module.value, disabled: true},
      {label: "用例", value: ScopeEnum.case.value, disabled: false},
    ],
    width: 110
  },
  {
    name: t('message.configTable.header.key'),
    prop: "key",
    width: 300
  },
  {
    name: t('message.configTable.header.value'),
    prop: "value",
    width: 300,
  }, {
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