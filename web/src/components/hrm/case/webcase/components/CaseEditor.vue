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
                v-for="item in props.projectOptions"
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

    <el-tabs v-model="caseEditorTab" class="case-editor-tabs">
      <el-tab-pane label="可视化步骤" name="visual">
        <div class="step-table-toolbar">
          <div class="panel-title">测试步骤</div>
          <div class="step-table-toolbar-actions">
            <el-button type="primary" icon="Plus" @click="addStep()">新增步骤 </el-button>
            <el-button
              plain
              icon="EditPen"
              :disabled="selectedStepIndex < 0"
              @click="openStepDetailByIndex(selectedStepIndex)"
              >编辑当前步骤
            </el-button>
          </div>
        </div>
        <el-table
          :data="form.steps"
          border
          class="step-edit-table"
          max-height="560px"
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
          <el-table-column label="步骤名称" min-width="220">
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
          <el-table-column label="定位信息" min-width="320">
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
                        @update:model-value="
                          updatePrimaryLocatorValue(scope.row, 'selector', $event)
                        "
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
          <el-table-column label="输入/参数" min-width="260">
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
                  :disabled="scope.$index === form.steps.length - 1"
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
          <el-button type="primary" icon="Check" @click="applyStepsTextToForm(true)"
            >应用 JSON 到可视化
          </el-button>
          <el-button icon="RefreshRight" @click="syncStepsTextFromForm"
            >使用当前可视化刷新 JSON
          </el-button>
        </div>
        <AceEditor v-model:content="stepsText" lang="json" :can-set="true" height="560px" />
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <el-button @click="showCaseDialog = false">取消</el-button>
      <el-button type="primary" :loading="loading.save" @click="saveCase">保存 </el-button>
    </template>
  </el-dialog>
  <StepDetail
    step-index=""
    current-step=""
    :show-step-detail-dialog="showStepDetailDialog"
  ></StepDetail>
</template>

<script setup>
  import AceEditor from '@/components/hrm/common/ace-editor.vue';
  import StepDetail from '@/components/hrm/case/webcase/components/StepDetail.vue';
  import { browserOptions } from '../utils/shared.js';
  import { createEmptyCase } from '../domain/caseDomain.js';
  import { stepNeedsTarget } from '@/components/hrm/case/webcase/domain/stepDomain.js';

  const props = defineProps({
    context: {
      type: Object,
      required: true,
    },
    projectOptions: { type: Object, required: true },
  });

  const form = ref(createEmptyCase());

  function openStepDetailByIndex(index) {
    if (index < 0 || index >= form.value.steps.length) {
      return;
    }
    finishStepCellEditing();
    form.value.steps[index] = normalizeStep(form.value.steps[index], index);
    if (stepNeedsTarget(form.value.steps[index]?.actionType)) {
      getPrimaryLocator(form.value.steps[index]);
    }
    selectedStepIndex.value = index;
    showStepDetailDialog.value = true;
  }
</script>

<style scoped lang="scss">
  @import '../styles/dialogs.scss';
</style>
