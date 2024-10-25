<script setup>
import { useI18n } from "vue-i18n";
import CommonTable from './table-config-common.vue';

const { t } = useI18n();
const selfData = defineModel();
const tableCols = [{
      name: t('message.configTable.header.comparator'),
      prop: "key",
      width: 300
    },
      {
        name: t('message.configTable.header.check'),
        prop: "value",
        width: 100
      }, {
        name: t('message.configTable.header.desc'),
        prop: "Expected"
      }]
</script>

<template>
  <CommonTable :cols="tableCols" v-model="selfData"></CommonTable>
</template>

<style scoped lang="scss">

</style>