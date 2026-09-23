<template>
  <el-dialog
    v-model="showCaseDialog"
    :title="caseDialogTitle"
    width="90%"
    destroy-on-close
    append-to-body
    :close-on-click-modal="false"
    :close-on-press-escape="false"
  >
    <el-form :model="form" label-width="90px" class="mb16">
      <el-row :gutter="16">
        <el-col :span="10">
          <el-form-item label="用例名称">
            <el-input v-model="form.caseName" />
          </el-form-item>
        </el-col>
        <el-col :span="7">
          <el-form-item label="浏览器">
            <el-select v-model="form.browserName" style="width: 100%">
              <el-option
                v-for="item in browserOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="7">
          <el-form-item label="无头模式">
            <el-switch v-model="form.headless" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="项目">
            <el-select v-model="form.projectId" clearable filterable style="width: 100%">
              <el-option
                v-for="item in projectOptions"
                :key="item.projectId"
                :label="item.projectName"
                :value="item.projectId"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="模块">
            <el-select v-model="form.moduleId" clearable filterable style="width: 100%">
              <el-option
                v-for="item in filteredCaseModules"
                :key="item.moduleId"
                :label="item.moduleName"
                :value="item.moduleId"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="起始地址">
            <el-input v-model="form.startUrl" placeholder="https://example.com" />
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="说明">
            <el-input v-model="form.notes" type="textarea" :rows="2" />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <!-- 步骤编辑（可视化表格 + 高级 JSON + 步骤详情弹窗）已下沉到公共组件 WebStepEditor，
         与门店配置版本编辑器共用同一交互与样式。 -->
    <WebStepEditor
      ref="stepEditorRef"
      :steps="form.steps"
      :serialize-steps="serializeStepsForJson"
    />

    <template #footer>
      <el-button @click="showCaseDialog = false">取消</el-button>
      <el-button type="primary" :loading="loading.save" @click="handleSave">保存 </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
  import { ref } from 'vue';
  import WebStepEditor from '@/components/hrm/case/webcase/components/WebStepEditor.vue';
  import { safeJsonStringify } from '@/components/hrm/case/webcase/utils/shared.js';

  const props = defineProps({
    context: {
      type: Object,
      required: true,
    },
  });

  const {
    showCaseDialog,
    caseDialogTitle,
    form,
    browserOptions,
    projectOptions,
    filteredCaseModules,
    loading,
    saveCase,
    prepareStepForSubmit,
  } = props.context;

  const stepEditorRef = ref(null);

  // JSON Tab 展示提交格式：与保存时的步骤结构完全一致（原行为保留）。
  function serializeStepsForJson(steps) {
    return safeJsonStringify(
      steps.map((step, index) => prepareStepForSubmit(step, index + 1)),
    );
  }

  // 保存前先把 JSON Tab 的编辑应用回步骤数组，失败时中止保存。
  function handleSave() {
    if (!stepEditorRef.value?.flush()) {
      return;
    }
    saveCase();
  }
</script>

<style scoped lang="scss">
  @import '../styles/dialogs.scss';
</style>
