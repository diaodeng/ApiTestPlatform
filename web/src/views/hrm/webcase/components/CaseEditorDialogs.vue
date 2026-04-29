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

  <el-dialog
    v-model="showStepDetailDialog"
    :title="stepDetailTitle"
    width="90%"
    destroy-on-close
    append-to-body
    :close-on-click-modal="false"
    :close-on-press-escape="false"
  >
    <template v-if="currentStep">
      <el-form :model="currentStep" label-width="100px" class="mb16">
        <el-row :gutter="16">
          <el-col :span="10">
            <el-form-item label="步骤名称">
              <el-input v-model="currentStep.stepName" placeholder="请输入步骤名称" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="动作类型">
              <el-select
                v-model="currentStep.actionType"
                filterable
                style="width: 100%"
                @change="handleStepActionTypeChange(currentStep)"
              >
                <el-option
                  v-for="item in actionOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="启用">
              <el-switch v-model="currentStep.enabled" />
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="继续执行">
              <el-switch v-model="currentStep.continueOnFailure" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="超时(ms)">
              <el-input-number
                v-model="currentStep.timeoutMs"
                :min="0"
                :step="1000"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="思考(ms)">
              <el-input-number
                v-model="currentStep.params.thinkTimeMs"
                :min="0"
                :step="100"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="记录来源">
              <el-input v-model="currentStep.recordOrigin" placeholder="manual / record" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="元素ID">
              <el-input v-model="currentStep.elementId" placeholder="可选" />
            </el-form-item>
          </el-col>
          <el-col v-if="currentStep.actionType === 'goto'" :span="24">
            <el-form-item label="跳转地址">
              <el-input v-model="currentStep.params.url" placeholder="https://example.com/path" />
            </el-form-item>
          </el-col>
          <el-col v-else-if="currentStep.actionType === 'set_window_size'" :span="24">
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="窗口宽度">
                  <el-input-number
                    v-model="currentStep.params.width"
                    :min="1"
                    :step="100"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="窗口高度">
                  <el-input-number
                    v-model="currentStep.params.height"
                    :min="1"
                    :step="100"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </el-col>
          <el-col v-else-if="currentStep.actionType === 'fill'" :span="24">
            <el-form-item label="输入内容">
              <el-input
                v-model="currentStep.params.value"
                type="textarea"
                :rows="3"
                placeholder="请输入内容"
              />
            </el-form-item>
          </el-col>
          <el-col v-else-if="currentStep.actionType === 'press'" :span="24">
            <el-form-item label="按键值">
              <el-select
                v-model="currentStep.params.key"
                filterable
                allow-create
                default-first-option
                style="width: 100%"
                placeholder="选择或输入按键"
              >
                <el-option
                  v-for="item in keyboardKeyOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-else-if="currentStep.actionType === 'select_option'" :span="24">
            <el-form-item label="选项值">
              <el-select
                v-model="currentStep.params.values"
                multiple
                filterable
                allow-create
                default-first-option
                collapse-tags
                collapse-tags-tooltip
                style="width: 100%"
                placeholder="输入或选择下拉选项值"
              />
            </el-form-item>
          </el-col>
          <el-col v-else-if="['sleep', 'wait'].includes(currentStep.actionType)" :span="24">
            <el-form-item label="等待时长(ms)">
              <el-input-number
                v-model="currentStep.params.waitMs"
                :min="0"
                :step="100"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col
            v-else-if="
              ['assert_page_contains', 'assert_page_not_contains'].includes(currentStep.actionType)
            "
            :span="24"
          >
            <el-form-item label="页面文本">
              <el-input
                v-model="currentStep.params.text"
                type="textarea"
                :rows="2"
                placeholder="请输入页面中应包含/不包含的文本"
              />
            </el-form-item>
          </el-col>
          <el-col v-else-if="currentStep.actionType === 'assert_title_contains'" :span="24">
            <el-form-item label="标题关键字">
              <el-input v-model="currentStep.params.title" placeholder="请输入页面标题关键字" />
            </el-form-item>
          </el-col>
          <el-col v-else-if="currentStep.actionType === 'assert_url_contains'" :span="24">
            <el-form-item label="URL关键字">
              <el-input
                v-model="currentStep.params.urlPart"
                placeholder="请输入 URL 中应包含的关键字"
              />
            </el-form-item>
          </el-col>
          <el-col
            v-else-if="
              ['assert_text_equals', 'assert_text_contains'].includes(currentStep.actionType)
            "
            :span="24"
          >
            <el-form-item label="文本期望值">
              <el-input
                v-model="currentStep.params.expected"
                type="textarea"
                :rows="2"
                placeholder="请输入元素文本期望值"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <el-card v-if="stepNeedsTarget(currentStep.actionType)" class="panel-card" shadow="never">
        <template #header>
          <div class="panel-header">
            <span>定位与快照</span>
            <el-button type="primary" plain icon="Plus" @click="addLocator(currentStep)"
              >新增定位器
            </el-button>
          </div>
        </template>

        <el-row :gutter="16" class="mb16">
          <el-col :span="8">
            <el-form-item label="元素文本" label-width="90px">
              <el-input
                v-model="currentStep.targetSnapshot.elementText"
                placeholder="元素文本快照"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="指纹" label-width="90px">
              <el-input v-model="currentStep.targetSnapshot.fingerprint" placeholder="元素指纹" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="稳定分" label-width="90px">
              <el-input-number
                v-model="currentStep.targetSnapshot.stableScore"
                :min="0"
                :step="1"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="页面URL" label-width="90px">
              <el-input
                v-model="currentStep.targetSnapshot.context.pageUrl"
                placeholder="页面 URL"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Frame URL" label-width="90px">
              <el-input
                v-model="currentStep.targetSnapshot.context.frameUrl"
                placeholder="Frame URL"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <div class="locator-tip">
          执行顺序按列表从上到下，仅尝试“启用”定位器；命中后继续下一步，可用“设为首选”快速置顶。
        </div>

        <div v-if="currentStep.targetSnapshot?.locators?.length" class="locator-list">
          <div
            v-for="(locator, locatorIndex) in currentStep.targetSnapshot.locators"
            :key="
              locator.locatorSnapshotId ||
              `${currentStep.stepIndex || selectedStepIndex}-${locatorIndex}`
            "
            class="locator-item"
          >
            <div class="locator-header">
              <div class="locator-title">
                <span>定位器 {{ locatorIndex + 1 }}</span>
                <el-tag v-if="locatorIndex === 0" size="small" type="success">首选</el-tag>
              </div>
              <div class="locator-actions">
                <el-switch
                  v-model="locator.enabled"
                  inline-prompt
                  active-text="启用"
                  inactive-text="停用"
                />
                <el-button
                  link
                  type="primary"
                  :disabled="locatorIndex === 0"
                  @click="setPrimaryLocator(currentStep, locatorIndex)"
                  >设为首选
                </el-button>
                <el-button
                  link
                  icon="Top"
                  :disabled="locatorIndex === 0"
                  @click="moveLocator(currentStep, locatorIndex, -1)"
                />
                <el-button
                  link
                  icon="Bottom"
                  :disabled="locatorIndex === currentStep.targetSnapshot.locators.length - 1"
                  @click="moveLocator(currentStep, locatorIndex, 1)"
                />
                <el-button
                  link
                  type="danger"
                  icon="Delete"
                  @click="removeLocator(currentStep, locatorIndex)"
                />
              </div>
            </div>

            <el-row :gutter="12">
              <el-col :span="6">
                <el-form-item label="类型" label-width="60px">
                  <el-select
                    v-model="locator.locatorType"
                    style="width: 100%"
                    @change="handleLocatorTypeChange(locator)"
                  >
                    <el-option
                      v-for="item in locatorTypeOptions"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col v-if="locator.locatorType === 'role'" :span="8">
                <el-form-item label="角色" label-width="60px">
                  <el-input v-model="locator.locatorValue.role" placeholder="button / textbox" />
                </el-form-item>
              </el-col>
              <el-col v-if="locator.locatorType === 'role'" :span="6">
                <el-form-item label="名称" label-width="60px">
                  <el-input v-model="locator.locatorValue.name" placeholder="按钮名称" />
                </el-form-item>
              </el-col>
              <el-col v-if="locator.locatorType === 'role'" :span="4">
                <el-form-item label="精确" label-width="60px">
                  <el-switch v-model="locator.locatorValue.exact" />
                </el-form-item>
              </el-col>
              <el-col
                v-if="['label', 'placeholder', 'text'].includes(locator.locatorType)"
                :span="14"
              >
                <el-form-item label="文本" label-width="60px">
                  <el-input v-model="locator.locatorValue.text" placeholder="定位文本" />
                </el-form-item>
              </el-col>
              <el-col
                v-if="['label', 'placeholder', 'text'].includes(locator.locatorType)"
                :span="4"
              >
                <el-form-item label="精确" label-width="60px">
                  <el-switch v-model="locator.locatorValue.exact" />
                </el-form-item>
              </el-col>
              <el-col v-if="locator.locatorType === 'test_id'" :span="14">
                <el-form-item label="Test ID" label-width="70px">
                  <el-input v-model="locator.locatorValue.testId" placeholder="data-testid" />
                </el-form-item>
              </el-col>
              <el-col v-if="locator.locatorType === 'id'" :span="14">
                <el-form-item label="ID" label-width="70px">
                  <el-input v-model="locator.locatorValue.id" placeholder="元素 id" />
                </el-form-item>
              </el-col>
              <el-col v-if="locator.locatorType === 'name'" :span="14">
                <el-form-item label="Name" label-width="70px">
                  <el-input v-model="locator.locatorValue.name" placeholder="元素 name" />
                </el-form-item>
              </el-col>
              <el-col v-if="['css', 'xpath'].includes(locator.locatorType)" :span="18">
                <el-form-item label="选择器" label-width="60px">
                  <el-input
                    v-model="locator.locatorValue.selector"
                    :placeholder="
                      locator.locatorType === 'xpath'
                        ? '//*[@id=&quot;login&quot;]'
                        : '.login-button'
                    "
                  />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="Nth(0基)" label-width="70px">
                  <el-input-number
                    :model-value="resolveLocatorIndex(locator.locatorValue)"
                    :min="0"
                    :step="1"
                    :value-on-clear="null"
                    controls-position="right"
                    style="width: 100%"
                    @update:model-value="(value) => updateLocatorNth(locator, value)"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </div>
        <el-empty v-else description="当前步骤暂无定位器" :image-size="70" />
      </el-card>

      <el-card class="panel-card" shadow="never">
        <template #header>
          <div class="panel-header">
            <span>断言</span>
            <el-button type="primary" plain icon="Plus" @click="addAssertion(currentStep)"
              >新增断言
            </el-button>
          </div>
        </template>

        <div v-if="currentStep.assertions?.length">
          <el-table
            :data="currentStep.assertions"
            border
            table-layout="fixed"
            class="assertion-edit-table"
          >
            <el-table-column type="expand" width="56">
              <template #default="scope">
                <template v-if="assertionNeedsTarget(scope.row.assertType)">
                  <div class="locator-tip">
                    断言定位器会按从上到下顺序尝试，命中第一个后执行断言。
                  </div>
                  <div v-if="getAssertionLocatorList(scope.row).length" class="locator-list">
                    <div
                      v-for="(locator, locatorIndex) in getAssertionLocatorList(scope.row)"
                      :key="
                        locator.locatorSnapshotId ||
                        `${selectedStepIndex}-${scope.$index}-${locatorIndex}`
                      "
                      class="locator-item"
                    >
                      <div class="locator-header">
                        <div class="locator-title">
                          <span>定位器 {{ locatorIndex + 1 }}</span>
                          <el-tag v-if="locatorIndex === 0" size="small" type="success"
                            >首选
                          </el-tag>
                        </div>
                        <div class="locator-actions">
                          <el-switch
                            v-model="locator.enabled"
                            inline-prompt
                            active-text="启用"
                            inactive-text="停用"
                          />
                          <el-button
                            link
                            type="primary"
                            :disabled="locatorIndex === 0"
                            @click="setAssertionPrimaryLocator(scope.row, locatorIndex)"
                            >设为首选
                          </el-button>
                          <el-button
                            link
                            icon="Top"
                            :disabled="locatorIndex === 0"
                            @click="moveAssertionLocator(scope.row, locatorIndex, -1)"
                          />
                          <el-button
                            link
                            icon="Bottom"
                            :disabled="
                              locatorIndex === getAssertionLocatorList(scope.row).length - 1
                            "
                            @click="moveAssertionLocator(scope.row, locatorIndex, 1)"
                          />
                          <el-button
                            link
                            type="danger"
                            icon="Delete"
                            @click="removeAssertionLocator(scope.row, locatorIndex)"
                          />
                        </div>
                      </div>

                      <el-row :gutter="12">
                        <el-col :span="6">
                          <el-form-item label="类型" label-width="60px">
                            <el-select
                              v-model="locator.locatorType"
                              style="width: 100%"
                              @change="handleLocatorTypeChange(locator)"
                            >
                              <el-option
                                v-for="item in locatorTypeOptions"
                                :key="item.value"
                                :label="item.label"
                                :value="item.value"
                              />
                            </el-select>
                          </el-form-item>
                        </el-col>
                        <el-col v-if="locator.locatorType === 'role'" :span="8">
                          <el-form-item label="角色" label-width="60px">
                            <el-input
                              v-model="locator.locatorValue.role"
                              placeholder="button / textbox"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col v-if="locator.locatorType === 'role'" :span="6">
                          <el-form-item label="名称" label-width="60px">
                            <el-input v-model="locator.locatorValue.name" placeholder="按钮名称" />
                          </el-form-item>
                        </el-col>
                        <el-col v-if="locator.locatorType === 'role'" :span="4">
                          <el-form-item label="精确" label-width="60px">
                            <el-switch v-model="locator.locatorValue.exact" />
                          </el-form-item>
                        </el-col>
                        <el-col
                          v-if="['label', 'placeholder', 'text'].includes(locator.locatorType)"
                          :span="14"
                        >
                          <el-form-item label="文本" label-width="60px">
                            <el-input v-model="locator.locatorValue.text" placeholder="定位文本" />
                          </el-form-item>
                        </el-col>
                        <el-col
                          v-if="['label', 'placeholder', 'text'].includes(locator.locatorType)"
                          :span="4"
                        >
                          <el-form-item label="精确" label-width="60px">
                            <el-switch v-model="locator.locatorValue.exact" />
                          </el-form-item>
                        </el-col>
                        <el-col v-if="locator.locatorType === 'test_id'" :span="14">
                          <el-form-item label="Test ID" label-width="70px">
                            <el-input
                              v-model="locator.locatorValue.testId"
                              placeholder="data-testid"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col v-if="locator.locatorType === 'id'" :span="14">
                          <el-form-item label="ID" label-width="70px">
                            <el-input v-model="locator.locatorValue.id" placeholder="元素 id" />
                          </el-form-item>
                        </el-col>
                        <el-col v-if="locator.locatorType === 'name'" :span="14">
                          <el-form-item label="Name" label-width="70px">
                            <el-input v-model="locator.locatorValue.name" placeholder="元素 name" />
                          </el-form-item>
                        </el-col>
                        <el-col v-if="['css', 'xpath'].includes(locator.locatorType)" :span="18">
                          <el-form-item label="选择器" label-width="60px">
                            <el-input
                              v-model="locator.locatorValue.selector"
                              :placeholder="
                                locator.locatorType === 'xpath'
                                  ? '//*[@id=&quot;login&quot;]'
                                  : '.login-button'
                              "
                            />
                          </el-form-item>
                        </el-col>
                        <el-col :span="6">
                          <el-form-item label="Nth(0基)" label-width="70px">
                            <el-input-number
                              :model-value="resolveLocatorIndex(locator.locatorValue)"
                              :min="0"
                              :step="1"
                              :value-on-clear="null"
                              controls-position="right"
                              style="width: 100%"
                              @update:model-value="(value) => updateLocatorNth(locator, value)"
                            />
                          </el-form-item>
                        </el-col>
                      </el-row>
                    </div>
                  </div>
                  <el-empty v-else description="当前断言暂无定位器" :image-size="60" />
                </template>
                <span v-else class="step-cell-placeholder">当前断言无需独立定位器</span>
              </template>
            </el-table-column>
            <el-table-column label="序号" width="76">
              <template #default="scope">#{{ scope.$index + 1 }} </template>
            </el-table-column>
            <el-table-column label="启用" width="90">
              <template #default="scope">
                <el-switch v-model="scope.row.enabled" />
              </template>
            </el-table-column>
            <el-table-column label="断言类型" width="170">
              <template #default="scope">
                <el-select
                  v-model="scope.row.assertType"
                  style="width: 100%"
                  @change="handleAssertionTypeChange(scope.row)"
                >
                  <el-option
                    v-for="item in assertionTypeOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="期望值" min-width="220">
              <template #default="scope">
                <el-input v-model="scope.row.expected" placeholder="请输入期望值" />
              </template>
            </el-table-column>
            <el-table-column label="等待(ms)" width="130">
              <template #default="scope">
                <el-input-number
                  v-model="scope.row.waitMs"
                  :min="200"
                  :step="100"
                  controls-position="right"
                  style="width: 100%"
                />
              </template>
            </el-table-column>
            <el-table-column label="定位器(首选)" min-width="340">
              <template #default="scope">
                <template
                  v-if="
                    assertionNeedsTarget(scope.row.assertType) &&
                    getAssertionPrimaryLocator(scope.row)
                  "
                >
                  <div class="step-inline-target" @click.stop>
                    <el-select
                      :model-value="getAssertionPrimaryLocator(scope.row)?.locatorType"
                      style="width: 110px"
                      @update:model-value="updateAssertionPrimaryLocatorType(scope.row, $event)"
                    >
                      <el-option
                        v-for="item in locatorTypeOptions"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                    <template v-if="getAssertionPrimaryLocator(scope.row)?.locatorType === 'role'">
                      <el-input
                        :model-value="
                          getAssertionPrimaryLocator(scope.row)?.locatorValue?.role || ''
                        "
                        placeholder="角色"
                        @update:model-value="
                          updateAssertionPrimaryLocatorValue(scope.row, 'role', $event)
                        "
                      />
                      <el-input
                        :model-value="
                          getAssertionPrimaryLocator(scope.row)?.locatorValue?.name || ''
                        "
                        placeholder="名称"
                        @update:model-value="
                          updateAssertionPrimaryLocatorValue(scope.row, 'name', $event)
                        "
                      />
                    </template>
                    <el-input
                      v-else-if="
                        ['label', 'placeholder', 'text'].includes(
                          getAssertionPrimaryLocator(scope.row)?.locatorType
                        )
                      "
                      :model-value="getAssertionPrimaryLocator(scope.row)?.locatorValue?.text || ''"
                      placeholder="定位文本"
                      @update:model-value="
                        updateAssertionPrimaryLocatorValue(scope.row, 'text', $event)
                      "
                    />
                    <el-input
                      v-else-if="getAssertionPrimaryLocator(scope.row)?.locatorType === 'test_id'"
                      :model-value="
                        getAssertionPrimaryLocator(scope.row)?.locatorValue?.testId || ''
                      "
                      placeholder="Test ID"
                      @update:model-value="
                        updateAssertionPrimaryLocatorValue(scope.row, 'testId', $event)
                      "
                    />
                    <el-input
                      v-else-if="getAssertionPrimaryLocator(scope.row)?.locatorType === 'id'"
                      :model-value="getAssertionPrimaryLocator(scope.row)?.locatorValue?.id || ''"
                      placeholder="元素 id"
                      @update:model-value="
                        updateAssertionPrimaryLocatorValue(scope.row, 'id', $event)
                      "
                    />
                    <el-input
                      v-else-if="getAssertionPrimaryLocator(scope.row)?.locatorType === 'name'"
                      :model-value="getAssertionPrimaryLocator(scope.row)?.locatorValue?.name || ''"
                      placeholder="元素 name"
                      @update:model-value="
                        updateAssertionPrimaryLocatorValue(scope.row, 'name', $event)
                      "
                    />
                    <el-input
                      v-else
                      :model-value="
                        getAssertionPrimaryLocator(scope.row)?.locatorValue?.selector || ''
                      "
                      :placeholder="
                        getAssertionPrimaryLocator(scope.row)?.locatorType === 'xpath'
                          ? '//*[@id=&quot;login&quot;]'
                          : '.login-button'
                      "
                      @update:model-value="
                        updateAssertionPrimaryLocatorValue(scope.row, 'selector', $event)
                      "
                    />
                  </div>
                </template>
                <span v-else class="step-cell-placeholder">当前断言无需定位器</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="170" fixed="right">
              <template #default="scope">
                <el-button
                  link
                  type="primary"
                  :disabled="!assertionNeedsTarget(scope.row.assertType)"
                  @click="addAssertionLocator(scope.row)"
                >
                  新增定位器
                </el-button>
                <el-button
                  link
                  type="danger"
                  icon="Delete"
                  @click="removeAssertion(currentStep, scope.$index)"
                  >删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="step-detail-tip mt8">展开每行可编辑该断言的完整定位器列表及优先级。</div>
        </div>
        <el-empty v-else description="当前步骤暂无断言" :image-size="70" />
      </el-card>

      <el-card class="panel-card" shadow="never">
        <template #header>
          <div class="panel-header">
            <span>原始事件</span>
            <span class="step-detail-tip">用于查看录制时的原始数据，默认只读</span>
          </div>
        </template>
        <AceEditor
          :content="safeJsonStringify(currentStep.rawEvent || {})"
          lang="json"
          :read-only="true"
          height="220px"
        />
      </el-card>
    </template>
    <template #footer>
      <el-button @click="showStepDetailDialog = false">关闭 </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
  import AceEditor from '@/components/hrm/common/ace-editor.vue';

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
    caseEditorTab,
    addStep,
    selectedStepIndex,
    openStepDetailByIndex,
    getStepRowClassName,
    handleStepRowClick,
    startStepCellEditing,
    isStepCellEditing,
    handleStepActionTypeChange,
    finishStepCellEditing,
    actionOptions,
    getActionLabel,
    stepNeedsTarget,
    getPrimaryLocator,
    locatorTypeOptions,
    updatePrimaryLocatorType,
    updatePrimaryLocatorValue,
    describeStepTarget,
    summarizeStepParams,
    insertStep,
    copyStep,
    removeStep,
    moveStep,
    syncStepsTextFromForm,
    stepsText,
    applyStepsTextToForm,
    loading,
    saveCase,
    showStepDetailDialog,
    stepDetailTitle,
    currentStep,
    addLocator,
    moveLocator,
    setPrimaryLocator,
    removeLocator,
    handleLocatorTypeChange,
    updateLocatorNth,
    isLocatorFilled,
    keyboardKeyOptions,
    addAssertion,
    removeAssertion,
    handleAssertionTypeChange,
    assertionTypeOptions,
    assertionNeedsTarget,
    getAssertionPrimaryLocator,
    updateAssertionPrimaryLocatorType,
    updateAssertionPrimaryLocatorValue,
    addAssertionLocator,
    getAssertionLocatorList,
    moveAssertionLocator,
    setAssertionPrimaryLocator,
    removeAssertionLocator,
    safeJsonStringify,
    resolveLocatorIndex,
  } = props.context;
</script>

<style scoped lang="scss">
  @import '../styles/dialogs.scss';
</style>
