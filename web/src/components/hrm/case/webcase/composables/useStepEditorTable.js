import { ref, computed, watch } from 'vue';
import { actionOptions, safeJsonStringify } from '../utils/shared.js';
import {
  stepNeedsTarget,
  normalizeStep,
  normalizeStepParams,
  summarizeStepParams,
  describeStepTarget,
  createDefaultStep,
} from '../domain/stepDomain.js';
import {
  createDefaultTargetSnapshot,
} from '../domain/snapshotDomain.js';
import {
  createDefaultLocator,
  normalizeLocatorValue,
} from '../domain/locatorDomain.js';

/**
 * 步骤编辑表格的组合式逻辑，供 WebStepEditor 组件使用。
 *
 * 职责边界：只负责"步骤数组"的表格交互（内联编辑、行操作、选中行、
 * JSON 双向同步、打开步骤详情弹窗），不负责步骤数组之外的表单与保存；
 * 数组本体由调用方持有并通过 getSteps() 访问器提供，本组合函数只做
 * 原地变更（push/splice），并在每次变更后回调 emitChange 通知调用方。
 *
 * @param {Object} options 依赖项
 * @param {Function} options.getSteps 步骤数组访问器 () => Array
 * @param {Function} options.emitChange 变更通知回调 () => void
 * @param {Function} [options.serializeSteps] JSON 文本序列化钩子，
 *   默认直接序列化步骤数组；用例管理注入提交格式（prepareStepForSubmit）
 * @returns {Object} 表格与详情弹窗所需的状态与方法
 */
