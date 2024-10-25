<script setup>
// header、extract使用
import { useI18n } from "vue-i18n";
import CommonTable from './table-config-common.vue';

const { t } = useI18n();
const selfData = defineModel("selfData");
const include = defineModel("include");
const props = defineProps({showInclude: {type: Boolean, default: false}})
const tableCols = [
  {
    name: t('message.configTable.header.enable'),
    prop: "enable",
    width: 60,
    type: 'switch'
  }, {
    name: t('message.configTable.header.key'),
    prop: "key",
    width: 150
  },
  {
    name: t('message.configTable.header.value'),
    prop: "value",
    width: 150,
  }, {
    name: t('message.configTable.header.desc'),
    prop: "desc",
    width: ""
  }]

const hrmConfigList = inject("hrm_case_config_list");

</script>

<template>
  <CommonTable :cols="tableCols" v-model="selfData">

    <template #tableHeader v-if="showInclude">
      <el-select style="flex-grow: 1;padding-right: 5px;padding-left: 5px;"
                 placeholder="请选择配置"
                 v-model="include.config.id"
                 filterable
      >
        <template #label="{ label, value }" >
          <template v-for="item in hrmConfigList">
            <template v-if="item.caseId === value">
              <el-tag round size="small" type="success" v-if="item.isSelf" >可管理</el-tag>
              <el-tag round size="small" type="info" v-if="!item.isSelf" >可使用</el-tag>
              <el-tag round size="small" type="warning" v-if="item.global" >全局</el-tag>
              <el-tag round size="small" type="primary" v-else-if="!item.global">局部</el-tag>
            </template>
          </template>
          {{ label }}
        </template>
        <el-option v-for="item in hrmConfigList"
                   :key="item.caseId"
                   :label="item.caseName"
                   :value="item.caseId"
        >
          <template #default>
            <el-tag round size="small" type="success" v-if="item.isSelf">可管理</el-tag>
            <el-tag round size="small" type="info" v-if="!item.isSelf">可使用</el-tag>
            <el-tag round size="small" type="warning" v-if="item.global">全局</el-tag>
            <el-tag round size="small" type="primary" v-else-if="!item.global">局部</el-tag>
            {{ item.caseName }}
          </template>
        </el-option>
      </el-select>
      <el-checkbox v-model="include.config.allow_extend">允许扩展</el-checkbox>
    </template>
  </CommonTable>
</template>

<style scoped lang="scss">

</style>