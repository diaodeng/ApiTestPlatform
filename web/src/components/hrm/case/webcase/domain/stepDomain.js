import { normalizeAssertion } from '../domain/assertDomain.js';
import { normalizeThinkTimeMs } from '../utils/shared.js';

export function createDefaultStep(actionType = 'click') {
  return normalizeStep({
    actionType,
    stepName: getActionLabel(actionType),
    targetSnapshot: stepNeedsTarget(actionType) ? createDefaultTargetSnapshot() : null,
  });
}

export function normalizeStepParams(actionType, params) {
  const data = isPlainObject(params) ? cloneData(params) : {};
  const thinkTimeMs = normalizeThinkTimeMs(data.thinkTimeMs ?? data.think_time_ms);
  const waitMs = Number(data.waitMs ?? data.wait_ms ?? 0);
  if (actionType === 'goto') {
    return { url: data.url || '', thinkTimeMs };
  }
  if (actionType === 'window_maximize') {
    return { thinkTimeMs };
  }
  if (actionType === 'set_window_size') {
    const width = Number(
      data.width ??
        data.windowWidth ??
        data.window_width ??
        data.viewportWidth ??
        data.viewport_width
    );
    const height = Number(
      data.height ??
        data.windowHeight ??
        data.window_height ??
        data.viewportHeight ??
        data.viewport_height
    );
    return {
      width: Number.isFinite(width) && width > 0 ? Math.round(width) : 1920,
      height: Number.isFinite(height) && height > 0 ? Math.round(height) : 1080,
      thinkTimeMs,
    };
  }
  if (actionType === 'fill') {
    return { value: data.value ?? '', thinkTimeMs };
  }
  if (actionType === 'press') {
    return { key: data.key || 'Enter', thinkTimeMs };
  }
  if (actionType === 'select_option') {
    const values = Array.isArray(data.values) ? data.values : data.values ? [data.values] : [];
    return { values: values.map((item) => `${item}`), thinkTimeMs };
  }
  if (['sleep', 'wait'].includes(actionType)) {
    return {
      waitMs: Number.isFinite(waitMs) && waitMs >= 0 ? Math.round(waitMs) : 0,
      thinkTimeMs,
    };
  }
  if (['assert_page_contains', 'assert_page_not_contains'].includes(actionType)) {
    return { text: data.text ?? data.expected ?? '', thinkTimeMs };
  }
  if (actionType === 'assert_title_contains') {
    return {
      title: data.title ?? data.text ?? data.expected ?? '',
      thinkTimeMs,
    };
  }
  if (actionType === 'assert_url_contains') {
    return {
      urlPart: data.urlPart ?? data.url_part ?? data.text ?? data.expected ?? '',
      thinkTimeMs,
    };
  }
  if (['assert_text_equals', 'assert_text_contains'].includes(actionType)) {
    return { expected: data.expected ?? data.text ?? '', thinkTimeMs };
  }
  return { thinkTimeMs };
}

export function stepNeedsTarget(actionType) {
  return ![
    'goto',
    'window_maximize',
    'set_window_size',
    'sleep',
    'wait',
    'assert_page_contains',
    'assert_page_not_contains',
    'assert_title_contains',
    'assert_url_contains',
  ].includes(actionType);
}

export function summarizeStepParams(step) {
  if (!step) return '-';
  const thinkTimeMs = normalizeThinkTimeMs(step.params?.thinkTimeMs);
  const appendThinkTime = (text) =>
    thinkTimeMs > 0 ? `${text || '-'} / 思考${thinkTimeMs}ms` : text || '-';
  if (step.actionType === 'goto') {
    return appendThinkTime(step.params?.url || '-');
  }
  if (step.actionType === 'window_maximize') {
    return appendThinkTime('最大化窗口');
  }
  if (step.actionType === 'set_window_size') {
    const width = Number(step.params?.width ?? 0) || 0;
    const height = Number(step.params?.height ?? 0) || 0;
    return appendThinkTime(width > 0 && height > 0 ? `${width}x${height}` : '自定义窗口尺寸');
  }
  if (step.actionType === 'fill') {
    return appendThinkTime(step.params?.value || '-');
  }
  if (step.actionType === 'press') {
    return appendThinkTime(step.params?.key || '-');
  }
  if (step.actionType === 'select_option') {
    const valuesText =
      Array.isArray(step.params?.values) && step.params.values.length
        ? step.params.values.join(', ')
        : '-';
    return appendThinkTime(valuesText);
  }
  if (['sleep', 'wait'].includes(step.actionType)) {
    return appendThinkTime(`${Number(step.params?.waitMs ?? 0) || 0}ms`);
  }
  if (step.actionType === 'assert_page_contains') {
    return appendThinkTime(`页面包含：${step.params?.text || '-'}`);
  }
  if (step.actionType === 'assert_page_not_contains') {
    return appendThinkTime(`页面不含：${step.params?.text || '-'}`);
  }
  if (step.actionType === 'assert_title_contains') {
    return appendThinkTime(`标题包含：${step.params?.title || '-'}`);
  }
  if (step.actionType === 'assert_url_contains') {
    return appendThinkTime(`URL包含：${step.params?.urlPart || '-'}`);
  }
  if (step.actionType === 'assert_text_equals') {
    return appendThinkTime(`文本等于：${step.params?.expected || '-'}`);
  }
  if (step.actionType === 'assert_text_contains') {
    return appendThinkTime(`文本包含：${step.params?.expected || '-'}`);
  }
  return appendThinkTime('-');
}

