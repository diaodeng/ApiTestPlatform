<script setup>
import {ElDialog, ElMessage} from "element-plus";
import EnvSelector from "@/components/hrm/common/env-selector.vue";
import RunCofig from "@/components/hrm/common/run/run-config.vue";
import {testRun} from "@/api/hrm/run_detail.js";
import {all as getAllForwardRules} from "@/api/hrm/forward";
import {all as getAllAgent} from "@/api/hrm/agent.js";
import {RunTypeEnum} from "@/components/hrm/enum.js";


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
  logLevel: 20,
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
    form.value.ids = runIds;
    form.value.runType = props.runType;
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

function runConfigChange(runConfigData) {
  form.value = {...form.value, ...runConfigData}
}


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
    <RunCofig @update="runConfigChange" v-loading.fullscreen.lock="dialogTestLoading">
    </RunCofig>
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