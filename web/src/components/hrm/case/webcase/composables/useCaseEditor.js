import { computed, ref, toRaw, watch } from 'vue';
import { updateWebCase, addWebCase, getWebCase } from '@/api/hrm/web_case.js';

/**
 * 用例编辑域组合式逻辑。
 * @param {Object} options 依赖项
 * @returns {Object} 用例编辑相关状态、计算属性与方法
 */
export function useCaseEditorManager(options) {
  const {
    ElMessage,
    loading,
    projectOptions,
    moduleOptions,
    actionOptions,
    cloneData,
    isPlainObject,
    isSameId,
    normalizeIdValue,
    safeJsonStringify,
    syncCaseOptions,
    refreshCaseTab,
    loadAllCaseOptions,
  } = options;

  const showCaseDialog = ref(false);
  const showStepDetailDialog = ref(false);
  const caseEditorTab = ref('visual');
  const selectedStepIndex = ref(-1);
  const stepEditingCell = ref({ index: -1, field: '' });
  const stepsText = ref('[]');

  function createDefaultContext() {
    return {
      pageUrl: '',
      frameUrl: '',
      frameChain: [],
      shadowChain: [],
    };
  }

  function extractLocatorMeta(locatorValue) {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    const result = {};
    for (const key of ['nth', 'index', 'targetIndex', 'target_index']) {
      const raw = value[key];
      if (raw === undefined || raw === null || raw === '') continue;
      const parsed = Number(raw);
      if (Number.isInteger(parsed) && parsed >= 0) {
        if (key === 'target_index') result.targetIndex = parsed;
        else result[key] = parsed;
        break;
      }
    }
    const rawMatchCount = value.matchCount ?? value.match_count;
    if (rawMatchCount !== undefined && rawMatchCount !== null && rawMatchCount !== '') {
      const parsedMatchCount = Number(rawMatchCount);
      if (Number.isInteger(parsedMatchCount) && parsedMatchCount >= 0) {
        result.matchCount = parsedMatchCount;
      }
    }
    const uniqueness = `${value.uniqueness ?? ''}`.trim();
    if (uniqueness) {
      result.uniqueness = uniqueness;
    }
    return result;
  }

  function getActionLabel(actionType) {
    return actionOptions.find((item) => item.value === actionType)?.label || actionType || '未设置';
  }

  const filteredCaseModules = computed(() => {
    if (!form.value.projectId) return moduleOptions.value;
    return moduleOptions.value.filter((item) => isSameId(item.projectId, form.value.projectId));
  });

  const caseDialogTitle = computed(() => `${form.value.webCaseId ? '编辑' : '新增'} Web 用例`);
  const currentStep = computed(() => form.value.steps[selectedStepIndex.value] || null);

  function describeLocator(locator) {
    if (!locator) return '未设置定位器';
    const resolvedIndex = resolveLocatorIndex(locator.locatorValue);
    const indexSuffix = resolvedIndex === null ? '' : ` / nth=${resolvedIndex}`;
    if (locator.locatorType === 'role') {
      return `role=${locator.locatorValue.role || '-'} / name=${locator.locatorValue.name || '-'}${indexSuffix}`;
    }
    if (['label', 'placeholder', 'text'].includes(locator.locatorType)) {
      return `${locator.locatorType}=${locator.locatorValue.text || '-'}${indexSuffix}`;
    }
    if (locator.locatorType === 'test_id') {
      return `testId=${locator.locatorValue.testId || '-'}${indexSuffix}`;
    }
    if (locator.locatorType === 'id') {
      return `id=${locator.locatorValue.id || '-'}${indexSuffix}`;
    }
    if (locator.locatorType === 'name') {
      return `name=${locator.locatorValue.name || '-'}${indexSuffix}`;
    }
    return `${locator.locatorType}=${locator.locatorValue.selector || '-'}${indexSuffix}`;
  }

  function syncStepsTextFromForm() {
    stepsText.value = safeJsonStringify(
      form.value.steps.map((step, index) => prepareStepForSubmit(step, index + 1))
    );
  }

  function applyStepsTextToForm(showSuccess = false) {
    let parsedSteps = [];
    try {
      parsedSteps = JSON.parse(stepsText.value || '[]');
    } catch (error) {
      ElMessage.error(`步骤 JSON 解析失败：${error.message}`);
      return false;
    }
    if (!Array.isArray(parsedSteps)) {
      ElMessage.error('步骤 JSON 必须是数组');
      return false;
    }
    form.value.steps = parsedSteps.map((step, index) => normalizeStep(step, index));
    selectedStepIndex.value = form.value.steps.length ? 0 : -1;
    if (showSuccess) {
      ElMessage.success('JSON 已同步到可视化编辑器');
    }
    return true;
  }

  function stripStepIdentity(step) {
    const cloned = normalizeStep(cloneData(step));
    cloned.stepId = undefined;
    if (cloned.targetSnapshot) {
      cloned.targetSnapshot.targetSnapshotId = undefined;
      cloned.targetSnapshot.locators = cloned.targetSnapshot.locators.map((locator, index) => ({
        ...locator,
        locatorSnapshotId: undefined,
        priority: index,
      }));
    }
    return cloned;
  }

  function selectStep(index) {
    selectedStepIndex.value = index;
  }

  function startStepCellEditing(index, field) {
    if (index < 0 || index >= form.value.steps.length) {
      return;
    }
    selectedStepIndex.value = index;
    stepEditingCell.value = {
      index,
      field: `${field || ''}`.trim(),
    };
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

  function handleStepRowClick(row) {
    const index = form.value.steps.indexOf(row);
    if (index === -1) {
      return;
    }
    selectedStepIndex.value = index;
    if (stepEditingCell.value.index !== index) {
      finishStepCellEditing();
    }
  }

  function getStepRowClassName({ row }) {
    return form.value.steps.indexOf(row) === selectedStepIndex.value ? 'selected-step-row' : '';
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
  }

  function updatePrimaryLocatorValue(step, key, value) {
    const locator = getPrimaryLocator(step);
    if (!locator) {
      return;
    }
    locator.locatorValue = normalizeLocatorValue(locator.locatorType, locator.locatorValue);
    locator.locatorValue[key] = value;
  }

  function isLocatorFilled(locator) {
    if (!locator || locator.enabled === false) return false;
    if (locator.locatorType === 'role') {
      return Boolean(locator.locatorValue.role);
    }
    if (['label', 'placeholder', 'text'].includes(locator.locatorType)) {
      return Boolean(locator.locatorValue.text);
    }
    if (locator.locatorType === 'test_id') {
      return Boolean(locator.locatorValue.testId);
    }
    if (locator.locatorType === 'id') {
      return Boolean(locator.locatorValue.id);
    }
    if (locator.locatorType === 'name') {
      return Boolean(locator.locatorValue.name);
    }
    return Boolean(locator.locatorValue.selector);
  }

  function getCaseValidationError() {
    if (!form.value.caseName?.trim()) return '用例名称不能为空';
    if (!form.value.steps.length) return '至少需要一个测试步骤';

    for (let index = 0; index < form.value.steps.length; index += 1) {
      const step = normalizeStep(form.value.steps[index], index);
      if (!step.stepName?.trim()) return `步骤${index + 1}名称不能为空`;
      if (!step.actionType) return `步骤${index + 1}缺少动作类型`;
      if (step.actionType === 'goto' && !step.params.url?.trim()) {
        return `步骤${index + 1}缺少跳转地址`;
      }
      if (
        step.actionType === 'set_window_size' &&
        (!Number.isFinite(Number(step.params.width)) ||
          Number(step.params.width) <= 0 ||
          !Number.isFinite(Number(step.params.height)) ||
          Number(step.params.height) <= 0)
      ) {
        return `步骤${index + 1}窗口尺寸必须为正整数`;
      }
      if (step.actionType === 'press' && !step.params.key?.trim()) {
        return `步骤${index + 1}缺少按键值`;
      }
      if (
        step.actionType === 'select_option' &&
        (!Array.isArray(step.params.values) || !step.params.values.length)
      ) {
        return `步骤${index + 1}至少需要一个下拉项值`;
      }
      if (['sleep', 'wait'].includes(step.actionType) && Number(step.params.waitMs ?? 0) < 0) {
        return `步骤${index + 1}等待时间不能小于0`;
      }
      if (
        ['assert_page_contains', 'assert_page_not_contains'].includes(step.actionType) &&
        !`${step.params.text ?? ''}`.trim()
      ) {
        return `步骤${index + 1}缺少页面断言文本`;
      }
      if (step.actionType === 'assert_title_contains' && !`${step.params.title ?? ''}`.trim()) {
        return `步骤${index + 1}缺少标题断言文本`;
      }
      if (step.actionType === 'assert_url_contains' && !`${step.params.urlPart ?? ''}`.trim()) {
        return `步骤${index + 1}缺少URL断言文本`;
      }
      if (
        ['assert_text_equals', 'assert_text_contains'].includes(step.actionType) &&
        !`${step.params.expected ?? ''}`.trim()
      ) {
        return `步骤${index + 1}缺少元素文本断言值`;
      }
      if (stepNeedsTarget(step.actionType)) {
        const locators = step.targetSnapshot?.locators || [];
        if (!locators.length) return `步骤${index + 1}至少需要一个定位器`;
        if (!locators.some(isLocatorFilled)) {
          return `步骤${index + 1}至少需要一个可用定位器`;
        }
      }
    }
    return '';
  }

  function prepareAssertionForSubmit(assertion) {
    const waitMs = Number(assertion.waitMs);
    return {
      assertType: assertion.assertType,
      expected: assertion.expected ?? '',
      operator: assertion.operator || undefined,
      actualSource: assertion.actualSource || undefined,
      enabled: assertion.enabled !== false,
      waitMs: Number.isFinite(waitMs) && waitMs > 0 ? Math.round(waitMs) : undefined,
      targetSnapshot: assertion.targetSnapshot
        ? prepareTargetSnapshotForSubmit(assertion.targetSnapshot)
        : undefined,
    };
  }

  function prepareLocatorForSubmit(locator, index) {
    return {
      locatorSnapshotId: locator.locatorSnapshotId,
      locatorType: locator.locatorType,
      locatorValue: normalizeLocatorValue(locator.locatorType, locator.locatorValue),
      priority: index,
      enabled: locator.enabled !== false,
    };
  }

  function prepareTargetSnapshotForSubmit(snapshot) {
    const normalized = normalizeTargetSnapshot(snapshot) || createDefaultTargetSnapshot();
    return {
      targetSnapshotId: normalized.targetSnapshotId,
      fingerprint: normalized.fingerprint || undefined,
      elementText: normalized.elementText || '',
      stableScore: Number(normalized.stableScore || 0),
      context: {
        pageUrl: normalized.context.pageUrl || '',
        frameUrl: normalized.context.frameUrl || '',
        frameChain: normalized.context.frameChain || [],
        shadowChain: normalized.context.shadowChain || [],
      },
      locators: normalized.locators.map((locator, index) =>
        prepareLocatorForSubmit(locator, index)
      ),
    };
  }

  function buildStepParamsForSubmit(step) {
    const thinkTimeMs = normalizeThinkTimeMs(step.params?.thinkTimeMs);
    const withThinkTime = (payload) => (thinkTimeMs > 0 ? { ...payload, thinkTimeMs } : payload);
    if (step.actionType === 'goto') {
      return withThinkTime({ url: step.params.url || '' });
    }
    if (step.actionType === 'window_maximize') {
      return withThinkTime({});
    }
    if (step.actionType === 'set_window_size') {
      return withThinkTime({
        width: Math.max(Math.round(Number(step.params?.width ?? 1920) || 1920), 1),
        height: Math.max(Math.round(Number(step.params?.height ?? 1080) || 1080), 1),
      });
    }
    if (step.actionType === 'fill') {
      return withThinkTime({ value: step.params.value ?? '' });
    }
    if (step.actionType === 'press') {
      return withThinkTime({ key: step.params.key || 'Enter' });
    }
    if (step.actionType === 'select_option') {
      return withThinkTime({
        values: Array.isArray(step.params.values)
          ? step.params.values.filter((item) => `${item}`.trim())
          : [],
      });
    }
    if (['sleep', 'wait'].includes(step.actionType)) {
      return withThinkTime({
        waitMs: Math.max(Math.round(Number(step.params?.waitMs ?? 0) || 0), 0),
      });
    }
    if (['assert_page_contains', 'assert_page_not_contains'].includes(step.actionType)) {
      return withThinkTime({ text: step.params?.text ?? '' });
    }
    if (step.actionType === 'assert_title_contains') {
      return withThinkTime({ title: step.params?.title ?? '' });
    }
    if (step.actionType === 'assert_url_contains') {
      return withThinkTime({ urlPart: step.params?.urlPart ?? '' });
    }
    if (['assert_text_equals', 'assert_text_contains'].includes(step.actionType)) {
      return withThinkTime({ expected: step.params?.expected ?? '' });
    }
    return withThinkTime({});
  }

  function prepareStepForSubmit(step, index) {
    const normalized = normalizeStep(step, index - 1);
    return {
      stepId: normalized.stepId,
      stepIndex: index,
      stepName: normalized.stepName?.trim() || `步骤${index}`,
      actionType: normalized.actionType,
      enabled: normalized.enabled !== false,
      timeoutMs: normalized.timeoutMs ?? undefined,
      continueOnFailure: Boolean(normalized.continueOnFailure),
      recordOrigin: normalized.recordOrigin || 'manual',
      elementId: normalized.elementId || undefined,
      params: buildStepParamsForSubmit(normalized),
      assertions: normalized.assertions.map(prepareAssertionForSubmit),
      rawEvent: normalized.rawEvent || {},
      targetSnapshot: stepNeedsTarget(normalized.actionType)
        ? prepareTargetSnapshotForSubmit(normalized.targetSnapshot)
        : null,
    };
  }

  function resetForm() {
    form.value = createEmptyCase();
    selectedStepIndex.value = -1;
    finishStepCellEditing();
    caseEditorTab.value = 'visual';
    syncStepsTextFromForm();
  }

  function handleAdd() {
    resetForm();
    showCaseDialog.value = true;
  }

  function handleEdit(row) {
    return getWebCase(row.webCaseId).then((response) => {
      form.value = normalizeCase(response.data || {});
      syncCaseOptions(form.value);
      selectedStepIndex.value = form.value.steps.length ? 0 : -1;
      syncStepsTextFromForm();
      caseEditorTab.value = 'visual';
      showCaseDialog.value = true;
    });
  }

  function saveCase() {
    if (caseEditorTab.value === 'json' && !applyStepsTextToForm()) {
      return;
    }
    const errorMessage = getCaseValidationError();
    if (errorMessage) {
      ElMessage.error(errorMessage);
      return;
    }

    loading.value.save = true;
    const rawForm = toRaw(form.value) || {};
    const payload = {
      ...rawForm,
      runtimeSettings: isPlainObject(rawForm.runtimeSettings)
        ? cloneData(rawForm.runtimeSettings)
        : {},
      steps: form.value.steps.map((step, index) => prepareStepForSubmit(step, index + 1)),
    };
    const request = payload.webCaseId ? updateWebCase(payload) : addWebCase(payload);
    request
      .then(async () => {
        ElMessage.success('保存成功');
        showCaseDialog.value = false;
        await refreshCaseTab();
        await loadAllCaseOptions(true);
      })
      .finally(() => {
        loading.value.save = false;
      });
  }

  watch(
    () => form.value.steps,
    () => {
      if (caseEditorTab.value !== 'json') {
        syncStepsTextFromForm();
      }
    },
    { deep: true }
  );

  watch(
    () => form.value.steps.length,
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
    }
  );

  watch(
    () => form.value.projectId,
    (projectId) => {
      if (!projectId) return;
      if (!filteredCaseModules.value.some((item) => isSameId(item.moduleId, form.value.moduleId))) {
        form.value.moduleId = undefined;
      }
    }
  );

  return {
    showCaseDialog,
    showStepDetailDialog,
    caseEditorTab,
    selectedStepIndex,
    stepsText,
    form,
    filteredCaseModules,
    caseDialogTitle,
    currentStep,
    getActionLabel,
    stepNeedsTarget,
    assertionNeedsTarget,
    describeStepTarget,
    summarizeStepParams,
    syncStepsTextFromForm,
    applyStepsTextToForm,
    startStepCellEditing,
    finishStepCellEditing,
    isStepCellEditing,
    openStepDetailByIndex,
    handleStepRowClick,
    getStepRowClassName,
    addStep,
    insertStep,
    copyStep,
    removeStep,
    moveStep,
    addLocator,
    moveLocator,
    setPrimaryLocator,
    removeLocator,
    addAssertion,
    removeAssertion,
    handleAssertionTypeChange,
    getAssertionLocatorList,
    getAssertionPrimaryLocator,
    updateAssertionPrimaryLocatorType,
    updateAssertionPrimaryLocatorValue,
    addAssertionLocator,
    moveAssertionLocator,
    setAssertionPrimaryLocator,
    removeAssertionLocator,
    handleStepActionTypeChange,
    getPrimaryLocator,
    updatePrimaryLocatorType,
    updatePrimaryLocatorValue,
    handleLocatorTypeChange,
    updateLocatorNth,
    isLocatorFilled,
    resetForm,
    handleAdd,
    handleEdit,
    saveCase,
    resolveLocatorIndex,
  };
}
