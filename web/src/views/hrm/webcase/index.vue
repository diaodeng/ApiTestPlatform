<template>
    <div class="app-container webcase-page">
        <el-tabs v-model="activeTab" class="webcase-tabs">
            <el-tab-pane label="用例管理" name="case">
                <CaseTab
                    ref="caseTabRef"
                    :project-options="projectOptions"
                    :module-options="moduleOptions"
                    @sync-case-options="syncCaseOptions"
                    @refresh-case-options="loadAllCaseOptions(true)"
                    @add="handleAdd"
                    @edit="handleEdit"
                    @open-run-dialog="openRunDialog"
                    @open-batch-run-dialog="openBatchRunDialog"
                    @open-run-history="openRunHistory"
                    @open-recording-dialog="openRecordingDialog"
                    @open-runtime-profile-dialog="openRuntimeProfileDialog"
                    @open-browser-session-dialog="openBrowserSessionDialog"
                />
            </el-tab-pane>

            <el-tab-pane label="执行记录" name="run">
                <RunTab
                    ref="runTabRef"
                    @sync-case-options="syncCaseOptions"
                    @open-detail="openRunDetail"
                    @deleted="handleRunRecordsDeleted"
                />
            </el-tab-pane>

            <el-tab-pane label="录制记录" name="recording">
                <RecordingTab
                    ref="recordingTabRef"
                    @sync-case-options="syncCaseOptions"
                    @open-recording-dialog="openRecordingDialog"
                    @open-detail="openRecordingDetail"
                    @open-replay="openReplayDialog"
                    @open-action="openRecordingActionDialog"
                    @deleted="handleRecordingRecordsDeleted"
                />
            </el-tab-pane>
        </el-tabs>

        <CaseEditorDialogs :context="caseEditorDialogsContext" />

        <RunDialogs :context="runDialogsContext" />

        <RecordingLiveDialogs :context="recordingLiveDialogsContext" />

        <RecordingActionDialogs :context="recordingActionDialogsContext" />

        <StateDialogs :context="stateDialogsContext" />
    </div>
</template>

<script setup name="WebCase">
import { ElMessage, ElMessageBox } from "element-plus";
import CaseTab from "./components/CaseTab.vue";
import CaseEditorDialogs from "./components/CaseEditorDialogs.vue";
import RecordingActionDialogs from "./components/RecordingActionDialogs.vue";
import RecordingLiveDialogs from "./components/RecordingLiveDialogs.vue";
import RunTab from "./components/RunTab.vue";
import RunDialogs from "./components/RunDialogs.vue";
import RecordingTab from "./components/RecordingTab.vue";
import StateDialogs from "./components/StateDialogs.vue";
import { useCaseEditorManager } from "./composables/useCaseEditorManager.js";
import { useRecordingManager } from "./composables/useRecordingManager.js";
import { useRunManager } from "./composables/useRunManager.js";
import { useStateManager } from "./composables/useStateManager.js";
import {
    actionOptions,
    assertionTypeOptions,
    browserOptions,
    cloneData,
    extractRows,
    isPlainObject,
    isSameId,
    keyboardKeyOptions,
    locatorTypeOptions,
    mergeCaseOptions,
    normalizeAgentOption,
    normalizeCaseOption,
    normalizeIdValue,
    normalizeModuleOption,
    normalizeProjectOption,
    parseOptionalJsonArray,
    parseOptionalJsonObject,
    recordingStatusOptions,
    runStatusOptions,
    runtimeTargetOptions,
    safeJsonStringify,
} from "./utils/shared.js";
import { all as getAllAgent } from "@/api/hrm/agent.js";
import { listProject } from "@/api/hrm/project.js";
import { showModulList } from "@/api/hrm/module.js";
import {
    addWebCase,
    addWebBrowserSession,
    applyWebRecording,
    cancelWebRecording,
    cancelWebRun,
    deleteWebRecordingStep,
    delWebBrowserSession,
    delWebRuntimeProfile,
    continueWebRecording,
    continueWebRun,
    getWebCase,
    getWebRecording,
    getWebRun,
    listWebBrowserSession,
    listWebRuntimeProfile,
    listWebCase,
    replayWebRecording,
    runWebCase,
    addWebRuntimeProfile,
    saveWebRecordingAsCase,
    startWebRecording,
    stopWebRecording,
    updateWebBrowserSession,
    updateWebRuntimeProfile,
    updateWebCase,
} from "@/api/hrm/web_case.js";

const { proxy } = getCurrentInstance();

const activeTab = ref("case");
const caseTabRef = ref(null);
const runTabRef = ref(null);
const recordingTabRef = ref(null);
const projectOptions = ref([]);
const moduleOptions = ref([]);
const agentOptions = ref([]);
const allCaseOptions = ref([]);
const caseSelectOptions = ref([]);
const caseSelectLoading = ref(false);

const loading = ref({
    save: false,
    run: false,
    runDetail: false,
    recording: false,
    recordingDetail: false,
    recordingAction: false,
    replay: false,
    runtimeProfile: false,
    runtimeProfileSave: false,
    browserSession: false,
    browserSessionSave: false,
});

function normalizePersistScopeHostPatterns(rawValue) {
    let candidates = [];
    if (Array.isArray(rawValue)) {
        candidates = rawValue;
    } else if (typeof rawValue === "string") {
        candidates = rawValue.split(",");
    } else if (rawValue !== undefined && rawValue !== null && rawValue !== "") {
        candidates = [rawValue];
    }
    const seen = new Set();
    return candidates
        .map((item) => `${item ?? ""}`.trim().toLowerCase())
        .filter((item) => {
            if (!item || seen.has(item)) return false;
            seen.add(item);
            return true;
        });
}

function normalizePersistContextScope(scope = {}) {
    const key =
        `${scope.key ?? scope.scopeKey ?? scope.scope_key ?? scope.persistContextKey ?? scope.persist_context_key ?? ""}`.trim();
    if (!key) return null;
    const hostPatterns = normalizePersistScopeHostPatterns(
        scope.hostPatterns ?? scope.host_patterns ?? scope.host ?? scope.domain,
    );
    return {
        key,
        label: `${scope.label ?? scope.name ?? key}`.trim() || key,
        hostPatterns,
        hostPatternsText: hostPatterns.join(","),
        enabled: parseBooleanFlag(scope.enabled, true),
        remark: `${scope.remark ?? ""}`.trim(),
    };
}

function normalizePersistContextScopeList(rawList) {
    if (!Array.isArray(rawList)) return [];
    const seen = new Set();
    const result = [];
    rawList.forEach((item) => {
        const normalized = normalizePersistContextScope(item);
        if (!normalized) return;
        const keyLower = normalized.key.toLowerCase();
        if (seen.has(keyLower)) return;
        seen.add(keyLower);
        result.push(normalized);
    });
    return result;
}

function createEmptyRuntimeProfile() {
    return {
        profileId: undefined,
        profileName: "",
        profileType: "runtime",
        targets: ["web"],
        enabled: true,
        projectId: undefined,
        moduleId: undefined,
        sort: 0,
        runtimeOverridesText: "",
        variablesText: "",
        cookieRulesText: "",
        persistContextScopes: [],
        remark: "",
    };
}

