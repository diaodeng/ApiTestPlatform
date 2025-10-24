<script setup>
import {ElDialog, ElMessage} from "element-plus";
import EnvSelector from "@/components/hrm/common/env-selector.vue";
import {testRun} from "@/api/hrm/run_detail.js";
import {all as getAllForwardRules} from "@/api/hrm/forward";
import {all as getAllAgent} from "@/api/hrm/agent.js";


const dialogVisible = defineModel("dialogVisible");
const runIds = defineModel("runIds");
const allForwardRules = ref([]);
const allAgent = ref([]);

const props = defineProps({
  runType: Number,
  // runIds: {type: Array, default: []},
  showDialog: {type: Boolean, default: false}
});

// const dialogVisible = props.showDialog;
const dialogTestLoading = ref(false);
const dialogCanClose = ref(true);
const disableCanRun = ref(false);

const form = ref({
  ids: runIds,
  runType: props.runType,
  env: null,
  reportName: null,
  isAsync: false,
  repeatNum: 1,
  concurrent: 1,
  push: false,
  forwardConfig: {
    forward: false,
    agentId: undefined,
    forwardRuleIds: undefined,
  },
  runBySort: false
});


function handleRun(env) {
  // const loading = ElLoading.service({
  //   lock: true,
  //   text: '用例执行中',
  //   background: 'rgba(0, 0, 0, 0.7)',
  // });

  try {
    disableCanRun.value = true;
    dialogCanClose.value = false;
    if (form.value.ids.length === 0) {
      ElMessage.error({
        message: "请选择要执行的数据",
        type: "error"
      });
      dialogCanClose.value = true;
      disableCanRun.value = false;
      return;
    }

    dialogTestLoading.value = true;
    testRun(form.value).then(response => {
      ElMessage.success({
        message: response.msg,
        type: "success"
      });
      dialogVisible.value = false;

    }).finally(
        () => {
          dialogTestLoading.value = false;
          dialogCanClose.value = true;
          disableCanRun.value = false;
          // loading.close();
        }
    )
    // dialogVisible.value = false;
  } catch (e) {
    console.log(e);
  } finally {
    // dialogTesting.value = false;
    // loading.close();
  }

}


function getForwardRule() {
  getAllForwardRules().then(response => {
    allForwardRules.value = response.data;
  });
}

function getAgent() {
  getAllAgent().then(response => {
    allAgent.value = response.data;
  });
}


function handleClose() {
  dialogCanClose.value = true;
  dialogVisible.value = false;
}

function beforeClose(done) {
  if (dialogCanClose) {
    done();
    dialogVisible.value = false;
  } else {
    done(false);
    dialogVisible.value = true;
  }
}

watch(()=>form.value.runBySort, (newValue)=>{
  if (form.value.runBySort){
    form.value.concurrent = 1;
  }
})

onMounted(() => {
  getForwardRule();
  getAgent();
});

</script>

<template>
  <el-dialog
      v-model="dialogVisible"
      title="测试确认"
      width="500"
      append-to-body
      @close="handleClose"
      :before-close="beforeClose"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
  >
    <el-form :model="form" v-loading.fullscreen.lock="dialogTestLoading">
      <el-form-item label="测试环境：">
        <EnvSelector v-model:selected-env="form.env" selector-width="100%"></EnvSelector>
      </el-form-item>
      <el-form-item label="报告名称：">
        <el-input v-model="form.reportName" autocomplete="off" placeholder="报告名称，默认为执行时间"/>
      </el-form-item>
      <el-form-item label="执行次数：">
        <el-input-number :min="1" controls-position="right" v-model="form.repeatNum"/>
      </el-form-item>
      <el-form-item label="同步执行：">
        <el-select v-model="form.isAsync" placeholder="选择本次执行方式">
          <el-option label="同步" :value="false"/>
          <el-option label="异步" :value="true"/>
        </el-select>
      </el-form-item>
      <el-form-item label="并发数量：">
        <el-input-number :min="1" controls-position="right" v-model="form.concurrent"
                         placeholder="输入并发执行的用例数量" :disabled="form.runBySort"></el-input-number>
      </el-form-item>

      <el-form-item label="转发配置：">
        <div style="display: flex;flex-direction: row;flex-grow: 1">
          <el-checkbox v-model="form.forwardConfig.forward" style="margin-right: 20px"></el-checkbox>
          <el-row style="flex-grow: 1" :gutter="10">
            <el-col :span="12">
              <el-select placeholder="请选择客户机"
                         v-model="form.forwardConfig.agentId"
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

      <el-form-item label="顺序执行：">
        <!--        <el-input v-model="form.push" type="checkbox"></el-input>-->
        <el-checkbox v-model="form.runBySort"></el-checkbox>
      </el-form-item>
      <el-form-item label="结果通知：">
        <!--        <el-input v-model="form.push" type="checkbox"></el-input>-->
        <el-checkbox v-model="form.push"></el-checkbox>
      </el-form-item>
    </el-form>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button
            :disabled="disableCanRun"
            type="primary"
            @click="handleRun">
          执行
        </el-button>
      </div>
    </template>
  </el-dialog>

</template>

<style scoped lang="scss">

</style>