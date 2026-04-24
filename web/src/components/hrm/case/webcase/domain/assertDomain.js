export function normalizeAssertion(assertion = {}) {
  return {
    assertType: assertion.assertType || assertion.assert_type || 'visible',
    expected: assertion.expected ?? '',
    operator: assertion.operator || '',
    actualSource: assertion.actualSource || assertion.actual_source || '',
    enabled: assertion.enabled !== false,
    waitMs: assertion.waitMs ?? assertion.wait_ms,
    targetSnapshot: normalizeTargetSnapshot(assertion.targetSnapshot || assertion.target_snapshot),
  };
}

export function createDefaultAssertion(assertType = 'visible') {
  return {
    assertType,
    expected: '',
    operator: '',
    actualSource: '',
    enabled: true,
    waitMs: undefined,
    targetSnapshot: null,
  };
}

export function assertionNeedsTarget(assertType) {
  return ['text_contains', 'text_equals', 'visible'].includes(`${assertType || ''}`.toLowerCase());
}

export function addAssertion(step) {
  step.assertions.push(createDefaultAssertion());
}

export function removeAssertion(step, index) {
  step.assertions.splice(index, 1);
}

export function handleAssertionTypeChange(assertion) {
  if (!assertionNeedsTarget(assertion?.assertType)) {
    return;
  }
  getAssertionLocatorList(assertion);
}

export function ensureAssertionTargetSnapshot(assertion) {
  if (!assertion?.targetSnapshot) {
    assertion.targetSnapshot = createDefaultTargetSnapshot();
  }
  if (!Array.isArray(assertion.targetSnapshot.locators)) {
    assertion.targetSnapshot.locators = [];
  }
  return assertion.targetSnapshot;
}

export function getAssertionLocatorList(assertion) {
  if (!assertionNeedsTarget(assertion?.assertType)) {
    return [];
  }
  const snapshot = ensureAssertionTargetSnapshot(assertion);
  if (!snapshot.locators.length) {
    snapshot.locators = [createDefaultLocator()];
  }
  return snapshot.locators;
}

export function getAssertionPrimaryLocator(assertion) {
  const locators = getAssertionLocatorList(assertion);
  return locators.find((item) => item.enabled !== false) || locators[0] || null;
}

export function updateAssertionPrimaryLocatorType(assertion, locatorType) {
  const locator = getAssertionPrimaryLocator(assertion);
  if (!locator) {
    return;
  }
  locator.locatorType = locatorType;
  locator.locatorValue = normalizeLocatorValue(locatorType, {});
}

export function updateAssertionPrimaryLocatorValue(assertion, key, value) {
  const locator = getAssertionPrimaryLocator(assertion);
  if (!locator) {
    return;
  }
  locator.locatorValue = normalizeLocatorValue(locator.locatorType, locator.locatorValue);
  locator.locatorValue[key] = value;
}

export function addAssertionLocator(assertion) {
  if (!assertionNeedsTarget(assertion?.assertType)) return;
  const snapshot = ensureAssertionTargetSnapshot(assertion);
  snapshot.locators.push(createDefaultLocator());
}

export function moveAssertionLocator(assertion, index, direction) {
  const locators = getAssertionLocatorList(assertion);
  const targetIndex = index + direction;
  if (targetIndex < 0 || targetIndex >= locators.length) return;
  [locators[index], locators[targetIndex]] = [locators[targetIndex], locators[index]];
}

export function setAssertionPrimaryLocator(assertion, index) {
  const locators = getAssertionLocatorList(assertion);
  if (index <= 0 || index >= locators.length) return;
  const [preferred] = locators.splice(index, 1);
  locators.unshift(preferred);
}

export function removeAssertionLocator(assertion, index) {
  const snapshot = ensureAssertionTargetSnapshot(assertion);
  if (!Array.isArray(snapshot.locators) || !snapshot.locators.length) return;
  snapshot.locators.splice(index, 1);
}
