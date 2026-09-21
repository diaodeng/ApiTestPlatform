import { computed, ref, toRaw, watch } from "vue";

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
        syncCaseOptions,
        refreshCaseTab,
        loadAllCaseOptions,
        getWebCase,
        addWebCase,
        updateWebCase,
    } = options;

    const showCaseDialog = ref(false);
    const form = ref(createEmptyCase());

    function createDefaultContext() {
        return {
            pageUrl: "",
            frameUrl: "",
            frameChain: [],
            shadowChain: [],
        };
    }

    function extractLocatorMeta(locatorValue) {
        const value = isPlainObject(locatorValue) ? locatorValue : {};
        const result = {};
        for (const key of ["nth", "index", "targetIndex", "target_index"]) {
            const raw = value[key];
            if (raw === undefined || raw === null || raw === "") continue;
            const parsed = Number(raw);
            if (Number.isInteger(parsed) && parsed >= 0) {
                if (key === "target_index") result.targetIndex = parsed;
                else result[key] = parsed;
                break;
            }
        }
        const rawMatchCount = value.matchCount ?? value.match_count;
        if (
            rawMatchCount !== undefined &&
            rawMatchCount !== null &&
            rawMatchCount !== ""
        ) {
            const parsedMatchCount = Number(rawMatchCount);
            if (Number.isInteger(parsedMatchCount) && parsedMatchCount >= 0) {
                result.matchCount = parsedMatchCount;
            }
        }
        const uniqueness = `${value.uniqueness ?? ""}`.trim();
        if (uniqueness) {
            result.uniqueness = uniqueness;
        }
        return result;
    }

    function resolveLocatorIndex(locatorValue) {
        const meta = extractLocatorMeta(locatorValue);
        for (const key of ["nth", "index", "targetIndex"]) {
            if (Number.isInteger(meta[key]) && meta[key] >= 0) {
                return meta[key];
            }
        }
        return null;
    }

    function normalizeLocatorValue(locatorType, locatorValue) {
        const meta = extractLocatorMeta(locatorValue);
        if (locatorType === "role") {
            const value = isPlainObject(locatorValue) ? locatorValue : {};
            return {
                role: value.role || "",
                name: value.name || "",
                exact: Boolean(value.exact),
                ...meta,
            };
        }
        if (["label", "placeholder", "text"].includes(locatorType)) {
            const value = isPlainObject(locatorValue) ? locatorValue : {};
            return {
                text: value.text || "",
                exact: Boolean(value.exact),
                ...meta,
            };
        }
        if (locatorType === "test_id") {
            const value = isPlainObject(locatorValue) ? locatorValue : {};
            return {
                testId: value.testId || "",
                ...meta,
            };
        }
        if (locatorType === "id") {
            const value = isPlainObject(locatorValue) ? locatorValue : {};
            return {
                id: value.id || "",
                ...meta,
            };
        }
        if (locatorType === "name") {
            const value = isPlainObject(locatorValue) ? locatorValue : {};
            return {
                name: value.name || "",
                ...meta,
            };
        }
        if (["css", "xpath"].includes(locatorType)) {
            if (typeof locatorValue === "string") {
                return { selector: locatorValue, ...meta };
            }
            const value = isPlainObject(locatorValue) ? locatorValue : {};
            return {
                selector: value.selector || "",
                ...meta,
            };
        }
        return isPlainObject(locatorValue) ? cloneData(locatorValue) : {};
    }

    function createDefaultLocator(locatorType = "css") {
        return {
            locatorSnapshotId: undefined,
            locatorType,
            locatorValue: normalizeLocatorValue(locatorType, {}),
            priority: 0,
            enabled: true,
        };
    }

    function normalizeLocator(locator = {}, index = 0) {
        const locatorType = locator.locatorType || locator.locator_type || "css";
        return {
            locatorSnapshotId:
                locator.locatorSnapshotId || locator.locator_snapshot_id,
            locatorType,
            locatorValue: normalizeLocatorValue(
                locatorType,
                locator.locatorValue ?? locator.locator_value,
            ),
            priority: Number.isFinite(Number(locator.priority))
                ? Number(locator.priority)
                : index,
            enabled: locator.enabled !== false,
        };
    }

    function createDefaultTargetSnapshot() {
        return {
            targetSnapshotId: undefined,
            fingerprint: "",
            elementText: "",
            stableScore: 0,
            context: createDefaultContext(),
            locators: [createDefaultLocator()],
        };
    }

    function normalizeTargetSnapshot(snapshot) {
        if (!snapshot) {
            return null;
        }
        const context = isPlainObject(snapshot.context) ? snapshot.context : {};
        return {
            targetSnapshotId:
                snapshot.targetSnapshotId || snapshot.target_snapshot_id,
            fingerprint: snapshot.fingerprint || "",
            elementText: snapshot.elementText || snapshot.element_text || "",
            stableScore: Number(snapshot.stableScore ?? snapshot.stable_score ?? 0),
            context: {
                pageUrl: context.pageUrl || context.page_url || "",
                frameUrl: context.frameUrl || context.frame_url || "",
                frameChain: Array.isArray(context.frameChain || context.frame_chain)
                    ? cloneData(context.frameChain || context.frame_chain)
                    : [],
                shadowChain: Array.isArray(
                    context.shadowChain || context.shadow_chain,
                )
                    ? cloneData(context.shadowChain || context.shadow_chain)
                    : [],
            },
            locators: Array.isArray(snapshot.locators)
                ? snapshot.locators.map((item, index) =>
                      normalizeLocator(item, index),
                  )
                : [],
        };
    }

    function createDefaultAssertion(assertType = "visible") {
        return {
            assertType,
            expected: "",
            operator: "",
            actualSource: "",
            enabled: true,
            waitMs: undefined,
            targetSnapshot: null,
        };
    }

    function assertionNeedsTarget(assertType) {
        return ["text_contains", "text_equals", "visible"].includes(
            `${assertType || ""}`.toLowerCase(),
        );
    }

    function normalizeAssertion(assertion = {}) {
        return {
            assertType: assertion.assertType || assertion.assert_type || "visible",
            expected: assertion.expected ?? "",
            operator: assertion.operator || "",
            actualSource: assertion.actualSource || assertion.actual_source || "",
            enabled: assertion.enabled !== false,
            waitMs: assertion.waitMs ?? assertion.wait_ms,
            targetSnapshot: normalizeTargetSnapshot(
                assertion.targetSnapshot || assertion.target_snapshot,
            ),
        };
    }

    function stepNeedsTarget(actionType) {
        return ![
            "goto",
            "window_maximize",
            "set_window_size",
            "sleep",
            "wait",
            "assert_page_contains",
            "assert_page_not_contains",
            "assert_title_contains",
            "assert_url_contains",
        ].includes(actionType);
    }

    function getActionLabel(actionType) {
        return (
            actionOptions.find((item) => item.value === actionType)?.label ||
            actionType ||
            "未设置"
        );
    }

    function normalizeThinkTimeMs(value) {
        const parsed = Number(value);
        if (!Number.isFinite(parsed) || parsed < 0) return 0;
        return Math.round(parsed);
    }

    function normalizeStepParams(actionType, params) {
        const data = isPlainObject(params) ? cloneData(params) : {};
        const thinkTimeMs = normalizeThinkTimeMs(
            data.thinkTimeMs ?? data.think_time_ms,
        );
        const waitMs = Number(data.waitMs ?? data.wait_ms ?? 0);
        if (actionType === "goto") {
            return { url: data.url || "", thinkTimeMs };
        }
        if (actionType === "window_maximize") {
            return { thinkTimeMs };
        }
        if (actionType === "set_window_size") {
            const width = Number(
                data.width ??
                    data.windowWidth ??
                    data.window_width ??
                    data.viewportWidth ??
                    data.viewport_width,
            );
            const height = Number(
                data.height ??
                    data.windowHeight ??
                    data.window_height ??
                    data.viewportHeight ??
                    data.viewport_height,
            );
            return {
                width:
                    Number.isFinite(width) && width > 0 ? Math.round(width) : 1920,
                height:
                    Number.isFinite(height) && height > 0
                        ? Math.round(height)
                        : 1080,
                thinkTimeMs,
            };
        }
        if (actionType === "fill") {
            return { value: data.value ?? "", thinkTimeMs };
        }
        if (actionType === "upload_file") {
            const resourceIds = Array.isArray(data.resourceIds)
                ? data.resourceIds
                : data.resourceIds
                  ? [data.resourceIds]
                  : [];
            return {
                fileKey: `${data.fileKey ?? data.file_key ?? ""}`.trim(),
                resourceIds: resourceIds
                    .map((item) => `${item ?? ""}`.trim())
                    .filter(Boolean),
                multiple: data.multiple === true || data.multiple === "true",
                thinkTimeMs,
            };
        }
        if (actionType === "press") {
            return { key: data.key || "Enter", thinkTimeMs };
        }
        if (actionType === "select_option") {
            const values = Array.isArray(data.values)
                ? data.values
                : data.values
                  ? [data.values]
                  : [];
            return { values: values.map((item) => `${item}`), thinkTimeMs };
        }
        if (["sleep", "wait"].includes(actionType)) {
            return {
                waitMs:
                    Number.isFinite(waitMs) && waitMs >= 0
                        ? Math.round(waitMs)
                        : 0,
                thinkTimeMs,
            };
        }
        if (
            ["assert_page_contains", "assert_page_not_contains"].includes(actionType)
        ) {
            return { text: data.text ?? data.expected ?? "", thinkTimeMs };
        }
        if (actionType === "assert_title_contains") {
            return {
                title: data.title ?? data.text ?? data.expected ?? "",
                thinkTimeMs,
            };
        }
        if (actionType === "assert_url_contains") {
            return {
                urlPart:
                    data.urlPart ??
                    data.url_part ??
                    data.text ??
                    data.expected ??
                    "",
                thinkTimeMs,
            };
        }
        if (["assert_text_equals", "assert_text_contains"].includes(actionType)) {
            return { expected: data.expected ?? data.text ?? "", thinkTimeMs };
        }
        return { thinkTimeMs };
    }

    function normalizeStep(step = {}, index = 0) {
        const actionType = step.actionType || step.action_type || "click";
        const targetSnapshot = normalizeTargetSnapshot(
            step.targetSnapshot || step.target_snapshot,
        );
        return {
            stepId: step.stepId || step.step_id,
            stepIndex: Number(step.stepIndex ?? step.step_index ?? index + 1),
            stepName:
                step.stepName ||
                step.step_name ||
                `${getActionLabel(actionType)} ${index + 1}`,
            actionType,
            enabled: step.enabled !== false,
            timeoutMs: step.timeoutMs ?? step.timeout_ms,
            continueOnFailure: Boolean(
                step.continueOnFailure || step.continue_on_failure,
            ),
            recordOrigin: step.recordOrigin || step.record_origin || "manual",
            elementId: step.elementId || step.element_id,
            params: normalizeStepParams(actionType, step.params),
            assertions: Array.isArray(step.assertions)
                ? step.assertions.map(normalizeAssertion)
                : [],
            rawEvent: isPlainObject(step.rawEvent || step.raw_event)
                ? cloneData(step.rawEvent || step.raw_event)
                : {},
            targetSnapshot: stepNeedsTarget(actionType)
                ? targetSnapshot || createDefaultTargetSnapshot()
                : targetSnapshot,
        };
    }

    function createEmptyCase() {
        return {
            webCaseId: undefined,
            caseName: "新增 Web 用例",
            projectId: undefined,
            moduleId: undefined,
            startUrl: "",
            browserName: "chromium",
            headless: false,
            runtimeSettings: {},
            notes: "",
            status: 2,
            remark: "",
            steps: [],
        };
    }

    function normalizeCase(data = {}) {
        const base = createEmptyCase();
        return {
            ...base,
            ...data,
            webCaseId: normalizeIdValue(data.webCaseId || data.web_case_id),
            caseName: data.caseName || data.case_name || base.caseName,
            projectId: normalizeIdValue(data.projectId || data.project_id),
            moduleId: normalizeIdValue(data.moduleId || data.module_id),
            startUrl: data.startUrl || data.start_url || "",
            browserName:
                data.browserName || data.browser_name || base.browserName,
            headless: data.headless ?? base.headless,
            runtimeSettings: isPlainObject(
                data.runtimeSettings || data.runtime_settings,
            )
                ? cloneData(data.runtimeSettings || data.runtime_settings)
                : {},
            notes: data.notes || "",
            status: data.status ?? 2,
            remark: data.remark || "",
            steps: Array.isArray(data.steps)
                ? data.steps.map((step, index) => normalizeStep(step, index))
                : [],
        };
    }

    const filteredCaseModules = computed(() => {
        if (!form.value.projectId) return moduleOptions.value;
        return moduleOptions.value.filter((item) =>
            isSameId(item.projectId, form.value.projectId),
        );
    });

    const caseDialogTitle = computed(
        () => `${form.value.webCaseId ? "编辑" : "新增"} Web 用例`,
    );

    function getCaseValidationError() {
        if (!form.value.caseName?.trim()) return "用例名称不能为空";
        if (!form.value.steps.length) return "至少需要一个测试步骤";

        for (let index = 0; index < form.value.steps.length; index += 1) {
            const step = normalizeStep(form.value.steps[index], index);
            if (!step.stepName?.trim()) return `步骤${index + 1}名称不能为空`;
            if (!step.actionType) return `步骤${index + 1}缺少动作类型`;
            if (step.actionType === "goto" && !step.params.url?.trim()) {
                return `步骤${index + 1}缺少跳转地址`;
            }
            if (
                step.actionType === "set_window_size" &&
                (!Number.isFinite(Number(step.params.width)) ||
                    Number(step.params.width) <= 0 ||
                    !Number.isFinite(Number(step.params.height)) ||
                    Number(step.params.height) <= 0)
            ) {
                return `步骤${index + 1}窗口尺寸必须为正整数`;
            }
            if (step.actionType === "press" && !step.params.key?.trim()) {
                return `步骤${index + 1}缺少按键值`;
            }
            if (
                step.actionType === "select_option" &&
                (!Array.isArray(step.params.values) || !step.params.values.length)
            ) {
                return `步骤${index + 1}至少需要一个下拉项值`;
            }
            if (
                ["sleep", "wait"].includes(step.actionType) &&
                Number(step.params.waitMs ?? 0) < 0
            ) {
                return `步骤${index + 1}等待时间不能小于0`;
            }
            if (
                ["assert_page_contains", "assert_page_not_contains"].includes(
                    step.actionType,
                ) &&
                !`${step.params.text ?? ""}`.trim()
            ) {
                return `步骤${index + 1}缺少页面断言文本`;
            }
            if (
                step.actionType === "assert_title_contains" &&
                !`${step.params.title ?? ""}`.trim()
            ) {
                return `步骤${index + 1}缺少标题断言文本`;
            }
            if (
                step.actionType === "assert_url_contains" &&
                !`${step.params.urlPart ?? ""}`.trim()
            ) {
                return `步骤${index + 1}缺少URL断言文本`;
            }
            if (
                ["assert_text_equals", "assert_text_contains"].includes(
                    step.actionType,
                ) &&
                !`${step.params.expected ?? ""}`.trim()
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
        return "";
    }

    function prepareAssertionForSubmit(assertion) {
        const waitMs = Number(assertion.waitMs);
        return {
            assertType: assertion.assertType,
            expected: assertion.expected ?? "",
            operator: assertion.operator || undefined,
            actualSource: assertion.actualSource || undefined,
            enabled: assertion.enabled !== false,
            waitMs:
                Number.isFinite(waitMs) && waitMs > 0
                    ? Math.round(waitMs)
                    : undefined,
            targetSnapshot: assertion.targetSnapshot
                ? prepareTargetSnapshotForSubmit(assertion.targetSnapshot)
                : undefined,
        };
    }

    function prepareLocatorForSubmit(locator, index) {
        return {
            locatorSnapshotId: locator.locatorSnapshotId,
            locatorType: locator.locatorType,
            locatorValue: normalizeLocatorValue(
                locator.locatorType,
                locator.locatorValue,
            ),
            priority: index,
            enabled: locator.enabled !== false,
        };
    }

    function prepareTargetSnapshotForSubmit(snapshot) {
        const normalized =
            normalizeTargetSnapshot(snapshot) || createDefaultTargetSnapshot();
        return {
            targetSnapshotId: normalized.targetSnapshotId,
            fingerprint: normalized.fingerprint || undefined,
            elementText: normalized.elementText || "",
            stableScore: Number(normalized.stableScore || 0),
            context: {
                pageUrl: normalized.context.pageUrl || "",
                frameUrl: normalized.context.frameUrl || "",
                frameChain: normalized.context.frameChain || [],
                shadowChain: normalized.context.shadowChain || [],
            },
            locators: normalized.locators.map((locator, index) =>
                prepareLocatorForSubmit(locator, index),
            ),
        };
    }

    function buildStepParamsForSubmit(step) {
        const thinkTimeMs = normalizeThinkTimeMs(step.params?.thinkTimeMs);
        const withThinkTime = (payload) =>
            thinkTimeMs > 0 ? { ...payload, thinkTimeMs } : payload;
        if (step.actionType === "goto") {
            return withThinkTime({ url: step.params.url || "" });
        }
        if (step.actionType === "window_maximize") {
            return withThinkTime({});
        }
        if (step.actionType === "set_window_size") {
            return withThinkTime({
                width: Math.max(
                    Math.round(Number(step.params?.width ?? 1920) || 1920),
                    1,
                ),
                height: Math.max(
                    Math.round(Number(step.params?.height ?? 1080) || 1080),
                    1,
                ),
            });
        }
        if (step.actionType === "fill") {
            return withThinkTime({ value: step.params.value ?? "" });
        }
        if (step.actionType === "upload_file") {
            const resourceIds = Array.isArray(step.params?.resourceIds)
                ? step.params.resourceIds
                      .map((item) => `${item ?? ""}`.trim())
                      .filter(Boolean)
                : [];
            return withThinkTime({
                fileKey: `${step.params?.fileKey ?? ""}`.trim(),
                resourceIds,
                multiple: step.params?.multiple === true,
            });
        }
        if (step.actionType === "press") {
            return withThinkTime({ key: step.params.key || "Enter" });
        }
        if (step.actionType === "select_option") {
            return withThinkTime({
                values: Array.isArray(step.params.values)
                    ? step.params.values.filter((item) => `${item}`.trim())
                    : [],
            });
        }
        if (["sleep", "wait"].includes(step.actionType)) {
            return withThinkTime({
                waitMs: Math.max(
                    Math.round(Number(step.params?.waitMs ?? 0) || 0),
                    0,
                ),
            });
        }
        if (
            ["assert_page_contains", "assert_page_not_contains"].includes(
                step.actionType,
            )
        ) {
            return withThinkTime({ text: step.params?.text ?? "" });
        }
        if (step.actionType === "assert_title_contains") {
            return withThinkTime({ title: step.params?.title ?? "" });
        }
        if (step.actionType === "assert_url_contains") {
            return withThinkTime({ urlPart: step.params?.urlPart ?? "" });
        }
        if (
            ["assert_text_equals", "assert_text_contains"].includes(step.actionType)
        ) {
            return withThinkTime({ expected: step.params?.expected ?? "" });
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
            recordOrigin: normalized.recordOrigin || "manual",
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
        // 步骤表格内部状态（选中行/JSON 文本/Tab）由 WebStepEditor 自行重置。
        form.value = createEmptyCase();
    }

    function handleAdd() {
        resetForm();
        showCaseDialog.value = true;
    }

    function handleEdit(row) {
        return getWebCase(row.webCaseId).then((response) => {
            form.value = normalizeCase(response.data || {});
            syncCaseOptions(form.value);
            showCaseDialog.value = true;
        });
    }

    function saveCase() {
        // JSON Tab 的保存前应用由 CaseEditorDialogs 调用 WebStepEditor.flush 完成。
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
            steps: form.value.steps.map((step, index) =>
                prepareStepForSubmit(step, index + 1),
            ),
        };
        const request = payload.webCaseId
            ? updateWebCase(payload)
            : addWebCase(payload);
        request
            .then(async () => {
                ElMessage.success("保存成功");
                showCaseDialog.value = false;
                await refreshCaseTab();
                await loadAllCaseOptions(true);
            })
            .finally(() => {
                loading.value.save = false;
            });
    }

    watch(
        () => form.value.projectId,
        (projectId) => {
            if (!projectId) return;
            if (
                !filteredCaseModules.value.some((item) =>
                    isSameId(item.moduleId, form.value.moduleId),
                )
            ) {
                form.value.moduleId = undefined;
            }
        },
    );

    return {
        showCaseDialog,
        form,
        filteredCaseModules,
        caseDialogTitle,
        resetForm,
        handleAdd,
        handleEdit,
        saveCase,
        // 提交格式序列化：供 WebStepEditor 的 JSON Tab 预览使用。
        prepareStepForSubmit,
    };
}