function normalizeRuntimeProfile(profile = {}) {
    const base = createEmptyRuntimeProfile();
    const runtimeOverrides = isPlainObject(
        profile.runtimeOverrides || profile.runtime_overrides,
    )
        ? cloneData(profile.runtimeOverrides || profile.runtime_overrides)
        : {};
    const variables = isPlainObject(profile.variables)
        ? cloneData(profile.variables)
        : {};
    const cookieRules = Array.isArray(
        profile.cookieRules || profile.cookie_rules,
    )
        ? cloneData(profile.cookieRules || profile.cookie_rules)
        : [];
    const persistContextScopes = normalizePersistContextScopeList(
        profile.persistContextScopes || profile.persist_context_scopes,
    );
    const targets =
        Array.isArray(profile.targets) && profile.targets.length
            ? profile.targets
                  .map((item) => `${item}`.trim().toLowerCase())
                  .filter(Boolean)
            : ["web"];
    return {
        ...base,
        ...profile,
        profileId: normalizeIdValue(profile.profileId || profile.profile_id),
        profileName: profile.profileName || profile.profile_name || "",
        profileType: profile.profileType || profile.profile_type || "runtime",
        targets,
        enabled: profile.enabled !== false,
        projectId: normalizeIdValue(profile.projectId || profile.project_id),
        moduleId: normalizeIdValue(profile.moduleId || profile.module_id),
        sort: Number.isFinite(Number(profile.sort))
            ? Math.max(Math.round(Number(profile.sort)), 0)
            : 0,
        runtimeOverridesText: Object.keys(runtimeOverrides).length
            ? safeJsonStringify(runtimeOverrides)
            : "",
        variablesText: Object.keys(variables).length
            ? safeJsonStringify(variables)
            : "",
        cookieRulesText: cookieRules.length
            ? safeJsonStringify(cookieRules)
            : "",
        persistContextScopes,
        remark: profile.remark || "",
        createTime: profile.createTime || profile.create_time,
        updateTime: profile.updateTime || profile.update_time,
    };
}

function normalizeStorageStatePayload(rawState) {
    let state = rawState;
    if (typeof rawState === "string" && rawState.trim()) {
        try {
            state = JSON.parse(rawState);
        } catch (error) {
            state = {};
        }
    }
    const value = isPlainObject(state) ? state : {};
    const cookies = Array.isArray(value.cookies)
        ? value.cookies
              .filter((item) => isPlainObject(item))
              .map((item) => cloneData(item))
        : [];
    const origins = Array.isArray(value.origins)
        ? value.origins
              .filter((item) => isPlainObject(item))
              .map((item) => cloneData(item))
        : [];
    return {
        cookies,
        origins,
    };
}

function createEmptyBrowserSession() {
    return {
        sessionId: undefined,
        sessionName: "",
        scopeKey: "",
        enabled: true,
        projectId: undefined,
        moduleId: undefined,
        browserName: "",
        sort: 0,
        hostPatternsText: "",
        storageStateText: safeJsonStringify({ cookies: [], origins: [] }),
        remark: "",
    };
}

function normalizeBrowserSession(session = {}) {
    const base = createEmptyBrowserSession();
    const hostPatterns = normalizePersistScopeHostPatterns(
        session.hostPatterns ??
            session.host_patterns ??
            session.host ??
            session.domain,
    );
    const storageState = normalizeStorageStatePayload(
        session.storageState ?? session.storage_state,
    );
    const scopeKey =
        `${session.scopeKey ?? session.scope_key ?? session.persistContextKey ?? session.persist_context_key ?? ""}`.trim();
    return {
        ...base,
        ...session,
        sessionId: normalizeIdValue(session.sessionId || session.session_id),
        sessionName:
            `${session.sessionName || session.session_name || ""}`.trim(),
        scopeKey:
            scopeKey ||
            normalizeIdValue(session.sessionId || session.session_id) ||
            "",
        enabled: parseBooleanFlag(session.enabled, true),
        projectId: normalizeIdValue(session.projectId || session.project_id),
        moduleId: normalizeIdValue(session.moduleId || session.module_id),
        browserName: `${session.browserName || session.browser_name || ""}`
            .trim()
            .toLowerCase(),
        sort: Number.isFinite(Number(session.sort))
            ? Math.max(Math.round(Number(session.sort)), 0)
            : 0,
        hostPatternsText: hostPatterns.join(","),
        storageStateText: safeJsonStringify(storageState),
        remark: `${session.remark || ""}`.trim(),
        createTime: session.createTime || session.create_time,
        updateTime: session.updateTime || session.update_time,
    };
}

const caseEditorManager = useCaseEditorManager({
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
});

const {
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
    resolveLocatorIndex
} = caseEditorManager;

const stateManager = useStateManager({
    ElMessage,
    ElMessageBox,
    loading,
    projectOptions,
    moduleOptions,
    isPlainObject,
    isSameId,
    normalizeIdValue,
    parseOptionalJsonArray,
    parseOptionalJsonObject,
    safeJsonStringify,
    createEmptyRuntimeProfile,
    normalizeRuntimeProfile,
    normalizePersistScopeHostPatterns,
    normalizePersistContextScope,
    createEmptyBrowserSession,
    normalizeBrowserSession,
    normalizeStorageStatePayload,
    listWebRuntimeProfile,
    listWebBrowserSession,
    addWebBrowserSession,
    updateWebBrowserSession,
    delWebBrowserSession,
    addWebRuntimeProfile,
    updateWebRuntimeProfile,
    delWebRuntimeProfile,
});

const {
    runtimeProfiles,
    runtimeProfileKeyword,
    runtimeProfileImportText,
    runtimeProfileImportHost,
    browserSessions,
    browserSessionKeyword,
    browserSessionImportText,
    showRuntimeProfileDialog,
    showBrowserSessionDialog,
    runtimeProfileForm,
    browserSessionForm,
    filteredRuntimeProfileModules,
    filteredBrowserSessionModules,
    filteredRuntimeProfiles,
    filteredBrowserSessions,
    profileSupportsWeb,
    isRuntimeProfileScopeMatch,
    isBrowserSessionBrowserMatch,
    formatRuntimeProfileScope,
    formatRuntimeProfileLabel,
    formatBrowserSessionLabel,
    createRuntimeProfileDraft,
    handleRuntimeProfileRowChange,
    loadRuntimeProfiles,
    createBrowserSessionDraft,
    handleBrowserSessionRowChange,
    loadBrowserSessions,
    openBrowserSessionDialog,
    openRuntimeProfileDialog,
    applyRuntimeProfileQuickImport,
    applyBrowserSessionQuickImport,
    addPersistContextScopeRow,
    removePersistContextScopeRow,
    deleteRuntimeProfile,
    saveRuntimeProfile,
    deleteBrowserSession,
    saveBrowserSession,
} = stateManager;