export function normalizeStep(step = {}, index = 0) {
  const actionType = step.actionType || step.action_type || 'click';
  const targetSnapshot = normalizeTargetSnapshot(step.targetSnapshot || step.target_snapshot);
  return {
    stepId: step.stepId || step.step_id,
    stepIndex: Number(step.stepIndex ?? step.step_index ?? index + 1),
    stepName: step.stepName || step.step_name || `${getActionLabel(actionType)} ${index + 1}`,
    actionType,
    enabled: step.enabled !== false,
    timeoutMs: step.timeoutMs ?? step.timeout_ms,
    continueOnFailure: Boolean(step.continueOnFailure || step.continue_on_failure),
    recordOrigin: step.recordOrigin || step.record_origin || 'manual',
    elementId: step.elementId || step.element_id,
    params: normalizeStepParams(actionType, step.params),
    assertions: Array.isArray(step.assertions) ? step.assertions.map(normalizeAssertion) : [],
    rawEvent: isPlainObject(step.rawEvent || step.raw_event)
      ? cloneData(step.rawEvent || step.raw_event)
      : {},
    targetSnapshot: stepNeedsTarget(actionType)
      ? targetSnapshot || createDefaultTargetSnapshot()
      : targetSnapshot,
  };
}

export function describeStepTarget(step) {
  if (!stepNeedsTarget(step.actionType)) {
    if (step.actionType === 'goto') return step.params?.url || '页面跳转';
    if (step.actionType === 'window_maximize') return '窗口最大化';
    if (step.actionType === 'set_window_size') {
      const width = Number(step.params?.width ?? 0) || 0;
      const height = Number(step.params?.height ?? 0) || 0;
      return width > 0 && height > 0 ? `窗口尺寸 ${width}x${height}` : '窗口尺寸调整';
    }
    if (['sleep', 'wait'].includes(step.actionType)) {
      return `等待 ${Number(step.params?.waitMs ?? 0) || 0}ms`;
    }
    if (step.actionType === 'assert_page_contains') {
      return `页面包含 ${step.params?.text || '-'}`;
    }
    if (step.actionType === 'assert_page_not_contains') {
      return `页面不包含 ${step.params?.text || '-'}`;
    }
    if (step.actionType === 'assert_title_contains') {
      return `标题包含 ${step.params?.title || '-'}`;
    }
    if (step.actionType === 'assert_url_contains') {
      return `URL包含 ${step.params?.urlPart || '-'}`;
    }
    return '页面级动作';
  }
  const firstLocator =
    step.targetSnapshot?.locators?.find((item) => item.enabled !== false) ||
    step.targetSnapshot?.locators?.[0];
  const locatorText = firstLocator ? describeLocator(firstLocator) : '未设置定位器';
  const elementText = step.targetSnapshot?.elementText
    ? ` / 文本=${step.targetSnapshot.elementText}`
    : '';
  return `${locatorText}${elementText}`;
}

export function addStep(actionType = 'click') {
  form.value.steps.push(createDefaultStep(actionType));
  selectedStepIndex.value = form.value.steps.length - 1;
  finishStepCellEditing();
}

export function insertStep(index, actionType = 'click') {
  const insertIndex = Math.max(0, Math.min(Number(index), form.value.steps.length));
  form.value.steps.splice(insertIndex, 0, createDefaultStep(actionType));
  selectedStepIndex.value = insertIndex;
  finishStepCellEditing();
}

export function copyStep(index) {
  const source = form.value.steps[index];
  if (!source) return;
  const copied = stripStepIdentity(source);
  copied.stepName = `${copied.stepName} - 副本`;
  form.value.steps.splice(index + 1, 0, copied);
  selectedStepIndex.value = index + 1;
}

export function removeStep(index) {
  form.value.steps.splice(index, 1);
  if (!form.value.steps.length) {
    selectedStepIndex.value = -1;
    finishStepCellEditing();
    return;
  }
  selectedStepIndex.value = Math.min(index, form.value.steps.length - 1);
  finishStepCellEditing();
}

export function moveStep(index, direction) {
  const targetIndex = index + direction;
  if (targetIndex < 0 || targetIndex >= form.value.steps.length) return;
  const steps = [...form.value.steps];
  [steps[index], steps[targetIndex]] = [steps[targetIndex], steps[index]];
  form.value.steps = steps;
  selectedStepIndex.value = targetIndex;
  finishStepCellEditing();
}
