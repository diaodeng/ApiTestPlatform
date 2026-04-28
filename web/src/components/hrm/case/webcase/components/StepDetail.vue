<script lang="ts" setup>
  import AceEditor from '@/components/hrm/common/ace-editor.vue';
  import { computed } from 'vue';
  import {
    actionOptions,
    keyboardKeyOptions,
    safeJsonStringify,
    locatorTypeOptions,
  } from '../utils/shared.js';
  import { stepNeedsTarget, normalizeStepParams } from '../domain/stepDomain';
  import { createDefaultTargetSnapshot } from '../domain/snapshotDomain';
  import {
    addLocator,
    setPrimaryLocator,
    moveLocator,
    removeLocator,
    handleLocatorTypeChange,
    resolveLocatorIndex,
    updateLocatorNth,
  } from '../domain/locatorDomain.js';

  const props = defineProps({
    currentStep: { type: Object, required: true },
    stepIndex: { type: Number, required: true },
  });
  const showStepDetailDialog = defineModel('showStepDetailDialog', {
    type: Boolean,
    default: false,
  });
  const emit = defineEmits(['update']);

  const stepDetailTitle = computed(() =>
    props.stepIndex >= 0 ? `步骤详情 - #${props.stepIndex + 1}` : '步骤详情'
  );

  function handleStepActionTypeChange(step) {
    step.params = normalizeStepParams(step.actionType, step.params);
    if (stepNeedsTarget(step.actionType) && !step.targetSnapshot) {
      step.targetSnapshot = createDefaultTargetSnapshot();
    }
  }

  function dialogClose(evt) {
    emit('update', props.currentStep, props.stepIndex);
    showStepDetailDialog.value = false;
  }
</script>