const runManager = useRunManager({
    ElMessage,
    loading,
    activeTab,
    runTabRef,
    runtimeProfiles,
    browserSessions,
    syncCaseOptions,
    refreshRunTab,
    openBrowserSessionDialog,
    openRuntimeProfileDialog,
    normalizeCaseOption,
    normalizeIdValue,
    normalizeStateSourceType,
    normalizeManualLoginWaitSec,
    normalizeLocatorIndexMode,
    resolveStateSourceTypeByIds,
    parseBooleanFlag,
    isPlainObject,
    cloneData,
    isSameId,
    safeJsonStringify,
    profileSupportsWeb,
    isRuntimeProfileScopeMatch,
    isBrowserSessionBrowserMatch,
    formatRuntimeProfileLabel,
    formatBrowserSessionLabel,
    getCaseName,
    getRunRowFailureReason,
    shouldStopRunDetailPoll,
    confirmAndContinueRunManualLogin,
    runWebCase,
    getWebRun,
});

const {
    runTargetCases,
    runDetail,
    showRunDialog,
    showRunDetailDialog,
    runDetailTab,
    runAdvancedPanels,
    runForm,
    availableRuntimeProfilesForRun,
    availableBrowserSessionsForRun,
    runDetailTitle,
    runTargetLabel,
    runStepResults,
    runDetailFailureMessage,
    runCookieApplySummary,
    runCookieApplySummaryType,
    runStepsJsonText,
    openRunDialog,
    openBatchRunDialog,
    openRunHistory,
    stopRunDetailPoll,
    refreshRunDetail,
    openRunDetail,
    submitRun,
} = runManager;

const recordingManager = useRecordingManager({
    ElMessage,
    ElMessageBox,
    loading,
    activeTab,
    runtimeProfiles,
    browserSessions,
    allCaseOptions,
    caseSelectOptions,
    runDetail,
    syncCaseOptions,
    refreshRecordingTab,
    refreshCaseTab,
    loadAllCaseOptions,
    openBrowserSessionDialog,
    openRuntimeProfileDialog,
    handleEdit,
    cloneData,
    isPlainObject,
    isSameId,
    normalizeIdValue,
    normalizeStateSourceType,
    resolveStateSourceTypeByIds,
    parseBooleanFlag,
    normalizeManualLoginWaitSec,
    normalizeOptionalPositiveInt,
    normalizeLocatorIndexMode,
    safeJsonStringify,
    profileSupportsWeb,
    isRuntimeProfileScopeMatch,
    isBrowserSessionBrowserMatch,
    formatRuntimeProfileLabel,
    formatBrowserSessionLabel,
    getCaseName,
    getActionLabel,
    describeStepTarget,
    summarizeStepParams,
    getRecordingStatusMeta,
    formatTime,
    getRunRowFailureReason,
    getStepStatusTagType,
    getStepFailureReason,
    formatDuration,
    canUseRecordingResult,
    shouldStopRecordingPoll,
    getRecordingSummaryPayload,
    mergeCaseOptions,
    confirmAndContinueRecordingManualLogin,
    loadBrowserSessions,
    searchCaseOptions,
    handleCaseSelectVisibleChange,
    moduleOptions,
    caseSelectLoading,
    startWebRecording,
    stopWebRecording,
    getWebRecording,
    saveWebRecordingAsCase,
    applyWebRecording,
    replayWebRecording,
    deleteWebRecordingStep,
});

const {
    selectedRecording,
    recordingDetail,
    replayResult,
    showRecordingDialog,
    showRecordingDetailDialog,
    showRecordingActionDialog,
    showReplayDialog,
    showReplayResultDialog,
    recordingLiveTab,
    recordingDetailTab,
    recordingAdvancedPanels,
    recordingActionMode,
    recordingActionForm,
    recordingForm,
    replayForm,
    filteredRecordingActionModules,
    availableRuntimeProfilesForRecording,
    availableBrowserSessionsForRecording,
    availableRuntimeProfilesForReplay,
    availableBrowserSessionsForReplay,
    recordingLinkedCaseLabel,
    recordingDialogTitle,
    recordingDetailTitle,
    recordingPreviewSteps,
    recordingEventRows,
    recordingDetailJsonText,
    recordingResultReady,
    recordingAssertionTipText,
    recordingLiveStatusText,
    recordingLiveStatusType,
    recordingActionDialogTitle,
    recordingActionDialogTip,
    recordingActionSubmitText,
    selectedReplayLabel,
    replayResultTitle,
    replayStepResults,
    replayFailureMessage,
    replayResultJsonText,
    recordingDetailText,
    liveRecordingSteps,
    handleDeleteLiveRecordingStep,
    openRecordingDialog,
    stopRecordingPoll,
    startRecording,
    stopRecording,
    refreshRecording,
    openRecordingDetail,
    stopRecordingDetailPoll,
    refreshRecordingDetail,
    openRecordingActionDialog,
    submitRecordingAction,
    openReplayDialog,
    submitReplay,
} = recordingManager;

const caseNameMap = computed(() =>
    Object.fromEntries(
        mergeCaseOptions(
            allCaseOptions.value,
            runDetail.value ? [runDetail.value] : [],
            recordingDetail.value ? [recordingDetail.value] : [],
        ).map((item) => [item.webCaseId, item.caseName]),
    ),
);

const caseEditorDialogsContext = {
    showCaseDialog,
    caseDialogTitle,
    form,
    browserOptions,
    projectOptions,
    filteredCaseModules,
    caseEditorTab,
    addStep,
    selectedStepIndex,
    openStepDetailByIndex,
    getStepRowClassName,
    handleStepRowClick,
    startStepCellEditing,
    isStepCellEditing,
    handleStepActionTypeChange,
    finishStepCellEditing,
    actionOptions,
    getActionLabel,
    stepNeedsTarget,
    getPrimaryLocator,
    locatorTypeOptions,
    updatePrimaryLocatorType,
    updatePrimaryLocatorValue,
    describeStepTarget,
    summarizeStepParams,
    insertStep,
    copyStep,
    removeStep,
    moveStep,
    syncStepsTextFromForm,
    stepsText,
    applyStepsTextToForm,
    loading,
    saveCase,
    showStepDetailDialog,
    stepDetailTitle,
    currentStep,
    addLocator,
    moveLocator,
    setPrimaryLocator,
    removeLocator,
    handleLocatorTypeChange,
    updateLocatorNth,
    isLocatorFilled,
    keyboardKeyOptions,
    addAssertion,
    removeAssertion,
    handleAssertionTypeChange,
    assertionTypeOptions,
    assertionNeedsTarget,
    getAssertionPrimaryLocator,
    updateAssertionPrimaryLocatorType,
    updateAssertionPrimaryLocatorValue,
    addAssertionLocator,
    getAssertionLocatorList,
    moveAssertionLocator,
    setAssertionPrimaryLocator,
    removeAssertionLocator,
    safeJsonStringify,
    resolveLocatorIndex,
};

