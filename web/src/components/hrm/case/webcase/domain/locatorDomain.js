export function normalizeLocator(locator = {}, index = 0) {
  const locatorType = locator.locatorType || locator.locator_type || 'css';
  return {
    locatorSnapshotId: locator.locatorSnapshotId || locator.locator_snapshot_id,
    locatorType,
    locatorValue: normalizeLocatorValue(locatorType, locator.locatorValue ?? locator.locator_value),
    priority: Number.isFinite(Number(locator.priority)) ? Number(locator.priority) : index,
    enabled: locator.enabled !== false,
  };
}

export function resolveLocatorIndex(locatorValue) {
  const meta = extractLocatorMeta(locatorValue);
  for (const key of ['nth', 'index', 'targetIndex']) {
    if (Number.isInteger(meta[key]) && meta[key] >= 0) {
      return meta[key];
    }
  }
  return null;
}

export function normalizeLocatorValue(locatorType, locatorValue) {
  const meta = extractLocatorMeta(locatorValue);
  if (locatorType === 'role') {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      role: value.role || '',
      name: value.name || '',
      exact: Boolean(value.exact),
      ...meta,
    };
  }
  if (['label', 'placeholder', 'text'].includes(locatorType)) {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      text: value.text || '',
      exact: Boolean(value.exact),
      ...meta,
    };
  }
  if (locatorType === 'test_id') {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      testId: value.testId || '',
      ...meta,
    };
  }
  if (locatorType === 'id') {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      id: value.id || '',
      ...meta,
    };
  }
  if (locatorType === 'name') {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      name: value.name || '',
      ...meta,
    };
  }
  if (['css', 'xpath'].includes(locatorType)) {
    if (typeof locatorValue === 'string') {
      return { selector: locatorValue, ...meta };
    }
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      selector: value.selector || '',
      ...meta,
    };
  }
  return isPlainObject(locatorValue) ? cloneData(locatorValue) : {};
}

export function createDefaultLocator(locatorType = 'css') {
  return {
    locatorSnapshotId: undefined,
    locatorType,
    locatorValue: normalizeLocatorValue(locatorType, {}),
    priority: 0,
    enabled: true,
  };
}

export function addLocator(step) {
  if (!step.targetSnapshot) {
    step.targetSnapshot = createDefaultTargetSnapshot();
  }
  if (!Array.isArray(step.targetSnapshot.locators)) {
    step.targetSnapshot.locators = [];
  }
  step.targetSnapshot.locators.push(createDefaultLocator());
}

export function moveLocator(step, index, direction) {
  if (!step?.targetSnapshot?.locators) return;
  const targetIndex = index + direction;
  if (targetIndex < 0 || targetIndex >= step.targetSnapshot.locators.length) {
    return;
  }
  const locators = [...step.targetSnapshot.locators];
  [locators[index], locators[targetIndex]] = [locators[targetIndex], locators[index]];
  step.targetSnapshot.locators = locators;
}

export function setPrimaryLocator(step, index) {
  if (!step?.targetSnapshot?.locators) return;
  if (index <= 0 || index >= step.targetSnapshot.locators.length) return;
  const locators = [...step.targetSnapshot.locators];
  const [preferred] = locators.splice(index, 1);
  locators.unshift(preferred);
  step.targetSnapshot.locators = locators;
}

export function removeLocator(step, index) {
  if (!step?.targetSnapshot?.locators) return;
  step.targetSnapshot.locators.splice(index, 1);
}

export function updateLocatorNth(locator, rawValue) {
  if (!locator) return;
  locator.locatorValue = normalizeLocatorValue(locator.locatorType, locator.locatorValue);
  delete locator.locatorValue.index;
  delete locator.locatorValue.targetIndex;
  delete locator.locatorValue.target_index;
  if (rawValue === undefined || rawValue === null || rawValue === '') {
    delete locator.locatorValue.nth;
    return;
  }
  const parsed = Number(rawValue);
  if (Number.isInteger(parsed) && parsed >= 0) {
    locator.locatorValue.nth = parsed;
    return;
  }
  delete locator.locatorValue.nth;
}

export function handleLocatorTypeChange(locator) {
  locator.locatorValue = normalizeLocatorValue(locator.locatorType, locator.locatorValue);
}
