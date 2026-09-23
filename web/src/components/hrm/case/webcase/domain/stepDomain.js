import { normalizeAssertion } from '../domain/assertDomain.js';
import { cloneData, isPlainObject, normalizeIdValue, normalizeThinkTimeMs } from '../utils/shared.js';
import { actionOptions } from '../utils/shared.js';
import { createDefaultTargetSnapshot, normalizeTargetSnapshot } from './snapshotDomain.js';
import { describeLocator } from './locatorDomain.js';

export function getActionLabel(actionType) {
  return actionOptions.find((item) => item.value === actionType)?.label || actionType || '未设置';
}

/**
 * 生成前端新增步骤使用的稳定字符串 ID。
 * 不把后端 BIGINT 主键转换为 Number，缺少后端 ID 时才生成本地身份。
 * @param {string} actionType 动作类型
 * @param {number} index 步骤位置
 * @returns {string} 步骤 ID
 */
function createLocalStepId(actionType, index = 0) {
  const suffix = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  return `step-${actionType || 'action'}-${index + 1}-${suffix}`;
}

const SCREENSHOT_EVIDENCE_TYPES = [
  'checkpoint_screenshot',
  'before_screenshot',
  'after_screenshot',
];

function normalizeMaskSelectors(value) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => `${item ?? ''}`.trim()).filter(Boolean);
}

function createDefaultScreenshotParams(stepName = '') {
  const fallbackLabel = `${stepName || '截图 / 采集证据'}`.trim();
  return {
    evidenceType: 'checkpoint_screenshot',
    evidenceKey: '',
    label: fallbackLabel,
    required: false,
    fullPage: false,
    maskSelectors: [],
    note: '',
    waitMs: 0,
    thinkTimeMs: 0,
  };
}

/**
 * 标准化截图证据参数，兼容后端下划线字段和历史 step_screenshot 类型。
 * @param {Record<string, any>} data 原始参数
 * @param {string} stepName 步骤名称
 * @returns {Record<string, any>} 截图参数
 */
function normalizeScreenshotParams(data, stepName = '') {
  const defaults = createDefaultScreenshotParams(stepName);
  const rawType = `${data.evidenceType ?? data.evidence_type ?? ''}`.trim();
  const evidenceType = rawType === 'step_screenshot' || !SCREENSHOT_EVIDENCE_TYPES.includes(rawType)
    ? defaults.evidenceType
    : rawType;
  const rawWaitMs = Number(data.waitMs ?? data.wait_ms ?? 0);
  return {
    ...defaults,
    evidenceType,
    evidenceKey: `${data.evidenceKey ?? data.evidence_key ?? ''}`.trim(),
    label: `${data.label ?? defaults.label}`.trim() || defaults.label,
    required: data.required === true || data.required === 'true',
    fullPage: data.fullPage === true || data.full_page === true || data.fullPage === 'true',
    maskSelectors: normalizeMaskSelectors(data.maskSelectors ?? data.mask_selectors),
    note: `${data.note ?? ''}`.trim(),
    waitMs: Number.isFinite(rawWaitMs) && rawWaitMs >= 0 ? Math.round(rawWaitMs) : 0,
  };
}

export function getScreenshotEvidenceTypes() {
  return SCREENSHOT_EVIDENCE_TYPES.map((value) => ({
    value,
    label: {
      checkpoint_screenshot: '检查点截图',
      before_screenshot: '修改前截图',
      after_screenshot: '修改后截图',
    }[value],
  }));
}

export function createDefaultStep(actionType = 'click') {
  const stepId = createLocalStepId(actionType);
  return normalizeStep({
    stepId,
    actionType,
    stepName: getActionLabel(actionType),
    targetSnapshot: stepNeedsTarget(actionType) ? createDefaultTargetSnapshot() : null,
  });
}

export function normalizeStepParams(actionType, params, stepName = '') {
  const data = isPlainObject(params) ? cloneData(params) : {};
  const thinkTimeMs = normalizeThinkTimeMs(data.thinkTimeMs ?? data.think_time_ms);
  const waitMs = Number(data.waitMs ?? data.wait_ms ?? 0);
  if (actionType === 'capture_screenshot') {
    const evidenceKey = `${data.evidenceKey ?? data.evidence_key ?? ''}`.trim();
    return {
      ...normalizeScreenshotParams(data, stepName),
      evidenceKey,
      thinkTimeMs,
    };
  }
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
  if (actionType === 'upload_file') {
    const resourceIds = Array.isArray(data.resourceIds)
      ? data.resourceIds
      : data.resourceIds
        ? [data.resourceIds]
        : [];
    const fileNames = Array.isArray(data.fileNames) ? data.fileNames : data.fileNames ? [data.fileNames] : [];
    return {
      fileKey: `${data.fileKey ?? data.file_key ?? ''}`.trim(),
      resourceIds: resourceIds
        .map((item) => `${item ?? ''}`.trim())
        .filter(Boolean),
      // Agent 受控上传根目录内的相对路径；与 resourceIds 二选一，运行时资源绑定优先
      agentPath: `${data.agentPath ?? data.agent_path ?? ''}`.trim(),
      // 录制样本文件名，仅编辑占位展示，不参与回放
      fileNames: fileNames.map((item) => `${item ?? ''}`.trim()).filter(Boolean),
      multiple: data.multiple === true || data.multiple === 'true',
      thinkTimeMs,
    };
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
    'capture_screenshot',
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
  if (step.actionType === 'upload_file') {
    const fileKey = `${step.params?.fileKey || ''}`.trim();
    const resourceCount = Array.isArray(step.params?.resourceIds)
      ? step.params.resourceIds.filter((item) => `${item ?? ''}`.trim()).length
      : 0;
    const agentPath = `${step.params?.agentPath || ''}`.trim();
    // 展示优先级：资源绑定 > Agent 目录文件 > 录制样本文件名占位
    let sourceText;
    if (resourceCount > 0) {
      sourceText = `${resourceCount}个资源`;
    } else if (agentPath) {
      sourceText = `Agent目录：${agentPath}`;
    } else {
      const fileNames = Array.isArray(step.params?.fileNames) ? step.params.fileNames : [];
      sourceText = fileNames.length ? `待绑定（样本：${fileNames.join('、')}）` : '未绑定文件';
    }
    const modeText = step.params?.multiple === true ? '多文件' : '单文件';
    return appendThinkTime(`${fileKey || '未设置资源键'} / ${modeText} / ${sourceText}`);
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
  const stepName = step.stepName || step.step_name || `${getActionLabel(actionType)} ${index + 1}`;
  const targetSnapshot = normalizeTargetSnapshot(step.targetSnapshot || step.target_snapshot);
  return {
    // 后端 BIGINT ID 只转为字符串，不经过 Number，缺少 ID 时生成一次本地稳定身份。
    stepId: normalizeIdValue(step.stepId ?? step.step_id) || createLocalStepId(actionType, index),
    stepIndex: Number(step.stepIndex ?? step.step_index ?? index + 1),
    stepName,
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