const runDialogsContext = {
    showRunDialog,
    runForm,
    runTargetLabel,
    agentOptions,
    browserOptions,
    availableBrowserSessionsForRun,
    formatBrowserSessionLabel,
    openBrowserSessionDialog,
    availableRuntimeProfilesForRun,
    formatRuntimeProfileLabel,
    openRuntimeProfileDialog,
    runAdvancedPanels,
    loading,
    submitRun,
    showRunDetailDialog,
    runDetailTitle,
    stopRunDetailPoll,
    runDetail,
    getCaseName,
    getRunStatusMeta,
    formatTime,
    formatDuration,
    runDetailFailureMessage,
    runCookieApplySummary,
    runCookieApplySummaryType,
    refreshRunDetail,
    canStopRun,
    handleStopRun,
    canCancelPreparedRun,
    handleCancelPreparedRun,
    handleDeleteRunRecords,
    runDetailTab,
    runStepResults,
    getStepStatusTagType,
    getStepFailureReason,
    runStepsJsonText,
};

const recordingLiveDialogsContext = {
    showRecordingDialog,
    recordingDialogTitle,
    stopRecordingPoll,
    recordingForm,
    recordingLinkedCaseLabel,
    agentOptions,
    browserOptions,
    recordingAdvancedPanels,
    availableBrowserSessionsForRecording,
    formatBrowserSessionLabel,
    openBrowserSessionDialog,
    availableRuntimeProfilesForRecording,
    formatRuntimeProfileLabel,
    openRuntimeProfileDialog,
    loading,
    startRecording,
    stopRecording,
    refreshRecording,
    openRecordingDetail,
    recordingResultReady,
    openRecordingActionDialog,
    recordingAssertionTipText,
    recordingLiveStatusText,
    recordingLiveStatusType,
    recordingLiveTab,
    liveRecordingSteps,
    handleDeleteLiveRecordingStep,
    getActionLabel,
    describeStepTarget,
    summarizeStepParams,
    recordingDetailText,
    showRecordingDetailDialog,
    recordingDetailTitle,
    stopRecordingDetailPoll,
    recordingDetail,
    getCaseName,
    getRecordingStatusMeta,
    formatTime,
    refreshRecordingDetail,
    canStopRecording,
    handleStopRecording,
    canCancelPreparedRecording,
    handleCancelPreparedRecording,
    handleDeleteRecordingRecords,
    canUseRecordingResult,
    openReplayDialog,
    recordingDetailTab,
    recordingPreviewSteps,
    recordingEventRows,
    recordingDetailJsonText,
};

const recordingActionDialogsContext = {
    showRecordingActionDialog,
    recordingActionDialogTitle,
    recordingActionDialogTip,
    recordingActionMode,
    recordingActionForm,
    browserOptions,
    projectOptions,
    filteredRecordingActionModules,
    searchCaseOptions,
    caseSelectLoading,
    handleCaseSelectVisibleChange,
    caseSelectOptions,
    loading,
    submitRecordingAction,
    recordingActionSubmitText,
    showReplayDialog,
    replayForm,
    selectedReplayLabel,
    agentOptions,
    availableBrowserSessionsForReplay,
    formatBrowserSessionLabel,
    openBrowserSessionDialog,
    availableRuntimeProfilesForReplay,
    formatRuntimeProfileLabel,
    openRuntimeProfileDialog,
    submitReplay,
    showReplayResultDialog,
    replayResultTitle,
    replayResult,
    replayFailureMessage,
    replayStepResults,
    getStepStatusTagType,
    formatDuration,
    getStepFailureReason,
    replayResultJsonText,
};

const stateDialogsContext = {
    showRuntimeProfileDialog,
    runtimeProfileKeyword,
    createRuntimeProfileDraft,
    loadRuntimeProfiles,
    loading,
    filteredRuntimeProfiles,
    handleRuntimeProfileRowChange,
    formatRuntimeProfileScope,
    runtimeProfileForm,
    runtimeTargetOptions,
    projectOptions,
    filteredRuntimeProfileModules,
    runtimeProfileImportHost,
    applyRuntimeProfileQuickImport,
    runtimeProfileImportText,
    addPersistContextScopeRow,
    removePersistContextScopeRow,
    deleteRuntimeProfile,
    saveRuntimeProfile,
    showBrowserSessionDialog,
    browserSessionKeyword,
    createBrowserSessionDraft,
    loadBrowserSessions,
    filteredBrowserSessions,
    handleBrowserSessionRowChange,
    browserSessionForm,
    browserOptions,
    filteredBrowserSessionModules,
    browserSessionImportText,
    applyBrowserSessionQuickImport,
    deleteBrowserSession,
    saveBrowserSession,
};

function formatTime(value) {
    return value ? proxy.parseTime(value) : "-";
}

