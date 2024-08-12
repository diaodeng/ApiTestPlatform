<script setup>
import { inject } from "vue";
import DictSelect from '../select/dict_select.vue'
const props = defineProps(["placeholder", "options"])
const value = defineModel()

const {proxy} = getCurrentInstance();
// const {hrm_data_type} = proxy.useDict("hrm_data_type");
// const hrm_data_type = inject("hrm_data_type");

</script>

<template>
  <DictSelect :options-dict="options" v-model="value" :placeholder="placeholder"></DictSelect>
</template>

<style scoped lang="scss">

</style>