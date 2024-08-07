<script setup>
import {ElDialog, ElLoading, ElMessage, ElMessageBox} from "element-plus";
import {testRun} from "@/api/hrm/run_detail.js";
import {listEnv} from "@/api/hrm/env";
import {HrmDataTypeEnum} from "@/components/hrm/enum.js";


const dialogVisible = defineModel("dialogVisible");
const runIds = defineModel("runIds");

const props = defineProps({
  runType: {type: Number, default: HrmDataTypeEnum.case},
  // runIds: {type: Array, default: []},
  showDialog: {type: Boolean, default: false}
})

// const dialogVisible = props.showDialog;
const dialogTestLoading = ref(false);
const dialogCanClose = ref(true);
const envList = ref([]);
const disableCanRun = ref(false);

const form = ref({
  ids: runIds,
  runType: props.runType,
  env: null,
  reportName: null,
  isAsync: "1",
  repeatNum: 1
})


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
      console.log(response);
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

function envListLoad() {
  listEnv().then(response => {
    envList.value = response.data;
  });
}

envListLoad();

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
        <el-select v-model="form.env" placeholder="请选择测试环境">
          <el-option
              v-for="option in envList"
              :key="option.envId"
              :label="option.envName"
              :value="option.envId">
          </el-option>
        </el-select>

      </el-form-item>
      <el-form-item label="报告名称：">
        <el-input v-model="form.reportName" autocomplete="off" placeholder="报告名称，默认为执行时间"/>
      </el-form-item>
      <el-form-item label="执行次数：">
        <el-input-number :min="1" controls-position="right" v-model="form.repeatNum"/>
      </el-form-item>
      <el-form-item label="同步执行：">
        <el-select v-model="form.isAsync" placeholder="Please select a zone">
          <el-option label="同步" value="1"/>
          <el-option label="异步" value="2"/>
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button
            :disabled="canRun"
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