<template>
  <div class="web-step-editor">
    <el-tabs v-model="activeTab" class="case-editor-tabs">
      <el-tab-pane label="可视化步骤" name="visual">
        <div class="step-table-toolbar">
          <div class="panel-title">测试步骤</div>
          <div class="step-table-toolbar-actions">
            <el-button type="primary" icon="Plus" @click="addStep()">新增步骤 </el-button>
          </div>
        </div>
        <el-table
          :data="steps"
          border
          class="step-edit-table"
          :max-height="tableMaxHeight || undefined"
          empty-text="暂无步骤，可手动新增或通过录制生成"
          :row-class-name="getStepRowClassName"
          @row-click="handleStepRowClick"
        >
          <el-table-column label="序号" width="100" fixed="left">
            <template #default="scope">
              <div class="step-order-cell">
                <span>#{{ scope.$index + 1 }}</span>
                <el-switch
                  v-model="scope.row.enabled"
                  size="small"
                  inline-prompt
                  active-text="启"
                  inactive-text="停"
                  @click.stop
                />
              </div>
            </template>
          </el-table-column>
          <el-table-column label="动作" width="170">
            <template #default="scope">
              <div
                class="step-edit-cell"
                @click.stop="startStepCellEditing(scope.$index, 'actionType')"
              >
                <el-select
                  v-if="isStepCellEditing(scope.$index, 'actionType')"
                  v-model="scope.row.actionType"
                  filterable
                  style="width: 100%"
                  @click.stop
                  @change="
                    handleStepActionTypeChange(scope.row);
                    finishStepCellEditing();
                  "
                  @visible-change="
                    (visible) => {
                      if (!visible) finishStepCellEditing();
                    }
                  "
                >
                  <el-option
                    v-for="item in actionOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
                <span v-else class="step-cell-text">
                  {{ getActionLabel(scope.row.actionType) }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="步骤名称" min-width="220" show-overflow-tooltip>
            <template #default="scope">
              <div
                class="step-edit-cell"
                @click.stop="startStepCellEditing(scope.$index, 'stepName')"
              >
                <el-input
                  v-if="isStepCellEditing(scope.$index, 'stepName')"
                  v-model="scope.row.stepName"
                  @click.stop
                  @blur="finishStepCellEditing"
                  placeholder="请输入步骤名称"
                />
                <span v-else class="step-cell-text">
                  {{ scope.row.stepName || '-' }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="定位信息" min-width="320" show-overflow-tooltip>
            <template #default="scope">
              <div
                class="step-edit-cell"
                @click.stop="startStepCellEditing(scope.$index, 'target')"
              >
                <template v-if="isStepCellEditing(scope.$index, 'target')">
                  <template
                    v-if="stepNeedsTarget(scope.row.actionType) && getPrimaryLocator(scope.row)"
                  >
                    <div class="step-inline-target" @click.stop>
                      <el-select
                        :model-value="getPrimaryLocator(scope.row)?.locatorType"
                        style="width: 110px"
                        @update:model-value="updatePrimaryLocatorType(scope.row, $event)"
                      >
                        <el-option
                          v-for="item in locatorTypeOptions"
                          :key="item.value"
                          :label="item.label"
                          :value="item.value"
                        />
                      </el-select>
                      <template v-if="getPrimaryLocator(scope.row)?.locatorType === 'role'">
                        <el-input
                          :model-value="getPrimaryLocator(scope.row)?.locatorValue?.role || ''"
                          placeholder="角色"
                          @update:model-value="updatePrimaryLocatorValue(scope.row, 'role', $event)"
                        />
                        <el-input
                          :model-value="getPrimaryLocator(scope.row)?.locatorValue?.name || ''"
                          placeholder="名称"
                          @update:model-value="updatePrimaryLocatorValue(scope.row, 'name', $event)"
                        />
                      </template>
                      <el-input
                        v-else-if="
                          ['label', 'placeholder', 'text'].includes(
                            getPrimaryLocator(scope.row)?.locatorType
                          )
                        "
                        :model-value="getPrimaryLocator(scope.row)?.locatorValue?.text || ''"
                        placeholder="定位文本"
                        @update:model-value="updatePrimaryLocatorValue(scope.row, 'text', $event)"
                      />
                      <el-input
                        v-else-if="getPrimaryLocator(scope.row)?.locatorType === 'test_id'"
                        :model-value="getPrimaryLocator(scope.row)?.locatorValue?.testId || ''"
                        placeholder="Test ID"
                        @update:model-value="updatePrimaryLocatorValue(scope.row, 'testId', $event)"
                      />
                      <el-input
                        v-else-if="getPrimaryLocator(scope.row)?.locatorType === 'id'"
                        :model-value="getPrimaryLocator(scope.row)?.locatorValue?.id || ''"
                        placeholder="元素 id"
                        @update:model-value="updatePrimaryLocatorValue(scope.row, 'id', $event)"
                      />
                      <el-input
                        v-else-if="getPrimaryLocator(scope.row)?.locatorType === 'name'"
                        :model-value="getPrimaryLocator(scope.row)?.locatorValue?.name || ''"
                        placeholder="元素 name"
                        @update:model-value="updatePrimaryLocatorValue(scope.row, 'name', $event)"
                      />
                      <el-input
                        v-else
                        :model-value="getPrimaryLocator(scope.row)?.locatorValue?.selector || ''"
                        :placeholder="
                          getPrimaryLocator(scope.row)?.locatorType === 'xpath'
                            ? '//*[@id=&quot;login&quot;]'
                            : '.login-button'
                        "
                        @update:model-value="updatePrimaryLocatorValue(scope.row, 'selector', $event)"
                      />
                    </div>
                  </template>
                  <span v-else class="step-cell-placeholder">当前动作无需定位器</span>
                </template>
                <span v-else class="step-cell-text">
                  {{ describeStepTarget(scope.row) }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="输入/参数" min-width="260" show-overflow-tooltip>
            <template #default="scope">
              <div
                class="step-edit-cell"
                @click.stop="startStepCellEditing(scope.$index, 'params')"
              >
                <template v-if="isStepCellEditing(scope.$index, 'params')">
                  <template v-if="scope.row.actionType === 'goto'">
                    <el-input
                      v-model="scope.row.params.url"
                      @click.stop
                      @blur="finishStepCellEditing"
                      placeholder="https://example.com/path"
                    />
                  </template>
                  <template v-else-if="scope.row.actionType === 'set_window_size'">
                    <el-row :gutter="8" style="width: 100%" @click.stop>
                      <el-col :span="12">
                        <el-input-number
                          v-model="scope.row.params.width"
                          :min="1"
                          :step="100"
                          controls-position="right"
                          style="width: 100%"
                          placeholder="宽度"
                        />
                      </el-col>
                      <el-col :span="12">
                        <el-input-number
                          v-model="scope.row.params.height"
                          :min="1"
                          :step="100"
                          controls-position="right"
                          style="width: 100%"
                          placeholder="高度"
                        />
                      </el-col>
                    </el-row>
                  </template>
                  <template v-else-if="scope.row.actionType === 'fill'">
                    <el-input
                      v-model="scope.row.params.value"
                      @click.stop
                      @blur="finishStepCellEditing"
                      placeholder="请输入内容"
                    />
                  </template>
                  <template v-else-if="scope.row.actionType === 'upload_file'">
                    <el-input
                      v-model="scope.row.params.fileKey"
                      @click.stop
                      @blur="finishStepCellEditing"
                      placeholder="资源键，如 price_tag"
                    />
                  </template>
                  <template v-else-if="scope.row.actionType === 'press'">
                    <el-select
                      v-model="scope.row.params.key"
                      filterable
                      allow-create
                      default-first-option
                      style="width: 100%"
                      placeholder="选择或输入按键"
                      @click.stop
                      @visible-change="
                        (visible) => {
                          if (!visible) finishStepCellEditing();
                        }
                      "
                    >
                      <el-option
                        v-for="item in keyboardKeyOptions"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </template>
                  <template v-else-if="scope.row.actionType === 'select_option'">
                    <el-select
                      v-model="scope.row.params.values"
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      collapse-tags
                      collapse-tags-tooltip
                      style="width: 100%"
                      placeholder="输入或选择选项值"
                      @click.stop
                    />
                  </template>
                  <template v-else-if="['sleep', 'wait'].includes(scope.row.actionType)">
                    <el-input-number
                      v-model="scope.row.params.waitMs"
                      :min="0"
                      :step="100"
                      controls-position="right"
                      style="width: 100%"
                    />
                  </template>
                  <template
                    v-else-if="
                      ['assert_page_contains', 'assert_page_not_contains'].includes(
                        scope.row.actionType
                      )
                    "
                  >
                    <el-input
                      v-model="scope.row.params.text"
                      @click.stop
                      @blur="finishStepCellEditing"
                      placeholder="请输入断言文本"
                    />
                  </template>
                  <template v-else-if="scope.row.actionType === 'assert_title_contains'">
                    <el-input
                      v-model="scope.row.params.title"
                      @click.stop
                      @blur="finishStepCellEditing"
                      placeholder="请输入页面标题关键字"
                    />
                  </template>
                  <template v-else-if="scope.row.actionType === 'assert_url_contains'">
                    <el-input
                      v-model="scope.row.params.urlPart"
                      @click.stop
                      @blur="finishStepCellEditing"
                      placeholder="请输入URL关键字"
                    />
                  </template>
                  <template
                    v-else-if="
                      ['assert_text_equals', 'assert_text_contains'].includes(scope.row.actionType)
                    "
                  >
                    <el-input
                      v-model="scope.row.params.expected"
                      @click.stop
                      @blur="finishStepCellEditing"
                      placeholder="请输入元素文本期望值"
                    />
                  </template>
                  <span v-else class="step-cell-placeholder">当前动作无额外参数</span>
                </template>
                <span v-else class="step-cell-text">
                  {{ summarizeStepParams(scope.row) }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column v-if="hasEvidenceStep" label="证据" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <template v-if="row.actionType === 'capture_screenshot'">
                <el-tag size="small" type="info">{{ row.params?.evidenceType || 'checkpoint_screenshot' }}</el-tag>
                <el-tag v-if="row.params?.required" size="small" type="warning" class="ml4">必需</el-tag>
                <span v-if="row.params?.evidenceKey" class="step-cell-text">{{ row.params.evidenceKey }}</span>
              </template>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="230" fixed="right">
            <template #default="scope">
              <div class="step-op-buttons">
                <el-button
                  link
                  type="primary"
                  icon="Plus"
                  title="前插"
                  @click.stop="insertStep(scope.$index)"
                />
                <el-button
                  link
                  icon="Top"
                  title="上移"
                  :disabled="scope.$index === 0"
                  @click.stop="moveStep(scope.$index, -1)"
                />
                <el-button
                  link
                  icon="Bottom"
                  title="下移"
                  :disabled="scope.$index === steps.length - 1"
                  @click.stop="moveStep(scope.$index, 1)"
                />
                <el-button
                  link
                  type="primary"
                  icon="EditPen"
                  title="编辑"
                  @click.stop="openStepDetailByIndex(scope.$index)"
                />
                <el-button
                  link
                  type="danger"
                  icon="Delete"
                  title="删除"
                  @click.stop="removeStep(scope.$index)"
                />
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="高级 JSON" name="json">
        <div class="json-toolbar">
          <el-button type="primary" icon="Check" @click="handleApplyJson"
            >应用 JSON 到可视化
          </el-button>
          <el-button icon="RefreshRight" @click="syncStepsTextFromForm"
            >使用当前可视化刷新 JSON
          </el-button>
        </div>
        <AceEditor v-model:content="stepsText" lang="json" :can-set="true" height="560px" />
      </el-tab-pane>
    </el-tabs>

    <WebStepDetailDialog
      v-model="showStepDetailDialog"
      :current-step="currentStep || {}"
      :step-index="selectedStepIndex"
      :show-fingerprint="showFingerprint"
      @change="emitChange"
    />
  </div>
</template>

<script setup>
  import { computed, onMounted } from 'vue';
  import { ElMessage } from 'element-plus';
  import AceEditor from '@/components/hrm/common/ace-editor.vue';
  import WebStepDetailDialog from './WebStepDetailDialog.vue';
  import { actionOptions, keyboardKeyOptions, locatorTypeOptions } from '../utils/shared.js';
  import { useStepEditorTable } from '../composables/useStepEditorTable.js';

  const props = defineProps({
    // 步骤数组：由调用方持有，组件只做原地变更（push/splice），
    // 每次变更后 emit('change') 通知调用方。
    steps: { type: Array, required: true },
    // JSON Tab 文本序列化钩子；默认直接序列化步骤数组，
    // 用例管理注入提交格式序列化（prepareStepForSubmit）。
    serializeSteps: { type: Function, default: null },
    // 是否在详情弹窗中显示"指纹"字段：用例管理显示（服务端落库），
    // 门店配置版本步骤不落指纹，传 false 隐藏。
    showFingerprint: { type: Boolean, default: true },
    // 表格内部滚动限高；传空值表示不限高，由外层容器（如弹窗 body）统一滚动，
    // 避免表格内滚动条与外层滚动条叠加出现两个竖向滚动条。
    tableMaxHeight: { type: [String, Number], default: 560 },
  });

  const emit = defineEmits(['change']);

  function emitChange() {
    emit('change', props.steps);
  }

  const editor = useStepEditorTable({
    getSteps: () => props.steps,
    emitChange,
    serializeSteps: props.serializeSteps || undefined,
  });

  // 顶层解构：模板中的 ref 自动解包，函数直接可用。
  const {
    activeTab,
    selectedStepIndex,
    stepsText,
    showStepDetailDialog,
    currentStep,
    syncStepsTextFromForm,
    applyStepsTextToForm,
    getActionLabel,
    startStepCellEditing,
    finishStepCellEditing,
    isStepCellEditing,
    handleStepRowClick,
    getStepRowClassName,
    openStepDetailByIndex,
    addStep,
    insertStep,
    removeStep,
    moveStep,
    handleStepActionTypeChange,
    getPrimaryLocator,
    updatePrimaryLocatorType,
    updatePrimaryLocatorValue,
    summarizeStepParams,
    describeStepTarget,
    stepNeedsTarget,
    resetUi,
    watchSteps,
  } = editor;

  // 存在截图步骤时展示证据列，与门店配置版本编辑器保持一致。
  const hasEvidenceStep = computed(() => props.steps.some((step) => step.actionType === 'capture_screenshot'));

  function handleApplyJson() {
    const result = applyStepsTextToForm(true);
    if (!result.ok) {
      ElMessage.error(result.message);
      return;
    }
    if (result.success) {
      ElMessage.success(result.message);
    }
    emitChange();
  }

  onMounted(() => {
    watchSteps();
    syncStepsTextFromForm();
  });

  /**
   * 保存前由调用方调用：若当前在 JSON Tab，把 JSON 文本应用回步骤数组。
   * 应用失败时提示并返回 false，调用方应中止保存。
   * @returns {boolean}
   */
  function flush() {
    if (editor.flushJsonToSteps()) {
      return true;
    }
    ElMessage.error('步骤 JSON 应用失败，请修正后再保存');
    return false;
  }

  defineExpose({
    flush,
    resetUi,
    syncStepsTextFromForm,
  });
</script>

<style scoped lang="scss">
  @import '../styles/web-step-editor.scss';
</style>
