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
        safeJsonStringify,
        syncCaseOptions,
        refreshCaseTab,
        loadAllCaseOptions,
        getWebCase,
        addWebCase,
        updateWebCase,
    } = options;

    const showCaseDialog = ref(false);
    const showStepDetailDialog = ref(false);
    const caseEditorTab = ref("visual");
    const selectedStepIndex = ref(-1);
    const stepEditingCell = ref({ index: -1, field: "" });
    const stepsText = ref("[]");
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

    function createDefaultStep(actionType = "click") {
        return normalizeStep({
            actionType,
            stepName: getActionLabel(actionType),
            targetSnapshot: stepNeedsTarget(actionType)
                ? createDefaultTargetSnapshot()
                : null,
        });
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
    const currentStep = computed(
        () => form.value.steps[selectedStepIndex.value] || null,
    );
    const stepDetailTitle = computed(() =>
        selectedStepIndex.value >= 0
            ? `步骤详情 - #${selectedStepIndex.value + 1}`
            : "步骤详情",
    );

    function describeLocator(locator) {
        if (!locator) return "未设置定位器";
        const resolvedIndex = resolveLocatorIndex(locator.locatorValue);
        const indexSuffix = resolvedIndex === null ? "" : ` / nth=${resolvedIndex}`;
        if (locator.locatorType === "role") {
            return `role=${locator.locatorValue.role || "-"} / name=${locator.locatorValue.name || "-"}${indexSuffix}`;
        }
        if (["label", "placeholder", "text"].includes(locator.locatorType)) {
            return `${locator.locatorType}=${locator.locatorValue.text || "-"}${indexSuffix}`;
        }
        if (locator.locatorType === "test_id") {
            return `testId=${locator.locatorValue.testId || "-"}${indexSuffix}`;
        }
        if (locator.locatorType === "id") {
            return `id=${locator.locatorValue.id || "-"}${indexSuffix}`;
        }
        if (locator.locatorType === "name") {
            return `name=${locator.locatorValue.name || "-"}${indexSuffix}`;
        }
        return `${locator.locatorType}=${locator.locatorValue.selector || "-"}${indexSuffix}`;
    }

    function describeStepTarget(step) {
        if (!stepNeedsTarget(step.actionType)) {
            if (step.actionType === "goto") return step.params?.url || "页面跳转";
            if (step.actionType === "window_maximize") return "窗口最大化";
            if (step.actionType === "set_window_size") {
                const width = Number(step.params?.width ?? 0) || 0;
                const height = Number(step.params?.height ?? 0) || 0;
                return width > 0 && height > 0
                    ? `窗口尺寸 ${width}x${height}`
                    : "窗口尺寸调整";
            }
            if (["sleep", "wait"].includes(step.actionType)) {
                return `等待 ${Number(step.params?.waitMs ?? 0) || 0}ms`;
            }
            if (step.actionType === "assert_page_contains") {
                return `页面包含 ${step.params?.text || "-"}`;
            }
            if (step.actionType === "assert_page_not_contains") {
                return `页面不包含 ${step.params?.text || "-"}`;
            }
            if (step.actionType === "assert_title_contains") {
                return `标题包含 ${step.params?.title || "-"}`;
            }
            if (step.actionType === "assert_url_contains") {
                return `URL包含 ${step.params?.urlPart || "-"}`;
            }
            return "页面级动作";
        }
        const firstLocator =
            step.targetSnapshot?.locators?.find((item) => item.enabled !== false) ||
            step.targetSnapshot?.locators?.[0];
        const locatorText = firstLocator
            ? describeLocator(firstLocator)
            : "未设置定位器";
        const elementText = step.targetSnapshot?.elementText
            ? ` / 文本=${step.targetSnapshot.elementText}`
            : "";
        return `${locatorText}${elementText}`;
    }

    function summarizeStepParams(step) {
        if (!step) return "-";
        const thinkTimeMs = normalizeThinkTimeMs(step.params?.thinkTimeMs);
        const appendThinkTime = (text) =>
            thinkTimeMs > 0
                ? `${text || "-"} / 思考${thinkTimeMs}ms`
                : text || "-";
        if (step.actionType === "goto") {
            return appendThinkTime(step.params?.url || "-");
        }
        if (step.actionType === "window_maximize") {
            return appendThinkTime("最大化窗口");
        }
        if (step.actionType === "set_window_size") {
            const width = Number(step.params?.width ?? 0) || 0;
            const height = Number(step.params?.height ?? 0) || 0;
            return appendThinkTime(
                width > 0 && height > 0 ? `${width}x${height}` : "自定义窗口尺寸",
            );
        }
        if (step.actionType === "fill") {
            return appendThinkTime(step.params?.value || "-");
        }
        if (step.actionType === "press") {
            return appendThinkTime(step.params?.key || "-");
        }
        if (step.actionType === "select_option") {
            const valuesText =
                Array.isArray(step.params?.values) && step.params.values.length
                    ? step.params.values.join(", ")
                    : "-";
            return appendThinkTime(valuesText);
        }
        if (["sleep", "wait"].includes(step.actionType)) {
            return appendThinkTime(`${Number(step.params?.waitMs ?? 0) || 0}ms`);
        }
        if (step.actionType === "assert_page_contains") {
            return appendThinkTime(`页面包含：${step.params?.text || "-"}`);
        }
        if (step.actionType === "assert_page_not_contains") {
            return appendThinkTime(`页面不含：${step.params?.text || "-"}`);
        }
        if (step.actionType === "assert_title_contains") {
            return appendThinkTime(`标题包含：${step.params?.title || "-"}`);
        }
        if (step.actionType === "assert_url_contains") {
            return appendThinkTime(`URL包含：${step.params?.urlPart || "-"}`);
        }
        if (step.actionType === "assert_text_equals") {
            return appendThinkTime(`文本等于：${step.params?.expected || "-"}`);
        }
        if (step.actionType === "assert_text_contains") {
            return appendThinkTime(`文本包含：${step.params?.expected || "-"}`);
        }
        return appendThinkTime("-");
    }

    function syncStepsTextFromForm() {
        stepsText.value = safeJsonStringify(
            form.value.steps.map((step, index) =>
                prepareStepForSubmit(step, index + 1),
            ),
        );
    }

    function applyStepsTextToForm(showSuccess = false) {
        let parsedSteps = [];
        try {
            parsedSteps = JSON.parse(stepsText.value || "[]");
        } catch (error) {
            ElMessage.error(`步骤 JSON 解析失败：${error.message}`);
            return false;
        }
        if (!Array.isArray(parsedSteps)) {
            ElMessage.error("步骤 JSON 必须是数组");
            return false;
        }
        form.value.steps = parsedSteps.map((step, index) =>
            normalizeStep(step, index),
        );
        selectedStepIndex.value = form.value.steps.length ? 0 : -1;
        if (showSuccess) {
            ElMessage.success("JSON 已同步到可视化编辑器");
        }
        return true;
    }

    function stripStepIdentity(step) {
        const cloned = normalizeStep(cloneData(step));
        cloned.stepId = undefined;
        if (cloned.targetSnapshot) {
            cloned.targetSnapshot.targetSnapshotId = undefined;
            cloned.targetSnapshot.locators = cloned.targetSnapshot.locators.map(
                (locator, index) => ({
                    ...locator,
                    locatorSnapshotId: undefined,
                    priority: index,
                }),
            );
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
            field: `${field || ""}`.trim(),
        };
    }

    function finishStepCellEditing() {
        stepEditingCell.value = { index: -1, field: "" };
    }

    function isStepCellEditing(index, field) {
        return (
            stepEditingCell.value.index === index &&
            stepEditingCell.value.field === `${field || ""}`.trim()
        );
    }

    function openStepDetailByIndex(index) {
        if (index < 0 || index >= form.value.steps.length) {
            return;
        }
        finishStepCellEditing();
        form.value.steps[index] = normalizeStep(form.value.steps[index], index);
        if (stepNeedsTarget(form.value.steps[index]?.actionType)) {
            getPrimaryLocator(form.value.steps[index]);
        }
        selectedStepIndex.value = index;
        showStepDetailDialog.value = true;
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
        return form.value.steps.indexOf(row) === selectedStepIndex.value
            ? "selected-step-row"
            : "";
    }

    function addStep(actionType = "click") {
        form.value.steps.push(createDefaultStep(actionType));
        selectedStepIndex.value = form.value.steps.length - 1;
        finishStepCellEditing();
    }

    function insertStep(index, actionType = "click") {
        const insertIndex = Math.max(
            0,
            Math.min(Number(index), form.value.steps.length),
        );
        form.value.steps.splice(insertIndex, 0, createDefaultStep(actionType));
        selectedStepIndex.value = insertIndex;
        finishStepCellEditing();
    }

    function copyStep(index) {
        const source = form.value.steps[index];
        if (!source) return;
        const copied = stripStepIdentity(source);
        copied.stepName = `${copied.stepName} - 副本`;
        form.value.steps.splice(index + 1, 0, copied);
        selectedStepIndex.value = index + 1;
    }

    function removeStep(index) {
        form.value.steps.splice(index, 1);
        if (!form.value.steps.length) {
            selectedStepIndex.value = -1;
            finishStepCellEditing();
            return;
        }
        selectedStepIndex.value = Math.min(index, form.value.steps.length - 1);
        finishStepCellEditing();
    }

    function moveStep(index, direction) {
        const targetIndex = index + direction;
        if (targetIndex < 0 || targetIndex >= form.value.steps.length) return;
        const steps = [...form.value.steps];
        [steps[index], steps[targetIndex]] = [steps[targetIndex], steps[index]];
        form.value.steps = steps;
        selectedStepIndex.value = targetIndex;
        finishStepCellEditing();
    }

    function addLocator(step) {
        if (!step.targetSnapshot) {
            step.targetSnapshot = createDefaultTargetSnapshot();
        }
        if (!Array.isArray(step.targetSnapshot.locators)) {
            step.targetSnapshot.locators = [];
        }
        step.targetSnapshot.locators.push(createDefaultLocator());
    }

    function moveLocator(step, index, direction) {
        if (!step?.targetSnapshot?.locators) return;
        const targetIndex = index + direction;
        if (targetIndex < 0 || targetIndex >= step.targetSnapshot.locators.length) {
            return;
        }
        const locators = [...step.targetSnapshot.locators];
        [locators[index], locators[targetIndex]] = [
            locators[targetIndex],
            locators[index],
        ];
        step.targetSnapshot.locators = locators;
    }

    function setPrimaryLocator(step, index) {
        if (!step?.targetSnapshot?.locators) return;
        if (index <= 0 || index >= step.targetSnapshot.locators.length) return;
        const locators = [...step.targetSnapshot.locators];
        const [preferred] = locators.splice(index, 1);
        locators.unshift(preferred);
        step.targetSnapshot.locators = locators;
    }

    function removeLocator(step, index) {
        if (!step?.targetSnapshot?.locators) return;
        step.targetSnapshot.locators.splice(index, 1);
    }

    function addAssertion(step) {
        step.assertions.push(createDefaultAssertion());
    }

    function removeAssertion(step, index) {
        step.assertions.splice(index, 1);
    }

    function handleAssertionTypeChange(assertion) {
        if (!assertionNeedsTarget(assertion?.assertType)) {
            return;
        }
        getAssertionLocatorList(assertion);
    }

    function ensureAssertionTargetSnapshot(assertion) {
        if (!assertion?.targetSnapshot) {
            assertion.targetSnapshot = createDefaultTargetSnapshot();
        }
        if (!Array.isArray(assertion.targetSnapshot.locators)) {
            assertion.targetSnapshot.locators = [];
        }
        return assertion.targetSnapshot;
    }

    function getAssertionLocatorList(assertion) {
        if (!assertionNeedsTarget(assertion?.assertType)) {
            return [];
        }
        const snapshot = ensureAssertionTargetSnapshot(assertion);
        if (!snapshot.locators.length) {
            snapshot.locators = [createDefaultLocator()];
        }
        return snapshot.locators;
    }

    function getAssertionPrimaryLocator(assertion) {
        const locators = getAssertionLocatorList(assertion);
        return (
            locators.find((item) => item.enabled !== false) || locators[0] || null
        );
    }

    function updateAssertionPrimaryLocatorType(assertion, locatorType) {
        const locator = getAssertionPrimaryLocator(assertion);
        if (!locator) {
            return;
        }
        locator.locatorType = locatorType;
        locator.locatorValue = normalizeLocatorValue(locatorType, {});
    }

    function updateAssertionPrimaryLocatorValue(assertion, key, value) {
        const locator = getAssertionPrimaryLocator(assertion);
        if (!locator) {
            return;
        }
        locator.locatorValue = normalizeLocatorValue(
            locator.locatorType,
            locator.locatorValue,
        );
        locator.locatorValue[key] = value;
    }

    function addAssertionLocator(assertion) {
        if (!assertionNeedsTarget(assertion?.assertType)) return;
        const snapshot = ensureAssertionTargetSnapshot(assertion);
        snapshot.locators.push(createDefaultLocator());
    }

    function moveAssertionLocator(assertion, index, direction) {
        const locators = getAssertionLocatorList(assertion);
        const targetIndex = index + direction;
        if (targetIndex < 0 || targetIndex >= locators.length) return;
        [locators[index], locators[targetIndex]] = [
            locators[targetIndex],
            locators[index],
        ];
    }

    function setAssertionPrimaryLocator(assertion, index) {
        const locators = getAssertionLocatorList(assertion);
        if (index <= 0 || index >= locators.length) return;
        const [preferred] = locators.splice(index, 1);
        locators.unshift(preferred);
    }

    function removeAssertionLocator(assertion, index) {
        const snapshot = ensureAssertionTargetSnapshot(assertion);
        if (!Array.isArray(snapshot.locators) || !snapshot.locators.length) return;
        snapshot.locators.splice(index, 1);
    }

    function handleStepActionTypeChange(step) {
        step.params = normalizeStepParams(step.actionType, step.params);
        if (stepNeedsTarget(step.actionType) && !step.targetSnapshot) {
            step.targetSnapshot = createDefaultTargetSnapshot();
        }
    }

    function getPrimaryLocator(step) {
        if (!stepNeedsTarget(step?.actionType)) {
            return null;
        }
        if (!step.targetSnapshot) {
            step.targetSnapshot = createDefaultTargetSnapshot();
        }
        if (
            !Array.isArray(step.targetSnapshot.locators) ||
            !step.targetSnapshot.locators.length
        ) {
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
        locator.locatorValue = normalizeLocatorValue(
            locator.locatorType,
            locator.locatorValue,
        );
        locator.locatorValue[key] = value;
    }

    function handleLocatorTypeChange(locator) {
        locator.locatorValue = normalizeLocatorValue(
            locator.locatorType,
            locator.locatorValue,
        );
    }

    function updateLocatorNth(locator, rawValue) {
        if (!locator) return;
        locator.locatorValue = normalizeLocatorValue(
            locator.locatorType,
            locator.locatorValue,
        );
        delete locator.locatorValue.index;
        delete locator.locatorValue.targetIndex;
        delete locator.locatorValue.target_index;
        if (rawValue === undefined || rawValue === null || rawValue === "") {
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

    function isLocatorFilled(locator) {
        if (!locator || locator.enabled === false) return false;
        if (locator.locatorType === "role") {
            return Boolean(locator.locatorValue.role);
        }
        if (["label", "placeholder", "text"].includes(locator.locatorType)) {
            return Boolean(locator.locatorValue.text);
        }
        if (locator.locatorType === "test_id") {
            return Boolean(locator.locatorValue.testId);
        }
        if (locator.locatorType === "id") {
            return Boolean(locator.locatorValue.id);
        }
        if (locator.locatorType === "name") {
            return Boolean(locator.locatorValue.name);
        }
        return Boolean(locator.locatorValue.selector);
    }

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
        form.value = createEmptyCase();
        selectedStepIndex.value = -1;
        finishStepCellEditing();
        caseEditorTab.value = "visual";
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
            caseEditorTab.value = "visual";
            showCaseDialog.value = true;
        });
    }

    function saveCase() {
        if (caseEditorTab.value === "json" && !applyStepsTextToForm()) {
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
        () => form.value.steps,
        () => {
            if (caseEditorTab.value !== "json") {
                syncStepsTextFromForm();
            }
        },
        { deep: true },
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
        },
    );

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
        showStepDetailDialog,
        caseEditorTab,
        selectedStepIndex,
        stepsText,
        form,
        filteredCaseModules,
        caseDialogTitle,
        currentStep,
        stepDetailTitle,
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
