export function createEmptyCase() {
  return {
    webCaseId: undefined,
    caseName: '新增 Web 用例',
    projectId: undefined,
    moduleId: undefined,
    startUrl: '',
    browserName: 'chromium',
    headless: false,
    runtimeSettings: {},
    notes: '',
    status: 2,
    remark: '',
    steps: [],
  };
}

export function normalizeCase(data = {}) {
  const base = createEmptyCase();
  return {
    ...base,
    ...data,
    webCaseId: normalizeIdValue(data.webCaseId || data.web_case_id),
    caseName: data.caseName || data.case_name || base.caseName,
    projectId: normalizeIdValue(data.projectId || data.project_id),
    moduleId: normalizeIdValue(data.moduleId || data.module_id),
    startUrl: data.startUrl || data.start_url || '',
    browserName: data.browserName || data.browser_name || base.browserName,
    headless: data.headless ?? base.headless,
    runtimeSettings: isPlainObject(data.runtimeSettings || data.runtime_settings)
      ? cloneData(data.runtimeSettings || data.runtime_settings)
      : {},
    notes: data.notes || '',
    status: data.status ?? 2,
    remark: data.remark || '',
    steps: Array.isArray(data.steps)
      ? data.steps.map((step, index) => normalizeStep(step, index))
      : [],
  };
}