function formatDuration(value) {
    if (value === undefined || value === null || value === "") return "-";
    const ms = Number(value);
    if (!Number.isFinite(ms)) return `${value}`;
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)}s`;
    const minutes = Math.floor(ms / 60000);
    const seconds = ((ms % 60000) / 1000).toFixed(1);
    return `${minutes}m ${seconds}s`;
}

function parseBooleanFlag(value, defaultValue = false) {
    if (value === undefined || value === null || value === "")
        return defaultValue;
    if (typeof value === "boolean") return value;
    if (typeof value === "number") return value !== 0;
    const normalized = `${value}`.trim().toLowerCase();
    if (["1", "true", "yes", "on", "enabled"].includes(normalized)) return true;
    if (["0", "false", "no", "off", "disabled"].includes(normalized))
        return false;
    return defaultValue;
}

function normalizeManualLoginWaitSec(value, defaultValue = 120) {
    const raw = Number(value);
    if (!Number.isFinite(raw)) return defaultValue;
    return Math.min(3600, Math.max(0, Math.round(raw)));
}

function normalizeOptionalPositiveInt(value) {
    if (value === undefined || value === null || value === "") {
        return undefined;
    }
    const raw = Number(value);
    if (!Number.isFinite(raw)) {
        return undefined;
    }
    const rounded = Math.round(raw);
    return rounded > 0 ? rounded : undefined;
}

function normalizeStateSourceType(value) {
    const normalized = `${value || ""}`.trim().toLowerCase();
    if (normalized === "session" || normalized === "cookie") return normalized;
    return "none";
}

/**
 * 标准化定位器索引策略，支持 delayed/auto/always。
 * @param {any} value 原始配置值（字符串或布尔）
 * @returns {"delayed" | "auto" | "always"}
 */
function normalizeLocatorIndexMode(value) {
    if (value === true) return "always";
    if (value === false) return "auto";
    const normalized = `${value || ""}`.trim().toLowerCase();
    if (
        ["always", "immediate", "force", "on", "enabled", "true", "1"].includes(
            normalized,
        )
    ) {
        return "always";
    }
    if (
        ["delayed", "legacy", "wait", "off", "disabled", "false", "0"].includes(
            normalized,
        )
    ) {
        return "delayed";
    }
    return "auto";
}

function resolveStateSourceTypeByIds(browserSessionId, runtimeProfileId) {
    if (normalizeIdValue(browserSessionId)) return "session";
    if (normalizeIdValue(runtimeProfileId)) return "cookie";
    return "none";
}

async function confirmAndContinueRunManualLogin({ runId, agentId, caseName }) {
    try {
        await ElMessageBox.confirm(
            `浏览器已启动，请先手动完成登录，再点击继续。\n执行记录ID：${runId}${caseName ? `\n目标用例：${caseName}` : ""}`,
            "等待手动登录",
            {
                confirmButtonText: "我已登录，继续执行",
                cancelButtonText: "取消继续",
                type: "warning",
                closeOnClickModal: false,
                closeOnPressEscape: false,
                showClose: false,
                distinguishCancelAndClose: true,
            },
        );
    } catch {
        try {
            await cancelWebRun({
                webCaseRunId: runId,
                agentId: agentId || undefined,
                reason: "用户取消继续执行",
            });
            ElMessage.info("已取消执行准备");
        } catch (cancelError) {
            const msg =
                cancelError?.response?.data?.msg ||
                cancelError?.message ||
                "取消执行准备失败";
            ElMessage.warning(msg);
        }
        throw new Error("已取消继续执行");
    }
    return continueWebRun({
        webCaseRunId: runId,
        agentId: agentId || undefined,
    });
}

async function confirmAndContinueRecordingManualLogin({
    recordingId,
    agentId,
    sessionName,
}) {
    try {
        await ElMessageBox.confirm(
            `浏览器已启动，请先手动完成登录，再点击继续录制。\n录制ID：${recordingId}${sessionName ? `\n录制名称：${sessionName}` : ""}`,
            "等待手动登录",
            {
                confirmButtonText: "我已登录，继续录制",
                cancelButtonText: "取消继续",
                type: "warning",
                closeOnClickModal: false,
                closeOnPressEscape: false,
                showClose: false,
                distinguishCancelAndClose: true,
            },
        );
    } catch {
        try {
            await cancelWebRecording({
                recordingId,
                agentId: agentId || undefined,
                reason: "用户取消继续录制",
            });
            ElMessage.info("已取消录制准备");
        } catch (cancelError) {
            const msg =
                cancelError?.response?.data?.msg ||
                cancelError?.message ||
                "取消录制准备失败";
            ElMessage.warning(msg);
        }
        throw new Error("已取消继续录制");
    }
    return continueWebRecording({
        recordingId,
        agentId: agentId || undefined,
    });
}

function getRunStatusMeta(status) {
    return (
        runStatusOptions.find((item) => item.value === status) || {
            label: `${status ?? "-"}`,
            type: "info",
        }
    );
}

function getRecordingStatusMeta(status) {
    return (
        recordingStatusOptions.find((item) => item.value === status) || {
            label: `${status ?? "-"}`,
            type: "info",
        }
    );
}

function normalizeStepStatus(status) {
    return `${status ?? ""}`.trim().toLowerCase();
}

function isPassedStepStatus(status) {
    const normalized = normalizeStepStatus(status);
    return (
        ["passed", "success", "ok"].includes(normalized) ||
        status === 1 ||
        status === true
    );
}

function isSkippedStepStatus(status) {
    const normalized = normalizeStepStatus(status);
    return ["skipped", "skip", "disabled"].includes(normalized);
}

function isRunningStepStatus(status) {
    const normalized = normalizeStepStatus(status);
    return ["running", "in_progress", "processing"].includes(normalized);
}

function getStepStatusTagType(status) {
    if (isPassedStepStatus(status)) return "success";
    if (isSkippedStepStatus(status)) return "info";
    if (isRunningStepStatus(status)) return "warning";
    return "danger";
}

function getStepFailureReason(step) {
    if (!step) return "-";
    if (
        isPassedStepStatus(step.status) ||
        isSkippedStepStatus(step.status) ||
        isRunningStepStatus(step.status)
    )
        return "-";
    const candidates = [
        step.error,
        step.errorMessage,
        step.message,
        step.reason,
        step.errorType,
        step.error_type,
    ];
    for (const item of candidates) {
        const text = `${item ?? ""}`.trim();
        if (text) return text;
    }
    return "执行失败（无详细错误）";
}

function getFirstFailedStep(resultPayload) {
    const steps = Array.isArray(resultPayload?.steps)
        ? resultPayload.steps
        : [];
    return steps.find(
        (item) =>
            item &&
            !isPassedStepStatus(item.status) &&
            !isSkippedStepStatus(item.status) &&
            !isRunningStepStatus(item.status),
    );
}

function getRunRowFailureReason(row) {
    const direct = `${row?.errorMessage ?? ""}`.trim();
    if (direct) return direct;
    const failedStep = getFirstFailedStep(row?.result);
    if (!failedStep) return "-";
    const stepName =
        `${failedStep.stepName ?? failedStep.step_name ?? failedStep.stepId ?? failedStep.step_id ?? "未知步骤"}`.trim();
    const reason = getStepFailureReason(failedStep);
    if (!stepName) return reason || "执行失败";
    if (!reason || reason === "-") return `[${stepName}] 执行失败`;
    if (reason.includes(stepName)) return reason;
    return `[${stepName}] ${reason}`;
}

function getRunResultPayload(row) {
    return isPlainObject(row?.result) ? row.result : {};
}

function isRunWaitingManualConfirm(row) {
    const resultPayload = getRunResultPayload(row);
    if (resultPayload.awaitingManualConfirm === true) return true;
    const directGate = isPlainObject(resultPayload.manualLoginGate)
        ? resultPayload.manualLoginGate
        : null;
    const runtimeDebug = isPlainObject(resultPayload.runtimeDebug)
        ? resultPayload.runtimeDebug
        : null;
    const runtimeGate = isPlainObject(runtimeDebug?.manualLoginGate)
        ? runtimeDebug.manualLoginGate
        : null;
    const gate = directGate || runtimeGate;
    if (gate && gate.waitingConfirm === true) return true;
    const statusText = `${resultPayload.manualLoginStatus || ""}`
        .trim()
        .toLowerCase();
    return statusText === "waiting_manual_login";
}

function canStopRun(row) {
    return Number(row?.status) === 9 && !isRunWaitingManualConfirm(row);
}

function canCancelPreparedRun(row) {
    return Number(row?.status) === 9 && isRunWaitingManualConfirm(row);
}

function getRecordingSummaryPayload(row) {
    if (isPlainObject(row?.resultSummary)) return row.resultSummary;
    if (isPlainObject(row?.result_summary)) return row.result_summary;
    if (isPlainObject(row?.resultSummaryJson)) return row.resultSummaryJson;
    if (isPlainObject(row?.result_summary_json)) return row.result_summary_json;
    return {};
}

function isRecordingWaitingManualConfirm(row) {
    const payload = getRecordingSummaryPayload(row);
    const manualGate = isPlainObject(payload.manualLoginGate)
        ? payload.manualLoginGate
        : null;
    if (manualGate && manualGate.waitingConfirm === true) return true;
    const statusText = `${payload.status || ""}`.trim().toLowerCase();
    return statusText === "waiting_manual_login";
}

function canStopRecording(row) {
    return Number(row?.status) === 2 && !isRecordingWaitingManualConfirm(row);
}

function canCancelPreparedRecording(row) {
    return Number(row?.status) === 2 && isRecordingWaitingManualConfirm(row);
}

function getCaseName(webCaseId) {
    const targetId = normalizeIdValue(webCaseId);
    if (!targetId) {
        return "";
    }
    return (
        caseNameMap.value[targetId] ||
        mergeCaseOptions(allCaseOptions.value).find((item) =>
            isSameId(item.webCaseId, targetId),
        )?.caseName ||
        ""
    );
}

const runtimeVariableKeys = [
    "variables",
    "runtimeVariables",
    "runtime_variables",
    "cookieVariables",
    "cookie_variables",
];
const runtimeCookieRuleKeys = [
    "cookieRules",
    "cookie_rules",
    "cookieScopes",
    "cookie_scopes",
    "cookieProfiles",
    "cookie_profiles",
];
const runtimeVarPattern = /\$\{([a-zA-Z0-9_.-]+)\}|\{\{([a-zA-Z0-9_.-]+)\}\}/g;

function getRuntimeProfileById(profileId) {
    const normalizedId = normalizeIdValue(profileId);
    if (!normalizedId) return null;
    return (
        runtimeProfiles.value.find((item) =>
            isSameId(item.profileId, normalizedId),
        ) || null
    );
}

function collectRuntimeVariables(runtimeOverrides) {
    const source = isPlainObject(runtimeOverrides) ? runtimeOverrides : {};
    const result = {};
    runtimeVariableKeys.forEach((key) => {
        const value = source[key];
        if (isPlainObject(value)) {
            Object.assign(result, value);
        }
    });
    return result;
}

function collectCookieRules(runtimeOverrides) {
    const source = isPlainObject(runtimeOverrides) ? runtimeOverrides : {};
    const result = [];
    runtimeCookieRuleKeys.forEach((key) => {
        const value = source[key];
        if (Array.isArray(value)) {
            value.forEach((item) => {
                if (isPlainObject(item)) {
                    result.push(cloneData(item));
                }
            });
        }
    });
    return result;
}

function mergeRuntimeOverrides(baseRuntimeOverrides, overrideRuntimeOverrides) {
    const base = isPlainObject(baseRuntimeOverrides)
        ? cloneData(baseRuntimeOverrides)
        : {};
    const override = isPlainObject(overrideRuntimeOverrides)
        ? cloneData(overrideRuntimeOverrides)
        : {};
    const merged = { ...base };
    Object.entries(override).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
            merged[key] = value;
        }
    });

    const mergedVariables = collectRuntimeVariables(base);
    Object.assign(mergedVariables, collectRuntimeVariables(override));
    if (Object.keys(mergedVariables).length) {
        merged.variables = mergedVariables;
    }
    runtimeVariableKeys.forEach((key) => {
        if (key !== "variables") {
            delete merged[key];
        }
    });

    const mergedRules = [
        ...collectCookieRules(base),
        ...collectCookieRules(override),
    ];
    if (mergedRules.length) {
        merged.cookieRules = mergedRules;
    }
    runtimeCookieRuleKeys.forEach((key) => {
        if (key !== "cookieRules") {
            delete merged[key];
        }
    });
    return merged;
}

function composeRuntimeOverridesFromProfile(profile) {
    if (!profile) return {};
    const runtimeOverrides = isPlainObject(
        profile.runtimeOverrides || profile.runtime_overrides,
    )
        ? cloneData(profile.runtimeOverrides || profile.runtime_overrides)
        : {};
    if (
        isPlainObject(profile.variables) &&
        Object.keys(profile.variables).length
    ) {
        const existingVariables = collectRuntimeVariables(runtimeOverrides);
        runtimeOverrides.variables = {
            ...existingVariables,
            ...profile.variables,
        };
    }
    if (
        Array.isArray(profile.cookieRules || profile.cookie_rules) &&
        (profile.cookieRules || profile.cookie_rules).length
    ) {
        const existingRules = collectCookieRules(runtimeOverrides);
        runtimeOverrides.cookieRules = [
            ...existingRules,
            ...cloneData(profile.cookieRules || profile.cookie_rules),
        ];
    }
    runtimeVariableKeys.forEach((key) => {
        if (key !== "variables") {
            delete runtimeOverrides[key];
        }
    });
    runtimeCookieRuleKeys.forEach((key) => {
        if (key !== "cookieRules") {
            delete runtimeOverrides[key];
        }
    });
    return runtimeOverrides;
}

function interpolateRuntimeString(value, variables) {
    const text = `${value ?? ""}`;
    if (!text) return text;
    return text.replace(runtimeVarPattern, (match, varA, varB) => {
        const key = varA || varB || "";
        if (Object.prototype.hasOwnProperty.call(variables, key)) {
            return `${variables[key] ?? ""}`;
        }
        return match;
    });
}

function ensureArrayValue(value) {
    if (Array.isArray(value))
        return value
            .map((item) => `${item ?? ""}`)
            .filter((item) => item.trim());
    if (value === undefined || value === null || value === "") return [];
    return [`${value}`];
}

function hostFromUrl(url) {
    const raw = `${url ?? ""}`.trim();
    if (!raw) return "";
    try {
        return new URL(raw).hostname.toLowerCase();
    } catch (error) {
        return "";
    }
}

function normalizeCookieRuleForPreview(rule, index = 0) {
    if (!isPlainObject(rule)) return null;
    const rawCookies = Array.isArray(rule.cookies) ? rule.cookies : [];
    const cookies = rawCookies
        .filter((item) => isPlainObject(item))
        .map((item) => cloneData(item));
    if (!cookies.length) return null;
    const match = isPlainObject(rule.match) ? cloneData(rule.match) : {};
    [
        "host",
        "domain",
        "urlContains",
        "url_contains",
        "urlRegex",
        "url_regex",
    ].forEach((key) => {
        if (
            !Object.prototype.hasOwnProperty.call(match, key) &&
            rule[key] !== undefined &&
            rule[key] !== null &&
            rule[key] !== ""
        ) {
            match[key] = rule[key];
        }
    });
    const applyOnRaw = Array.isArray(rule.applyOn || rule.apply_on)
        ? rule.applyOn || rule.apply_on
        : [];
    const applyOn = new Set(
        applyOnRaw
            .map((item) => `${item ?? ""}`.trim().toLowerCase())
            .filter(Boolean),
    );
    if (!applyOn.size) {
        ["before_start", "before_step", "before_goto"].forEach((item) =>
            applyOn.add(item),
        );
    }
    return {
        name: `${rule.name || `rule_${index + 1}`}`,
        match,
        applyOn,
        cookies,
    };
}

function ruleMatchesUrlForPreview(rule, targetUrl, targetHost, variables) {
    const match = isPlainObject(rule?.match) ? rule.match : {};
    if (!Object.keys(match).length) return true;

    const hostValues = [
        ...ensureArrayValue(match.host),
        ...ensureArrayValue(match.domain),
    ].map((item) =>
        interpolateRuntimeString(`${item}`.toLowerCase(), variables),
    );
    if (hostValues.length) {
        if (!targetHost) return false;
        if (
            !hostValues.some(
                (item) =>
                    item &&
                    (targetHost === item || targetHost.endsWith(`.${item}`)),
            )
        ) {
            return false;
        }
    }

    const containsValues = ensureArrayValue(
        match.urlContains ?? match.url_contains,
    ).map((item) => interpolateRuntimeString(item, variables));
    if (containsValues.length) {
        if (!containsValues.some((item) => item && targetUrl.includes(item))) {
            return false;
        }
    }

    const regexValues = ensureArrayValue(match.urlRegex ?? match.url_regex).map(
        (item) => interpolateRuntimeString(item, variables),
    );
    if (regexValues.length) {
        let matched = false;
        regexValues.forEach((pattern) => {
            if (matched || !pattern) return;
            try {
                if (new RegExp(pattern).test(targetUrl)) {
                    matched = true;
                }
            } catch (error) {
                // ignore invalid regex
            }
        });
        if (!matched) {
            return false;
        }
    }
    return true;
}

function normalizeCookieForPreview(
    cookieDef,
    targetUrl,
    targetHost,
    variables,
    defaultDomain = "",
) {
    if (!isPlainObject(cookieDef)) return null;
    const name = interpolateRuntimeString(cookieDef.name, variables).trim();
    if (!name) return null;
    const value = interpolateRuntimeString(cookieDef.value, variables);
    if (value === "") return null;

    const cookie = {
        name,
        value,
    };
    const explicitUrl = cookieDef.url
        ? interpolateRuntimeString(cookieDef.url, variables)
        : "";
    const explicitDomain = cookieDef.domain
        ? interpolateRuntimeString(cookieDef.domain, variables)
        : "";
    const explicitPath = cookieDef.path
        ? interpolateRuntimeString(cookieDef.path, variables)
        : "";
    const fallbackDomain = interpolateRuntimeString(
        defaultDomain || "",
        variables,
    )
        .trim()
        .replace(/^\./, "")
        .toLowerCase();
    if (explicitUrl) {
        cookie.url = explicitUrl;
    } else if (explicitDomain) {
        cookie.domain = explicitDomain;
        cookie.path = explicitPath || "/";
    } else if (fallbackDomain) {
        cookie.domain = fallbackDomain;
        cookie.path = explicitPath || "/";
    } else if (targetUrl) {
        cookie.url = targetUrl;
    } else if (targetHost) {
        cookie.domain = targetHost;
        cookie.path = "/";
    } else {
        return null;
    }
    if (cookieDef.httpOnly !== undefined) {
        cookie.httpOnly = Boolean(cookieDef.httpOnly);
    }
    if (cookieDef.secure !== undefined) {
        cookie.secure = Boolean(cookieDef.secure);
    }
    if (
        cookieDef.sameSite !== undefined &&
        cookieDef.sameSite !== null &&
        cookieDef.sameSite !== ""
    ) {
        cookie.sameSite = `${cookieDef.sameSite}`;
    }
    if (
        cookieDef.expires !== undefined &&
        cookieDef.expires !== null &&
        cookieDef.expires !== ""
    ) {
        const expiresValue = Number(cookieDef.expires);
        if (Number.isFinite(expiresValue)) {
            cookie.expires = Math.round(expiresValue);
        }
    }
    return cookie;
}

function buildCookiePreviewForTarget({
    targetUrl,
    runtimeProfileId,
    runtimeOverrides,
    stage = "before_start",
}) {
    const normalizedStage =
        `${stage || ""}`.trim().toLowerCase() || "before_start";
    const normalizedTargetUrl = `${targetUrl || ""}`.trim();
    const targetHost = hostFromUrl(normalizedTargetUrl);

    const profile = getRuntimeProfileById(runtimeProfileId);
    const profileRuntimeOverrides = composeRuntimeOverridesFromProfile(profile);
    const mergedRuntimeOverrides = mergeRuntimeOverrides(
        profileRuntimeOverrides,
        runtimeOverrides,
    );
    const variables = collectRuntimeVariables(mergedRuntimeOverrides);
    const rules = collectCookieRules(mergedRuntimeOverrides)
        .map((item, index) => normalizeCookieRuleForPreview(item, index))
        .filter(Boolean);

    const matchedRuleNames = [];
    const cookies = [];
    rules.forEach((rule) => {
        if (rule.applyOn.size && !rule.applyOn.has(normalizedStage)) return;
        if (
            !ruleMatchesUrlForPreview(
                rule,
                normalizedTargetUrl,
                targetHost,
                variables,
            )
        )
            return;
        matchedRuleNames.push(rule.name);
        const ruleMatch = isPlainObject(rule.match) ? rule.match : {};
        const defaultDomainCandidates = [
            ...ensureArrayValue(ruleMatch.domain),
            ...ensureArrayValue(ruleMatch.host),
        ];
        const defaultDomain = defaultDomainCandidates
            .map((item) =>
                interpolateRuntimeString(item, variables)
                    .trim()
                    .replace(/^\./, "")
                    .toLowerCase(),
            )
            .find((item) => item);
        rule.cookies.forEach((cookieDef) => {
            const normalized = normalizeCookieForPreview(
                cookieDef,
                normalizedTargetUrl,
                targetHost,
                variables,
                defaultDomain,
            );
            if (normalized) {
                cookies.push(normalized);
            }
        });
    });

    const dedup = new Map();
    cookies.forEach((cookie) => {
        const key = `${cookie.name}::${cookie.domain || cookie.url || ""}::${cookie.path || "/"}`;
        dedup.set(key, cookie);
    });
    const dedupedCookies = Array.from(dedup.values());
    return {
        targetUrl: normalizedTargetUrl,
        targetHost,
        rules: matchedRuleNames,
        cookies: dedupedCookies,
        appliedCount: dedupedCookies.length,
    };
}

function escapeHtml(text) {
    return `${text ?? ""}`
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function hasCookiePreviewInput(runtimeProfileId, runtimeOverrides) {
    if (normalizeIdValue(runtimeProfileId)) return true;
    return collectCookieRules(runtimeOverrides).length > 0;
}

async function confirmCookiePreviewBeforeStart({
    mode,
    targets,
    runtimeProfileId,
    runtimeOverrides,
    stage = "before_start",
}) {
    if (!hasCookiePreviewInput(runtimeProfileId, runtimeOverrides)) {
        return true;
    }
    const normalizedTargets = Array.isArray(targets)
        ? targets.filter((item) => item && item.targetUrl)
        : [];
    if (!normalizedTargets.length) {
        return true;
    }
    const previewRows = normalizedTargets.map((target, index) => {
        const preview = buildCookiePreviewForTarget({
            targetUrl: target.targetUrl,
            runtimeProfileId,
            runtimeOverrides,
            stage,
        });
        return {
            label: target.label || `目标${index + 1}`,
            ...preview,
        };
    });
    const hasZeroApply = previewRows.some(
        (item) => Number(item.appliedCount || 0) <= 0,
    );
    const displayRows = previewRows.slice(0, 12);
    const omitted = previewRows.length - displayRows.length;
    const lines = displayRows.map((item, index) => {
        const cookieNames = item.cookies
            .slice(0, 6)
            .map((cookie) => cookie.name)
            .filter(Boolean);
        const cookieText = cookieNames.length
            ? `，Cookie: ${escapeHtml(cookieNames.join(", "))}`
            : "";
        const ruleText = item.rules.length
            ? `，规则: ${escapeHtml(item.rules.join("、"))}`
            : "，规则: 无命中";
        return `${index + 1}. <strong>${escapeHtml(item.label)}</strong> (${escapeHtml(item.targetHost || item.targetUrl || "-")})：注入 <strong>${item.appliedCount}</strong> 个${ruleText}${cookieText}`;
    });
    if (omitted > 0) {
        lines.push(`其余 ${omitted} 条目标已省略，规则计算逻辑一致。`);
    }
    if (hasZeroApply) {
        lines.push("存在未命中Cookie规则的目标，可能仍会跳转登录页。");
    }
    const title =
        mode === "recording" ? "录制前 Cookie 预览" : "执行前 Cookie 预览";
    const confirmText = mode === "recording" ? "确认开始录制" : "确认继续执行";
    const html = `<div style="line-height: 1.6;">${lines.map((line) => `<div>${line}</div>`).join("")}</div>`;
    try {
        await ElMessageBox.confirm(html, title, {
            type: hasZeroApply ? "warning" : "info",
            confirmButtonText: confirmText,
            cancelButtonText: "取消",
            closeOnClickModal: false,
            closeOnPressEscape: false,
            dangerouslyUseHTMLString: true,
        });
        return true;
    } catch (error) {
        return false;
    }
}

function syncCaseOptions(...collections) {
    const mergedAll = mergeCaseOptions(allCaseOptions.value, ...collections);
    allCaseOptions.value = mergedAll;
}

function loadAllCaseOptions(force = false) {
    if (!force && allCaseOptions.value.length) {
        return Promise.resolve(allCaseOptions.value);
    }
    return searchCaseOptions("");
}

function searchCaseOptions(keyword = "") {
    const searchKeyword = keyword?.trim();
    caseSelectLoading.value = true;
    return listWebCase({
        pageNum: 1,
        pageSize: searchKeyword ? 50 : 200,
        caseName: searchKeyword || undefined,
    })
        .then((response) => {
            const rows = mergeCaseOptions(extractRows(response));
            caseSelectOptions.value = rows;
            if (searchKeyword) {
                allCaseOptions.value = mergeCaseOptions(
                    allCaseOptions.value,
                    rows,
                );
            } else {
                allCaseOptions.value = rows;
            }
            return rows;
        })
        .finally(() => {
            caseSelectLoading.value = false;
        });
}

function handleCaseSelectVisibleChange(visible) {
    if (visible && !caseSelectOptions.value.length) {
        searchCaseOptions("");
    }
}

function refreshCaseTab() {
    return caseTabRef.value?.getList?.() || Promise.resolve();
}

function refreshRunTab() {
    return runTabRef.value?.getRunList?.() || Promise.resolve();
}

function refreshRecordingTab() {
    return recordingTabRef.value?.getRecordingList?.() || Promise.resolve();
}

function handleRunRecordsDeleted(ids = []) {
    if (
        runDetail.value?.webCaseRunId &&
        ids.includes(normalizeIdValue(runDetail.value.webCaseRunId))
    ) {
        showRunDetailDialog.value = false;
        runDetail.value = null;
        stopRunDetailPoll();
    }
}

function handleRecordingRecordsDeleted(ids = []) {
    if (
        recordingDetail.value?.recordingId &&
        ids.includes(normalizeIdValue(recordingDetail.value.recordingId))
    ) {
        showRecordingDetailDialog.value = false;
        recordingDetail.value = null;
        stopRecordingDetailPoll();
    }
}

async function handleStopRun(row) {
    await runTabRef.value?.handleStopRun?.(row);
    await refreshRunDetail().catch(() => {});
}

async function handleCancelPreparedRun(row) {
    await runTabRef.value?.handleCancelPreparedRun?.(row);
    await refreshRunDetail().catch(() => {});
}

async function handleDeleteRunRecords(row = null) {
    await runTabRef.value?.handleDeleteRecords?.(row);
}

async function handleStopRecording(row) {
    await recordingTabRef.value?.handleStopRecording?.(row);
    await refreshRecordingDetail().catch(() => {});
}

async function handleCancelPreparedRecording(row) {
    await recordingTabRef.value?.handleCancelPreparedRecording?.(row);
    await refreshRecordingDetail().catch(() => {});
}

async function handleDeleteRecordingRecords(row = null) {
    await recordingTabRef.value?.handleDeleteRecords?.(row);
}

function shouldStopRecordingPoll(detailOrStatus) {
    if (isPlainObject(detailOrStatus)) {
        const status = Number(detailOrStatus.status);
        if ([3, 4].includes(status)) {
            return true;
        }
        if (status !== 5) {
            return false;
        }
        const summaryPayload = getRecordingSummaryPayload(detailOrStatus);
        const summaryStatus = `${summaryPayload?.status || ""}`
            .trim()
            .toLowerCase();
        return [
            "cancelled",
            "canceled",
            "stopped",
            "finished",
            "failed",
        ].includes(summaryStatus);
    }
    return [3, 4].includes(Number(detailOrStatus));
}

function shouldStopRunDetailPoll(status) {
    return [1, 2, 3, 8].includes(Number(status));
}

function canUseRecordingResult(status) {
    return [3, 4, 5].includes(Number(status));
}

async function loadBaseData() {
    const [projectRes, moduleRes, agentRes] = await Promise.all([
        listProject({ isPage: false }),
        showModulList({ isPage: false }),
        getAllAgent(),
    ]);
    projectOptions.value = extractRows(projectRes).map(normalizeProjectOption);
    moduleOptions.value = extractRows(moduleRes).map(normalizeModuleOption);
    agentOptions.value = extractRows(agentRes).map(normalizeAgentOption);
}

watch(activeTab, (value) => {
    if (value === "run") {
        loadAllCaseOptions();
        nextTick(() => {
            refreshRunTab();
        });
    }
    if (value === "recording") {
        loadAllCaseOptions();
        nextTick(() => {
            refreshRecordingTab();
        });
    }
});

onMounted(async () => {
    await loadBaseData();
    await loadAllCaseOptions().catch(() => {});
    await loadRuntimeProfiles().catch(() => {});
    await loadBrowserSessions().catch(() => {});
    createRuntimeProfileDraft();
    resetForm();
});
</script>

<style scoped lang="scss">
.webcase-page {
    min-height: calc(100vh - 84px);
}

.webcase-tabs :deep(.el-tabs__content) {
    overflow: visible;
}
</style>