export function useStepEditorTable(options = {}) {
  const {
    getSteps,
    emitChange,
    serializeSteps,
  } = options;

  // ---------- 基础状态 ----------
  const activeTab = ref('visual');
  const selectedStepIndex = ref(-1);
  const stepEditingCell = ref({ index: -1, field: '' });
  const stepsText = ref('[]');
  const showStepDetailDialog = ref(false);

  const currentStep = computed(() => getSteps()[selectedStepIndex.value] || null);
  const stepDetailTitle = computed(() =>
    selectedStepIndex.value >= 0 ? `步骤详情 - #${selectedStepIndex.value + 1}` : '步骤详情',
  );

  function getActionLabel(actionType) {
    return actionOptions.find((item) => item.value === actionType)?.label || actionType || '未设置';
  }

  // ---------- JSON 双向同步 ----------
  // JSON 文本默认直接序列化步骤数组；用例管理可注入提交格式序列化。
  const serialize = serializeSteps || ((steps) => safeJsonStringify(steps));

  function syncStepsTextFromForm() {
    stepsText.value = serialize(getSteps());
  }

  function applyStepsTextToForm(showSuccess = false) {
    let parsedSteps = [];
    try {
      parsedSteps = JSON.parse(stepsText.value || '[]');
    } catch (error) {
      return { ok: false, message: `步骤 JSON 解析失败：${error.message}` };
    }
    if (!Array.isArray(parsedSteps)) {
      return { ok: false, message: '步骤 JSON 必须是数组' };
    }
    const steps = getSteps();
    const normalized = parsedSteps.map((step, index) => normalizeStep(step, index));
    steps.splice(0, steps.length, ...normalized);
    selectedStepIndex.value = steps.length ? 0 : -1;
    if (showSuccess) {
      return { ok: true, message: 'JSON 已同步到可视化编辑器', success: true };
    }
    return { ok: true };
  }

  /**
   * 保存前调用：若当前在 JSON Tab，则把 JSON 文本应用回步骤数组；
   * 应用失败时提示并返回 false，调用方应中止保存。
   * @returns {boolean} 是否可以继续保存
   */
  function flushJsonToSteps() {
    if (activeTab.value !== 'json') {
      return true;
    }
    const result = applyStepsTextToForm();
    if (!result.ok) {
      return false;
    }
    return true;
  }

  // ---------- 内联单元格编辑 ----------
  function startStepCellEditing(index, field) {
    const steps = getSteps();
    if (index < 0 || index >= steps.length) {
      return;
    }
    selectedStepIndex.value = index;
    stepEditingCell.value = { index, field: `${field || ''}`.trim() };
  }

  function finishStepCellEditing() {
    stepEditingCell.value = { index: -1, field: '' };
  }

  function isStepCellEditing(index, field) {
    return (
      stepEditingCell.value.index === index &&
      stepEditingCell.value.field === `${field || ''}`.trim()
    );
  }

  // ---------- 选中行 ----------
  function handleStepRowClick(row) {
    const steps = getSteps();
    const index = steps.indexOf(row);
    if (index === -1) {
      return;
    }
    selectedStepIndex.value = index;
    if (stepEditingCell.value.index !== index) {
      finishStepCellEditing();
    }
  }

  function getStepRowClassName({ row }) {
    return getSteps().indexOf(row) === selectedStepIndex.value ? 'selected-step-row' : '';
  }

  // ---------- 步详情打开 ----------
  function openStepDetailByIndex(index) {
    const steps = getSteps();
    if (index < 0 || index >= steps.length) {
      return;
    }
    finishStepCellEditing();
    // 打开前全量标准化：补默认步骤名/参数/断言/定位快照，详情弹窗才能完整渲染。
    steps[index] = normalizeStep(steps[index], index);
    if (stepNeedsTarget(steps[index]?.actionType)) {
      getPrimaryLocator(steps[index]);
    }
    selectedStepIndex.value = index;
    showStepDetailDialog.value = true;
  }

  // ---------- 行操作（全部原地变更，不替换数组引用） ----------
  function addStep(actionType = 'click') {
    const steps = getSteps();
    steps.push(createDefaultStep(actionType));
    selectedStepIndex.value = steps.length - 1;
    finishStepCellEditing();
    emitChange();
  }

  function insertStep(index, actionType = 'click') {
    const steps = getSteps();
    const insertIndex = Math.max(0, Math.min(Number(index), steps.length));
    steps.splice(insertIndex, 0, createDefaultStep(actionType));
    selectedStepIndex.value = insertIndex;
    finishStepCellEditing();
    emitChange();
  }

  function removeStep(index) {
    const steps = getSteps();
    steps.splice(index, 1);
    if (!steps.length) {
      selectedStepIndex.value = -1;
      finishStepCellEditing();
      emitChange();
      return;
    }
    selectedStepIndex.value = Math.min(index, steps.length - 1);
    finishStepCellEditing();
    emitChange();
  }

  function moveStep(index, direction) {
    const steps = getSteps();
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= steps.length) return;
    const [moved] = steps.splice(index, 1);
    steps.splice(targetIndex, 0, moved);
    selectedStepIndex.value = targetIndex;
    finishStepCellEditing();
    emitChange();
  }

  // ---------- 动作切换与首选定位器（表格内联编辑用） ----------
  function handleStepActionTypeChange(step) {
    step.params = normalizeStepParams(step.actionType, step.params);
    if (stepNeedsTarget(step.actionType) && !step.targetSnapshot) {
      step.targetSnapshot = createDefaultTargetSnapshot();
    }
    emitChange();
  }

  function getPrimaryLocator(step) {
    if (!stepNeedsTarget(step?.actionType)) {
      return null;
    }
    if (!step.targetSnapshot) {
      step.targetSnapshot = createDefaultTargetSnapshot();
    }
    if (!Array.isArray(step.targetSnapshot.locators) || !step.targetSnapshot.locators.length) {
      step.targetSnapshot.locators = [createDefaultLocator()];
    }
    return (
      step.targetSnapshot.locators.find((item) => item.enabled !== false) ||
      step.targetSnapshot.locators[0]
    );
  }

  function updatePrimaryLocatorType(step, locatorType) {
    const locator = getPrimaryLocator(step);
    if (!locator) {
      return;
    }
    locator.locatorType = locatorType;
    locator.locatorValue = normalizeLocatorValue(locatorType, {});
    emitChange();
  }

  function updatePrimaryLocatorValue(step, key, value) {
    const locator = getPrimaryLocator(step);
    if (!locator) {
      return;
    }
    locator.locatorValue = normalizeLocatorValue(locator.locatorType, locator.locatorValue);
    locator.locatorValue[key] = value;
    emitChange();
  }

  // ---------- 组件级重置与监听 ----------
  /**
   * 打开编辑器/切换用例后重置内部 UI 状态，语义与原用例编辑器一致：
   * 回到可视化 Tab、按步骤数重置选中行、刷新 JSON 文本。
   */
  function resetUi() {
    activeTab.value = 'visual';
    const steps = getSteps();
    selectedStepIndex.value = steps.length ? 0 : -1;
    finishStepCellEditing();
    syncStepsTextFromForm();
  }

  function watchSteps() {
    // 步骤内容或引用变化时刷新 JSON 文本（JSON Tab 编辑中不覆盖用户输入）。
    watch(
      () => getSteps(),
      () => {
        if (activeTab.value !== 'json') {
          syncStepsTextFromForm();
        }
      },
      { deep: true },
    );
    // 步骤数量变化时守护选中行，避免详情弹窗指向越界步骤。
    watch(
      () => getSteps().length,
      (length) => {
        if (!length) {
          selectedStepIndex.value = -1;
          return;
        }
        if (selectedStepIndex.value < 0) {
          selectedStepIndex.value = 0;
          return;
        }
        if (selectedStepIndex.value >= length) {
          selectedStepIndex.value = length - 1;
        }
      },
    );
    // JSON Tab 与可视化 Tab 互切时的单向同步：离开 JSON 前不覆盖文本，
    // 进入 JSON 前以当前步骤数组为准刷新（与原用例编辑器行为一致）。
    watch(activeTab, (tab) => {
      if (tab === 'json') {
        syncStepsTextFromForm();
      }
    });
  }

  return {
    // 状态
    activeTab,
    selectedStepIndex,
    stepsText,
    showStepDetailDialog,
    currentStep,
    stepDetailTitle,
    // JSON 同步
    syncStepsTextFromForm,
    applyStepsTextToForm,
    flushJsonToSteps,
    // 表格交互
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
    // 摘要
    summarizeStepParams,
    describeStepTarget,
    stepNeedsTarget,
    // 生命周期
    resetUi,
    watchSteps,
  };
}