<template>
  <el-dialog
    v-model="showStepDetailDialog"
    :title="stepDetailTitle"
    width="90%"
    destroy-on-close
    append-to-body
    :close-on-click-modal="false"
    :close-on-press-escape="false"
  >
    <template v-if="props.currentStep">
      <el-form :model="props.currentStep" label-width="100px" class="mb16">
        <el-row :gutter="16">
          <el-col :span="10">
            <el-form-item label="步骤名称">
              <el-input v-model="props.currentStep.stepName" placeholder="请输入步骤名称" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="动作类型">
              <el-select
                v-model="props.currentStep.actionType"
                filterable
                style="width: 100%"
                @change="handleStepActionTypeChange(props.currentStep)"
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
              <el-switch v-model="props.currentStep.enabled" />
            </el-form-item>
          </el-col>
          <el-col :span="4">
            <el-form-item label="继续执行">
              <el-switch v-model="props.currentStep.continueOnFailure" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="超时(ms)">
              <el-input-number
                v-model="props.currentStep.timeoutMs"
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
                v-model="props.currentStep.params.thinkTimeMs"
                :min="0"
                :step="100"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="记录来源">
              <el-input v-model="props.currentStep.recordOrigin" placeholder="manual / record" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="元素ID">
              <el-input v-model="props.currentStep.elementId" placeholder="可选" />
            </el-form-item>
          </el-col>
          <el-col v-if="props.currentStep.actionType === 'goto'" :span="24">
            <el-form-item label="跳转地址">
              <el-input
                v-model="props.currentStep.params.url"
                placeholder="https://example.com/path"
              />
            </el-form-item>
          </el-col>
          <el-col v-else-if="props.currentStep.actionType === 'set_window_size'" :span="24">
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="窗口宽度">
                  <el-input-number
                    v-model="props.currentStep.params.width"
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
                    v-model="props.currentStep.params.height"
                    :min="1"
                    :step="100"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </el-col>
          <el-col v-else-if="props.currentStep.actionType === 'fill'" :span="24">
            <el-form-item label="输入内容">
              <el-input
                v-model="props.currentStep.params.value"
                type="textarea"
                :rows="3"
                placeholder="请输入内容"
              />
            </el-form-item>
          </el-col>
          <el-col v-else-if="props.currentStep.actionType === 'press'" :span="24">
            <el-form-item label="按键值">
              <el-select
                v-model="props.currentStep.params.key"
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
          <el-col v-else-if="props.currentStep.actionType === 'select_option'" :span="24">
            <el-form-item label="选项值">
              <el-select
                v-model="props.currentStep.params.values"
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
          <el-col v-else-if="['sleep', 'wait'].includes(props.currentStep.actionType)" :span="24">
            <el-form-item label="等待时长(ms)">
              <el-input-number
                v-model="props.currentStep.params.waitMs"
                :min="0"
                :step="100"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col
            v-else-if="
              ['assert_page_contains', 'assert_page_not_contains'].includes(
                props.currentStep.actionType
              )
            "
            :span="24"
          >
            <el-form-item label="页面文本">
              <el-input
                v-model="props.currentStep.params.text"
                type="textarea"
                :rows="2"
                placeholder="请输入页面中应包含/不包含的文本"
              />
            </el-form-item>
          </el-col>
          <el-col v-else-if="props.currentStep.actionType === 'assert_title_contains'" :span="24">
            <el-form-item label="标题关键字">
              <el-input
                v-model="props.currentStep.params.title"
                placeholder="请输入页面标题关键字"
              />
            </el-form-item>
          </el-col>
          <el-col v-else-if="props.currentStep.actionType === 'assert_url_contains'" :span="24">
            <el-form-item label="URL关键字">
              <el-input
                v-model="props.currentStep.params.urlPart"
                placeholder="请输入 URL 中应包含的关键字"
              />
            </el-form-item>
          </el-col>
          <el-col
            v-else-if="
              ['assert_text_equals', 'assert_text_contains'].includes(props.currentStep.actionType)
            "
            :span="24"
          >
            <el-form-item label="文本期望值">
              <el-input
                v-model="props.currentStep.params.expected"
                type="textarea"
                :rows="2"
                placeholder="请输入元素文本期望值"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <el-card
        v-if="stepNeedsTarget(props.currentStep.actionType)"
        class="panel-card"
        shadow="never"
      >
        <template #header>
          <div class="panel-header">
            <span>定位与快照</span>
            <el-button type="primary" plain icon="Plus" @click="addLocator(props.currentStep)"
              >新增定位器
            </el-button>
          </div>
        </template>

        <el-row :gutter="16" class="mb16">
          <el-col :span="8">
            <el-form-item label="元素文本" label-width="90px">
              <el-input
                v-model="props.currentStep.targetSnapshot.elementText"
                placeholder="元素文本快照"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="指纹" label-width="90px">
              <el-input
                v-model="props.currentStep.targetSnapshot.fingerprint"
                placeholder="元素指纹"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="稳定分" label-width="90px">
              <el-input-number
                v-model="props.currentStep.targetSnapshot.stableScore"
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
                v-model="props.currentStep.targetSnapshot.context.pageUrl"
                placeholder="页面 URL"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Frame URL" label-width="90px">
              <el-input
                v-model="props.currentStep.targetSnapshot.context.frameUrl"
                placeholder="Frame URL"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <div class="locator-tip">
          执行顺序按列表从上到下，仅尝试“启用”定位器；命中后继续下一步，可用“设为首选”快速置顶。
        </div>

        <div v-if="props.currentStep.targetSnapshot?.locators?.length" class="locator-list">
          <div
            v-for="(locator, locatorIndex) in props.currentStep.targetSnapshot.locators"
            :key="
              locator.locatorSnapshotId ||
              `${props.currentStep.stepIndex || props.stepIndex}-${locatorIndex}`
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
                  @click="setPrimaryLocator(props.currentStep, locatorIndex)"
                  >设为首选
                </el-button>
                <el-button
                  link
                  icon="Top"
                  :disabled="locatorIndex === 0"
                  @click="moveLocator(props.currentStep, locatorIndex, -1)"
                />
                <el-button
                  link
                  icon="Bottom"
                  :disabled="locatorIndex === props.currentStep.targetSnapshot.locators.length - 1"
                  @click="moveLocator(props.currentStep, locatorIndex, 1)"
                />
                <el-button
                  link
                  type="danger"
                  icon="Delete"
                  @click="removeLocator(props.currentStep, locatorIndex)"
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
            <el-button type="primary" plain icon="Plus" @click="addAssertion(props.currentStep)"
              >新增断言
            </el-button>
          </div>
        </template>

        <div v-if="props.currentStep.assertions?.length">
          <el-table
            :data="props.currentStep.assertions"
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
                  @click="removeAssertion(props.currentStep, scope.$index)"
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
          :content="safeJsonStringify(props.currentStep.rawEvent || {})"
          lang="json"
          :read-only="true"
          height="220px"
        />
      </el-card>
    </template>
    <template #footer>
      <el-button @click="dialogClose">关闭 </el-button>
    </template>
  </el-dialog>
</template>

<style scoped lang="scss"></style>
