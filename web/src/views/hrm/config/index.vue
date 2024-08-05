<template>
  <CaseView :data-type="HrmDataTypeEnum.config" :form-rules="formRules"></CaseView>
</template>

<script setup name="RunDetail">
import CaseView from '@/views/hrm/case/index.vue';
import {HrmDataTypeEnum} from '@/components/hrm/enum.js';

const formRules = {
      caseName: [{required: true, message: "配置名称不能为空", trigger: "blur"}]
    }

</script>
