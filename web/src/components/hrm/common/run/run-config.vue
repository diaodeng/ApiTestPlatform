<script setup>
import EnvSelector from "@/components/hrm/common/env-selector.vue";
import {all as getAllForwardRules} from "@/api/hrm/forward";
import {all as getAllAgent} from "@/api/hrm/agent.js";
import {initRunConfig} from "@/components/hrm/data-template.js";

const configData = defineModel('configData');
const emits = defineEmits(['update']);
const form = ref(JSON.parse(JSON.stringify(initRunConfig)));

const allForwardRules = ref([]);
const allAgent = ref([]);

function getForwardRule() {
  getAllForwardRules().then(response => {
    allForwardRules.value = response.data;
  });
}

function getAgent() {
  getAllAgent().then(response => {
    allAgent.value = response.rows;
  });
}

// watch(() => form.value.runBySort, (newValue) => {
//   if (form.value.runBySort) {
//     form.value.concurrent = 1;
//   }
// });

watch(() => configData.value, (newValue) => {
  form.value = configData.value;
}, {deep: true});


watch(() => form.value, (newValue) => {
  if (form.value.runBySort) {
    form.value.concurrent = 1;
  }
  emits('update', form.value);
}, {deep: true});

onMounted(() => {
  if (configData.value) {
    form.value = configData.value;
  }
  nextTick(() => {
    getForwardRule();
    getAgent();
  });

});

const runConfigRules = ref({
  env: [{required: true, message: "运行环境不能为空", trigger: 'blur'}],
});

</script>

<template>
  <el-form :model="form" :rules="runConfigRules">

    <el-form-item label="测试环境" prop="env">
      <EnvSelector v-model:selected-env="form.env" selector-width="100%"></EnvSelector>
    </el-form-item>
    <el-form-item label="报告名称">
      <el-input v-model="form.reportName" autocomplete="off" placeholder="报告名称，默认为执行时间"/>
    </el-form-item>

    <el-form-item label="执行次数">
      <el-input-number :min="1" controls-position="right" v-model="form.repeatNum"/>
    </el-form-item>
    <el-form-item label="同步执行">
      <el-select v-model="form.isAsync" placeholder="选择本次执行方式">
        <el-option label="同步" :value="false"/>
        <el-option label="异步" :value="true"/>
      </el-select>
    </el-form-item>
    <el-form-item label="并发数量">
      <el-input-number :min="1" controls-position="right" v-model="form.concurrent"
                       placeholder="输入并发执行的用例数量" :disabled="form.runBySort"></el-input-number>
    </el-form-item>
    <el-form-item label="日志等级">
      <el-select v-model="form.logLevel" placeholder="选择日志等级">
        <el-option label="DEBUG" :value="10"/>
        <el-option label="INFO" :value="20"/>
        <el-option label="WARNING" :value="30"/>
        <el-option label="ERROR" :value="40"/>
        <el-option label="CRITICAL" :value="50"/>
      </el-select>
    </el-form-item>

    <el-form-item label="转发配置">
      <div style="display: flex;flex-direction: row;flex-grow: 1">
        <el-checkbox v-model="form.forwardConfig.forward" style="margin-right: 20px"></el-checkbox>
        <el-row style="flex-grow: 1" :gutter="10">
          <el-col :span="12">
            <el-select placeholder="请选择客户机"
                       v-model="form.forwardConfig.agentId"
                       clearable
            >
              <el-option
                  v-for="item in allAgent"
                  :key="item.agentId"
                  :label="item.agentName"
                  :value="item.agentId"
              />
            </el-select>
          </el-col>
          <el-col :span="12">
            <el-select multiple
                       placeholder="请选择转发规则"
                       v-model="form.forwardConfig.forwardRuleIds"
            >
              <el-option
                  v-for="item in allForwardRules"
                  :key="item.ruleId"
                  :label="item.ruleName"
                  :value="item.ruleId"
              />
            </el-select>
          </el-col>
        </el-row>
      </div>
    </el-form-item>

    <el-form-item label="顺序执行">
      <!--        <el-input v-model="form.push" type="checkbox"></el-input>-->
      <el-checkbox v-model="form.runBySort"></el-checkbox>
    </el-form-item>
    <el-form-item label="结果通知">
      <!--        <el-input v-model="form.push" type="checkbox"></el-input>-->
      <el-checkbox v-model="form.push"></el-checkbox>
    </el-form-item>


  </el-form>
</template>

<style scoped lang="scss">

</style>