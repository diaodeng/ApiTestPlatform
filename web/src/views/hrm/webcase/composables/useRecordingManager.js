import { computed, onBeforeUnmount, ref, watch } from "vue";

/**
 * 录制业务域组合式逻辑。
 * @param {Object} options 依赖项
 * @returns {Object} 录制相关状态与方法
 */
export function useRecordingManager(options) {
    const {
        ElMessage,
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
        startWebRecording,
        stopWebRecording,
        getWebRecording,
        saveWebRecordingAsCase,
        applyWebRecording,
        replayWebRecording,
    } = options;

    const selectedCase = ref(null);
    const selectedRecording = ref(null);
    const recordingEvents = ref([]);
    const liveRecordingSteps = ref([]);
    const recordingDetail = ref(null);
    const replayResult = ref(null);
    const recordingDetailText = ref("");

    const showRecordingDialog = ref(false);
    const showRecordingDetailDialog = ref(false);
    const showRecordingActionDialog = ref(false);
    const showReplayDialog = ref(false);
    const showReplayResultDialog = ref(false);

    const recordingLiveTab = ref("steps");
    const recordingDetailTab = ref("steps");
    const recordingAdvancedPanels = ref([]);

    const recordingActionMode = ref("create");
    const recordingActionForm = ref({
        recordingId: undefined,
        webCaseId: undefined,
        caseName: "",
        projectId: undefined,
        moduleId: undefined,
        startUrl: "",
        browserName: "chromium",
        headless: false,
        notes: "",
    });

    const recordingForm = ref({
        webCaseId: undefined,
        sessionName: "",
        agentId: undefined,
        browserName: "chromium",
        headless: false,
        startUrl: "",
        stateSourceType: "none",
        browserSessionId: undefined,
        runtimeProfileId: undefined,
        persistContextEnabled: false,
        persistContextAutoSyncSession: false,
        manualLoginEnabled: false,
        manualLoginRequireConfirm: false,
        manualLoginWaitSec: 120,
        windowMaximize: false,
        windowWidth: undefined,
        windowHeight: undefined,
        closeBrowserOnStop: true,
        captureAssertions: true,
        attachAssertionsToPreviousStep: true,
        autoAssertTextOnClick: false,
        recordingId: undefined,
    });

    const replayForm = ref({
        recordingId: undefined,
        agentId: undefined,
        browserName: "chromium",
        headless: false,
        closeBrowserOnFinish: true,
        immediateLocatorIndexMode: false,
        stateSourceType: "none",
        browserSessionId: undefined,
        runtimeProfileId: undefined,
        persistContextEnabled: false,
        persistContextAutoSyncSession: false,
    });

    let recordingTimer = null;
    let recordingDetailTimer = null;

    const filteredRecordingActionModules = computed(() => {
        if (!recordingActionForm.value.projectId) {
            return moduleOptions.value;
        }
        return moduleOptions.value.filter((item) =>
            isSameId(item.projectId, recordingActionForm.value.projectId),
        );
    });

    const recordingScopeProjectId = computed(() => selectedCase.value?.projectId);
    const recordingScopeModuleId = computed(() => selectedCase.value?.moduleId);

    const availableRuntimeProfilesForRecording = computed(() =>
        runtimeProfiles.value.filter(
            (item) =>
                item.enabled !== false &&
                profileSupportsWeb(item) &&
                isRuntimeProfileScopeMatch(
                    item,
                    recordingScopeProjectId.value,
                    recordingScopeModuleId.value,
                ),
        ),
    );

    const availableBrowserSessionsForRecording = computed(() =>
        browserSessions.value.filter(
            (item) =>
                item.enabled !== false &&
                isRuntimeProfileScopeMatch(
                    item,
                    recordingScopeProjectId.value,
                    recordingScopeModuleId.value,
                ) &&
                isBrowserSessionBrowserMatch(item, recordingForm.value.browserName),
        ),
    );

    const replayLinkedCase = computed(() => {
        const replayRecording = selectedRecording.value;
        const replayCaseId = normalizeIdValue(replayRecording?.webCaseId);
        if (!replayCaseId) return null;
        return (
            mergeCaseOptions(
                allCaseOptions.value,
                runDetail.value ? [runDetail.value] : [],
                recordingDetail.value ? [recordingDetail.value] : [],
            ).find((item) => isSameId(item.webCaseId, replayCaseId)) || null
        );
    });

    const replayScopeProjectId = computed(() => replayLinkedCase.value?.projectId);
    const replayScopeModuleId = computed(() => replayLinkedCase.value?.moduleId);

    const availableRuntimeProfilesForReplay = computed(() =>
        runtimeProfiles.value.filter(
            (item) =>
                item.enabled !== false &&
                profileSupportsWeb(item) &&
                isRuntimeProfileScopeMatch(
                    item,
                    replayScopeProjectId.value,
                    replayScopeModuleId.value,
                ),
        ),
    );

    const availableBrowserSessionsForReplay = computed(() =>
        browserSessions.value.filter(
            (item) =>
                item.enabled !== false &&
                isRuntimeProfileScopeMatch(
                    item,
                    replayScopeProjectId.value,
                    replayScopeModuleId.value,
                ) &&
                isBrowserSessionBrowserMatch(item, replayForm.value.browserName),
        ),
    );

    const recordingLinkedCaseLabel = computed(() => {
        if (!recordingForm.value.webCaseId) return "独立录制";
        return `${getCaseName(recordingForm.value.webCaseId) || recordingForm.value.webCaseId} [${recordingForm.value.webCaseId}]`;
    });

    const recordingDialogTitle = computed(() =>
        recordingForm.value.recordingId
            ? `录制 Web 步骤 [${recordingForm.value.recordingId}]`
            : "录制 Web 步骤",
    );

    const recordingDetailTitle = computed(() => {
        if (!recordingDetail.value) return "录制详情";
        return `录制详情 - ${recordingDetail.value.sessionName || recordingDetail.value.recordingId}`;
    });

    const recordingPreviewSteps = computed(() =>
        Array.isArray(recordingDetail.value?.steps)
            ? recordingDetail.value.steps
            : [],
    );

    const recordingEventRows = computed(() =>
        Array.isArray(recordingDetail.value?.events)
            ? recordingDetail.value.events
            : [],
    );

    const recordingDetailJsonText = computed(() =>
        safeJsonStringify(recordingDetail.value || {}),
    );

    const recordingLiveStatusMeta = computed(() =>
        getRecordingStatusMeta(
            recordingDetail.value?.status ||
                (recordingForm.value.recordingId ? 2 : 1),
        ),
    );

    const recordingResultReady = computed(
        () =>
            canUseRecordingResult(recordingDetail.value?.status) &&
            liveRecordingSteps.value.length > 0,
    );

    const recordingAssertionTipText = computed(() => {
        if (!recordingForm.value.captureAssertions) {
            return "当前已关闭断言录制，仅记录操作步骤。";
        }
        const pickTip = recordingForm.value.attachAssertionsToPreviousStep
            ? "按住 Alt 点击任意元素可把断言追加到上一步（不触发点击）。"
            : "按住 Alt 点击任意元素会新增平级断言步骤（不触发点击）。";
        if (recordingForm.value.autoAssertTextOnClick) {
            return `录制技巧：普通点击会先插入“断言文本包含”再执行点击；${pickTip}`;
        }
        return `录制技巧：${pickTip} 适合新页面批量文案验收。`;
    });

    const recordingLiveStatusText = computed(() => {
        if (!recordingForm.value.recordingId) {
            return "请先填写录制参数后启动录制。";
        }
        if (recordingDetail.value?.status === 5) {
            const summaryPayload = getRecordingSummaryPayload(
                recordingDetail.value,
            );
            const summaryStatus = `${summaryPayload?.status || ""}`
                .trim()
                .toLowerCase();
            if (["cancelled", "canceled"].includes(summaryStatus)) {
                return "录制已取消。";
            }
            if (["stopped", "finished", "failed"].includes(summaryStatus)) {
                return "录制已结束。";
            }
            return "停止指令已发送，正在等待录制结果落盘。";
        }
        return `录制状态：${recordingLiveStatusMeta.value.label}`;
    });

    const recordingLiveStatusType = computed(
        () => recordingLiveStatusMeta.value.type,
    );

    const recordingActionDialogTitle = computed(() => {
        if (recordingActionMode.value === "create") return "将录制保存为新用例";
        if (recordingActionMode.value === "append") return "将录制追加到用例";
        return "使用录制覆盖用例步骤";
    });

    const recordingActionDialogTip = computed(() => {
        if (recordingActionMode.value === "create")
            return "当前录制会保存成一个独立的新 Web 用例。";
        if (recordingActionMode.value === "append")
            return "会把录制得到的步骤追加到目标用例尾部，不会覆盖原步骤。";
        return "会使用当前录制步骤替换目标用例原有步骤，请确认后再执行。";
    });

    const recordingActionSubmitText = computed(() =>
        recordingActionMode.value === "create" ? "保存新用例" : "确认应用",
    );

    const selectedReplayLabel = computed(() => {
        if (!selectedRecording.value) return "";
        return `${selectedRecording.value.sessionName || "录制回放"} [${selectedRecording.value.recordingId}]`;
    });

    const replayResultTitle = computed(() => {
        if (!replayResult.value) return "回放结果";
        return `${replayResult.value.sessionName || "录制回放"} - ${replayResult.value.status === "passed" ? "成功" : "失败"}`;
    });

    const replayStepResults = computed(() =>
        Array.isArray(replayResult.value?.result?.steps)
            ? replayResult.value.result.steps
            : [],
    );

    const replayFailureMessage = computed(() =>
        getRunRowFailureReason(replayResult.value),
    );

    const replayResultJsonText = computed(() =>
        safeJsonStringify(replayResult.value?.result || replayResult.value || {}),
    );

    /**
     * 重置录制弹窗状态。
     * @param {Record<string, any>|null} row 关联用例
     * @returns {void}
     */
    function resetRecordingDialogState(row = null) {
        stopRecordingPoll();
        selectedCase.value = row || null;
        recordingLiveTab.value = "steps";
        recordingEvents.value = [];
        liveRecordingSteps.value = [];
        recordingDetail.value = null;
        recordingDetailText.value = "";
        const runtimeSettings = isPlainObject(
            row?.runtimeSettings || row?.runtime_settings,
        )
            ? cloneData(row.runtimeSettings || row.runtime_settings)
            : {};
        const browserSessionId = normalizeIdValue(
            runtimeSettings.browserSessionId ??
                runtimeSettings.browser_session_id ??
                runtimeSettings.persistContextSessionId ??
                runtimeSettings.persist_context_session_id ??
                runtimeSettings.sessionProfileId ??
                runtimeSettings.session_profile_id,
        );
        const runtimeProfileId = normalizeIdValue(
            runtimeSettings.runtimeProfileId ??
                runtimeSettings.runtime_profile_id ??
                runtimeSettings.cookieProfileId ??
                runtimeSettings.cookie_profile_id,
        );
        const preferredStateSourceType = normalizeStateSourceType(
            runtimeSettings.stateSourceType ?? runtimeSettings.state_source_type,
        );
        const inferredStateSourceType = resolveStateSourceTypeByIds(
            browserSessionId,
            runtimeProfileId,
        );
        const stateSourceType =
            preferredStateSourceType === "none"
                ? inferredStateSourceType
                : preferredStateSourceType;
        const manualLoginEnabled = parseBooleanFlag(
            runtimeSettings.manualLoginEnabled ??
                runtimeSettings.manual_login_enabled ??
                runtimeSettings.manualLoginGate ??
                runtimeSettings.manual_login_gate,
            false,
        );
        const manualLoginRequireConfirm = parseBooleanFlag(
            runtimeSettings.manualLoginRequireConfirm ??
                runtimeSettings.manual_login_require_confirm ??
                runtimeSettings.manualLoginNeedConfirm ??
                runtimeSettings.manual_login_need_confirm,
            false,
        );
        const manualLoginWaitSec = normalizeManualLoginWaitSec(
            runtimeSettings.manualLoginWaitSec ??
                runtimeSettings.manual_login_wait_sec ??
                runtimeSettings.manualLoginTimeoutSec ??
                runtimeSettings.manual_login_timeout_sec,
            120,
        );
        const windowMaximize = parseBooleanFlag(
            runtimeSettings.windowMaximize ??
                runtimeSettings.window_maximize ??
                runtimeSettings.recordWindowMaximize ??
                runtimeSettings.record_window_maximize,
            false,
        );
        const windowWidth = normalizeOptionalPositiveInt(
            runtimeSettings.windowWidth ??
                runtimeSettings.window_width ??
                runtimeSettings.recordWindowWidth ??
                runtimeSettings.record_window_width,
        );
        const windowHeight = normalizeOptionalPositiveInt(
            runtimeSettings.windowHeight ??
                runtimeSettings.window_height ??
                runtimeSettings.recordWindowHeight ??
                runtimeSettings.record_window_height,
        );
        const persistContextEnabled = parseBooleanFlag(
            runtimeSettings.persistContextEnabled ??
                runtimeSettings.persist_context_enabled ??
                runtimeSettings.preserveBrowserContext ??
                runtimeSettings.preserve_browser_context ??
                runtimeSettings.keepBrowserCache ??
                runtimeSettings.keep_browser_cache,
            false,
        );
        const persistContextAutoSyncSession = parseBooleanFlag(
            runtimeSettings.persistContextAutoSyncSession ??
                runtimeSettings.persist_context_auto_sync_session ??
                runtimeSettings.persistContextSyncToSession ??
                runtimeSettings.persist_context_sync_to_session,
            true,
        );
        recordingForm.value = {
            webCaseId: row?.webCaseId,
            sessionName: row ? `${row.caseName}-录制` : "",
            agentId: undefined,
            browserName: row?.browserName || "chromium",
            headless: false,
            startUrl: row?.startUrl || "",
            stateSourceType,
            browserSessionId,
            runtimeProfileId,
            persistContextEnabled:
                stateSourceType !== "none" && Boolean(persistContextEnabled),
            persistContextAutoSyncSession,
            manualLoginEnabled,
            manualLoginRequireConfirm: manualLoginEnabled
                ? manualLoginRequireConfirm
                : false,
            manualLoginWaitSec,
            windowMaximize,
            windowWidth,
            windowHeight,
            closeBrowserOnStop: true,
            captureAssertions: true,
            attachAssertionsToPreviousStep: true,
            autoAssertTextOnClick: false,
            recordingId: undefined,
        };
    }

    /**
     * 打开录制弹窗。
     * @param {Record<string, any>|null} row 关联用例
     * @returns {void}
     */
    function openRecordingDialog(row = null) {
        resetRecordingDialogState(row);
        recordingAdvancedPanels.value = [];
        showRecordingDialog.value = true;
    }

    /**
     * 启动录制轮询。
     * @returns {void}
     */
    function startRecordingPoll() {
        stopRecordingPoll();
        recordingTimer = window.setInterval(() => {
            if (recordingForm.value.recordingId) {
                refreshRecording();
            }
        }, 3000);
    }

    /**
     * 停止录制轮询。
     * @returns {void}
     */
    function stopRecordingPoll() {
        if (recordingTimer) {
            window.clearInterval(recordingTimer);
            recordingTimer = null;
        }
    }

    /**
     * 更新录制实时数据。
     * @param {Record<string, any>} detail 录制详情
     * @returns {void}
     */
    function updateLiveRecording(detail) {
        recordingDetail.value = detail;
        recordingEvents.value = detail.events || [];
        liveRecordingSteps.value = detail.steps || [];
        recordingDetailText.value = safeJsonStringify(detail);
        if (shouldStopRecordingPoll(detail)) {
            stopRecordingPoll();
            loadBrowserSessions().catch(() => {});
        }
    }

    /**
     * 获取录制详情。
     * @param {string|number} recordingId 录制ID
     * @returns {Promise<Record<string, any>>} 详情数据
     */
    function fetchRecordingDetail(recordingId) {
        return getWebRecording(recordingId).then((response) => response.data || {});
    }

    /**
     * 启动录制。
     * @returns {Promise<void>} 启动完成
     */
    async function startRecording() {
        if (!recordingForm.value.agentId) {
            ElMessage.error("请选择执行 Agent");
            return;
        }
        if (!recordingForm.value.startUrl?.trim()) {
            ElMessage.error("请填写录制起始地址");
            return;
        }

        const manualLoginEnabled = Boolean(recordingForm.value.manualLoginEnabled);
        const manualLoginRequireConfirm =
            manualLoginEnabled &&
            Boolean(recordingForm.value.manualLoginRequireConfirm);
        const manualLoginWaitSec = normalizeManualLoginWaitSec(
            recordingForm.value.manualLoginWaitSec,
            120,
        );
        const stateSourceType = normalizeStateSourceType(
            recordingForm.value.stateSourceType,
        );
        const selectedBrowserSessionId =
            stateSourceType === "session"
                ? normalizeIdValue(recordingForm.value.browserSessionId)
                : undefined;
        const selectedRuntimeProfileId =
            stateSourceType === "cookie"
                ? normalizeIdValue(recordingForm.value.runtimeProfileId)
                : undefined;
        const persistContextEnabled = Boolean(
            stateSourceType !== "none" &&
                recordingForm.value.persistContextEnabled,
        );
        const persistContextAutoSyncSession = Boolean(
            stateSourceType !== "none" &&
                persistContextEnabled &&
                recordingForm.value.persistContextAutoSyncSession,
        );
        const windowMaximize = Boolean(recordingForm.value.windowMaximize);
        const hasWindowWidthInput =
            recordingForm.value.windowWidth !== undefined &&
            recordingForm.value.windowWidth !== null &&
            recordingForm.value.windowWidth !== "";
        const hasWindowHeightInput =
            recordingForm.value.windowHeight !== undefined &&
            recordingForm.value.windowHeight !== null &&
            recordingForm.value.windowHeight !== "";
        let windowWidth = normalizeOptionalPositiveInt(recordingForm.value.windowWidth);
        let windowHeight = normalizeOptionalPositiveInt(
            recordingForm.value.windowHeight,
        );
        if (!windowMaximize && (hasWindowWidthInput || hasWindowHeightInput)) {
            if (!windowWidth || !windowHeight) {
                ElMessage.error("录制窗口宽高必须同时为正整数，或清空后使用默认尺寸");
                return;
            }
        }
        if (windowMaximize) {
            windowWidth = undefined;
            windowHeight = undefined;
        }

        loading.value.recording = true;
        if (manualLoginEnabled && !manualLoginRequireConfirm) {
            ElMessage.info(
                `浏览器启动后将预留 ${manualLoginWaitSec} 秒手动登录时间，再开始录制`,
            );
        }
        try {
            const response = await startWebRecording({
                webCaseId: recordingForm.value.webCaseId,
                agentId: recordingForm.value.agentId,
                sessionName: recordingForm.value.sessionName || undefined,
                browserName: recordingForm.value.browserName,
                headless: recordingForm.value.headless,
                startUrl: recordingForm.value.startUrl,
                stateSourceType,
                browserSessionId: selectedBrowserSessionId,
                runtimeProfileId: selectedRuntimeProfileId,
                persistContextEnabled,
                persistContextAutoSyncSession,
                manualLoginEnabled,
                manualLoginRequireConfirm,
                manualLoginWaitSec,
                recordingOptions: {
                    closeBrowserOnStop: recordingForm.value.closeBrowserOnStop,
                    captureAssertions: recordingForm.value.captureAssertions,
                    assertionAttachMode: recordingForm.value.captureAssertions
                        ? recordingForm.value.attachAssertionsToPreviousStep
                            ? "inside_step"
                            : "parallel_step"
                        : "parallel_step",
                    autoAssertTextOnClick:
                        recordingForm.value.captureAssertions &&
                        recordingForm.value.autoAssertTextOnClick,
                    windowMaximize,
                    windowWidth,
                    windowHeight,
                },
            });
            recordingForm.value.recordingId = response.data?.recordingId;
            ElMessage.success(response.msg || "录制已启动");
            refreshRecording();
            startRecordingPoll();
            await refreshRecordingTab();
            if (manualLoginRequireConfirm && recordingForm.value.recordingId) {
                await confirmAndContinueRecordingManualLogin({
                    recordingId: recordingForm.value.recordingId,
                    agentId: recordingForm.value.agentId,
                    sessionName: recordingForm.value.sessionName,
                });
                ElMessage.success("已确认继续录制");
                refreshRecording();
                await refreshRecordingTab();
            }
        } catch (error) {
            const msg =
                error?.response?.data?.msg || error?.message || "录制启动失败";
            ElMessage.error(msg);
        } finally {
            loading.value.recording = false;
        }
    }

    /**
     * 停止录制。
     * @returns {void}
     */
    function stopRecording() {
        if (!recordingForm.value.recordingId) return;
        stopWebRecording({
            recordingId: recordingForm.value.recordingId,
            agentId: recordingForm.value.agentId,
            closeBrowserOnStop: recordingForm.value.closeBrowserOnStop,
        }).then((response) => {
            ElMessage.success(response.msg || "已发送停止录制指令");
            refreshRecording();
            refreshRecordingTab();
            loadBrowserSessions().catch(() => {});
        });
    }

    /**
     * 刷新录制详情。
     * @returns {void}
     */
    function refreshRecording() {
        if (!recordingForm.value.recordingId) return;
        fetchRecordingDetail(recordingForm.value.recordingId).then((detail) => {
            updateLiveRecording(detail);
        });
    }

    /**
     * 停止录制详情轮询。
     * @returns {void}
     */
    function stopRecordingDetailPoll() {
        if (recordingDetailTimer) {
            window.clearInterval(recordingDetailTimer);
            recordingDetailTimer = null;
        }
    }

    /**
     * 刷新录制详情弹窗数据。
     * @returns {Promise<Record<string, any>|null>} 最新详情
     */
    function refreshRecordingDetail() {
        const recordingId = normalizeIdValue(recordingDetail.value?.recordingId);
        if (!recordingId || !showRecordingDetailDialog.value) {
            return Promise.resolve(null);
        }
        return fetchRecordingDetail(recordingId).then((detail) => {
            recordingDetail.value = detail;
            syncCaseOptions(detail);
            selectedRecording.value = detail;
            if (shouldStopRecordingPoll(detail)) {
                stopRecordingDetailPoll();
            }
            return detail;
        });
    }

    /**
     * 启动录制详情轮询。
     * @returns {void}
     */
    function startRecordingDetailPoll() {
        stopRecordingDetailPoll();
        if (
            !recordingDetail.value?.recordingId ||
            shouldStopRecordingPoll(recordingDetail.value)
        ) {
            return;
        }
        recordingDetailTimer = window.setInterval(() => {
            refreshRecordingDetail();
        }, 3000);
    }

    /**
     * 打开录制详情。
     * @param {number|Record<string, any>} recordingSource 录制来源
     * @returns {void}
     */
    function openRecordingDetail(recordingSource) {
        const recordingId =
            typeof recordingSource === "number"
                ? recordingSource
                : recordingSource?.recordingId;
        if (!recordingId) return;
        stopRecordingDetailPoll();
        loading.value.recordingDetail = true;
        fetchRecordingDetail(recordingId)
            .then((detail) => {
                recordingDetail.value = detail;
                syncCaseOptions(detail);
                selectedRecording.value = detail;
                showRecordingDetailDialog.value = true;
                startRecordingDetailPoll();
            })
            .finally(() => {
                loading.value.recordingDetail = false;
            });
    }

    /**
     * 构造录制结果应用默认值。
     * @param {Record<string, any>} detail 录制详情
     * @returns {Record<string, any>} 默认表单
     */
    function buildRecordingActionDefaults(detail) {
        const linkedCase = mergeCaseOptions(
            allCaseOptions.value,
            caseSelectOptions.value,
        ).find((item) => isSameId(item.webCaseId, detail.webCaseId));
        return {
            recordingId: detail.recordingId,
            webCaseId: normalizeIdValue(
                detail.webCaseId || selectedCase.value?.webCaseId,
            ),
            caseName: `${linkedCase?.caseName || detail.sessionName || "录制结果"}-${detail.recordingId}`,
            projectId: linkedCase?.projectId,
            moduleId: linkedCase?.moduleId,
            startUrl: detail.startUrl || linkedCase?.startUrl || "",
            browserName:
                detail.browserName || linkedCase?.browserName || "chromium",
            headless: detail.headless ?? linkedCase?.headless ?? false,
            notes:
                linkedCase?.notes ||
                `由录制[${detail.sessionName || detail.recordingId}]生成`,
        };
    }

    /**
     * 解析录制来源。
     * @param {number|Record<string, any>} recordingSource 录制来源
     * @returns {Promise<Record<string, any>|null>} 录制详情
     */
    function resolveRecordingSource(recordingSource) {
        if (typeof recordingSource === "number") {
            return fetchRecordingDetail(recordingSource);
        }
        if (recordingSource?.recordingId && Array.isArray(recordingSource.steps)) {
            return Promise.resolve(recordingSource);
        }
        if (recordingSource?.recordingId) {
            return fetchRecordingDetail(recordingSource.recordingId);
        }
        return Promise.resolve(null);
    }

    /**
     * 打开录制结果应用弹窗。
     * @param {"create"|"append"|"replace"} mode 应用模式
     * @param {number|Record<string, any>} recordingSource 录制来源
     * @returns {void}
     */
    function openRecordingActionDialog(mode, recordingSource) {
        resolveRecordingSource(recordingSource).then((detail) => {
            if (!detail?.recordingId) {
                ElMessage.error("未找到可用录制记录");
                return;
            }
            if (!canUseRecordingResult(detail.status)) {
                ElMessage.warning("录制仍在进行中，请先停止录制并等待结果生成");
                return;
            }
            if (!Array.isArray(detail.steps) || !detail.steps.length) {
                ElMessage.warning("当前录制记录中没有可保存的步骤");
                return;
            }
            recordingActionMode.value = mode;
            selectedRecording.value = detail;
            recordingActionForm.value = buildRecordingActionDefaults(detail);
            showRecordingActionDialog.value = true;
        });
    }

    /**
     * 提交录制结果应用。
     * @returns {void}
     */
    function submitRecordingAction() {
        if (!recordingActionForm.value.recordingId) {
            ElMessage.error("缺少录制会话ID");
            return;
        }

        const mode = recordingActionMode.value;
        if (mode === "create" && !recordingActionForm.value.caseName?.trim()) {
            ElMessage.error("请输入新用例名称");
            return;
        }
        if (mode !== "create" && !recordingActionForm.value.webCaseId) {
            ElMessage.error("请选择目标用例");
            return;
        }

        loading.value.recordingAction = true;
        const promise =
            mode === "create"
                ? saveWebRecordingAsCase({
                      recordingId: recordingActionForm.value.recordingId,
                      caseName: recordingActionForm.value.caseName,
                      projectId: recordingActionForm.value.projectId,
                      moduleId: recordingActionForm.value.moduleId,
                      startUrl: recordingActionForm.value.startUrl,
                      browserName: recordingActionForm.value.browserName,
                      headless: recordingActionForm.value.headless,
                      notes: recordingActionForm.value.notes,
                  })
                : applyWebRecording({
                      recordingId: recordingActionForm.value.recordingId,
                      webCaseId: recordingActionForm.value.webCaseId,
                      replaceSteps: mode === "replace",
                  });

        promise
            .then(async (response) => {
                ElMessage.success(response.msg || "操作成功");
                showRecordingActionDialog.value = false;
                await loadAllCaseOptions(true);
                await refreshCaseTab();
                await refreshRecordingTab();
                if (mode === "create" && response.data?.webCaseId) {
                    activeTab.value = "case";
                    handleEdit(response.data);
                }
            })
            .finally(() => {
                loading.value.recordingAction = false;
            });
    }

    /**
     * 打开录制回放弹窗。
     * @param {number|Record<string, any>} recordingSource 录制来源
     * @returns {void}
     */
    function openReplayDialog(recordingSource) {
        resolveRecordingSource(recordingSource).then((detail) => {
            if (!detail?.recordingId) {
                ElMessage.error("未找到可用录制记录");
                return;
            }
            if (!canUseRecordingResult(detail.status)) {
                ElMessage.warning("录制仍在进行中，请先停止录制并等待结果生成");
                return;
            }
            if (!Array.isArray(detail.steps) || !detail.steps.length) {
                ElMessage.warning("当前录制记录中没有可回放的步骤");
                return;
            }
            const recordingOptions = isPlainObject(detail.options)
                ? cloneData(detail.options)
                : {};
            const runtimeSettings = isPlainObject(
                recordingOptions.runtimeOptions ||
                    recordingOptions.runtime_options,
            )
                ? cloneData(
                      recordingOptions.runtimeOptions ||
                          recordingOptions.runtime_options,
                  )
                : {};
            const browserSessionId = normalizeIdValue(
                runtimeSettings.browserSessionId ??
                    runtimeSettings.browser_session_id ??
                    runtimeSettings.persistContextSessionId ??
                    runtimeSettings.persist_context_session_id ??
                    runtimeSettings.sessionProfileId ??
                    runtimeSettings.session_profile_id,
            );
            const runtimeProfileId = normalizeIdValue(
                runtimeSettings.runtimeProfileId ??
                    runtimeSettings.runtime_profile_id ??
                    runtimeSettings.cookieProfileId ??
                    runtimeSettings.cookie_profile_id,
            );
            const preferredStateSourceType = normalizeStateSourceType(
                runtimeSettings.stateSourceType ??
                    runtimeSettings.state_source_type,
            );
            const inferredStateSourceType = resolveStateSourceTypeByIds(
                browserSessionId,
                runtimeProfileId,
            );
            const stateSourceType =
                preferredStateSourceType === "none"
                    ? inferredStateSourceType
                    : preferredStateSourceType;
            const persistContextEnabled = parseBooleanFlag(
                runtimeSettings.persistContextEnabled ??
                    runtimeSettings.persist_context_enabled ??
                    runtimeSettings.preserveBrowserContext ??
                    runtimeSettings.preserve_browser_context ??
                    runtimeSettings.keepBrowserCache ??
                    runtimeSettings.keep_browser_cache,
                false,
            );
            const persistContextAutoSyncSession = parseBooleanFlag(
                runtimeSettings.persistContextAutoSyncSession ??
                    runtimeSettings.persist_context_auto_sync_session ??
                    runtimeSettings.persistContextSyncToSession ??
                    runtimeSettings.persist_context_sync_to_session,
                true,
            );
            const locatorIndexMode = normalizeLocatorIndexMode(
                runtimeSettings.locatorIndexMode ??
                    runtimeSettings.locator_index_mode ??
                    runtimeSettings.locatorIndexStrategy ??
                    runtimeSettings.locator_index_strategy ??
                    runtimeSettings.locatorImmediateIndex ??
                    runtimeSettings.locator_immediate_index,
            );
            selectedRecording.value = detail;
            replayForm.value = {
                recordingId: detail.recordingId,
                agentId: undefined,
                browserName: detail.browserName || "chromium",
                headless: detail.headless ?? false,
                closeBrowserOnFinish: true,
                immediateLocatorIndexMode: locatorIndexMode === "always",
                stateSourceType,
                browserSessionId,
                runtimeProfileId,
                persistContextEnabled:
                    stateSourceType !== "none" && Boolean(persistContextEnabled),
                persistContextAutoSyncSession,
            };
            showReplayDialog.value = true;
        });
    }

    /**
     * 提交录制回放。
     * @returns {void}
     */
    function submitReplay() {
        if (!replayForm.value.recordingId) {
            ElMessage.error("缺少录制会话ID");
            return;
        }
        if (!replayForm.value.agentId) {
            ElMessage.error("请选择执行 Agent");
            return;
        }

        const stateSourceType = normalizeStateSourceType(
            replayForm.value.stateSourceType,
        );
        const selectedBrowserSessionId =
            stateSourceType === "session"
                ? normalizeIdValue(replayForm.value.browserSessionId)
                : undefined;
        const selectedRuntimeProfileId =
            stateSourceType === "cookie"
                ? normalizeIdValue(replayForm.value.runtimeProfileId)
                : undefined;
        const persistContextEnabled = Boolean(
            stateSourceType !== "none" && replayForm.value.persistContextEnabled,
        );
        const persistContextAutoSyncSession = Boolean(
            stateSourceType !== "none" &&
                persistContextEnabled &&
                replayForm.value.persistContextAutoSyncSession,
        );
        const runtimeOverrides = {
            locatorIndexMode: replayForm.value.immediateLocatorIndexMode
                ? "always"
                : "auto",
        };

        loading.value.replay = true;
        replayWebRecording({
            recordingId: replayForm.value.recordingId,
            agentId: replayForm.value.agentId,
            browserName: replayForm.value.browserName,
            headless: replayForm.value.headless,
            closeBrowserOnFinish: replayForm.value.closeBrowserOnFinish,
            stateSourceType,
            browserSessionId: selectedBrowserSessionId,
            runtimeProfileId: selectedRuntimeProfileId,
            persistContextEnabled,
            persistContextAutoSyncSession,
            runtimeOverrides,
        })
            .then((response) => {
                replayResult.value = response.data || null;
                showReplayDialog.value = false;
                showReplayResultDialog.value = true;
                ElMessage.success(response.msg || "回放完成");
            })
            .finally(() => {
                loading.value.replay = false;
            });
    }

    watch(
        () => recordingActionForm.value.projectId,
        (projectId) => {
            if (!projectId) return;
            if (
                !filteredRecordingActionModules.value.some((item) =>
                    isSameId(item.moduleId, recordingActionForm.value.moduleId),
                )
            ) {
                recordingActionForm.value.moduleId = undefined;
            }
        },
    );

    watch(
        () => recordingForm.value.stateSourceType,
        (stateType) => {
            const normalized = normalizeStateSourceType(stateType);
            if (normalized !== stateType) {
                recordingForm.value.stateSourceType = normalized;
                return;
            }
            if (normalized !== "session") {
                recordingForm.value.browserSessionId = undefined;
            }
            if (normalized !== "cookie") {
                recordingForm.value.runtimeProfileId = undefined;
            }
            if (normalized === "none") {
                recordingForm.value.persistContextEnabled = false;
                recordingForm.value.persistContextAutoSyncSession = false;
            } else {
                recordingForm.value.persistContextEnabled = true;
                recordingForm.value.persistContextAutoSyncSession = true;
            }
        },
    );

    watch(
        () => replayForm.value.stateSourceType,
        (stateType) => {
            const normalized = normalizeStateSourceType(stateType);
            if (normalized !== stateType) {
                replayForm.value.stateSourceType = normalized;
                return;
            }
            if (normalized !== "session") {
                replayForm.value.browserSessionId = undefined;
            }
            if (normalized !== "cookie") {
                replayForm.value.runtimeProfileId = undefined;
            }
            if (normalized === "none") {
                replayForm.value.persistContextEnabled = false;
                replayForm.value.persistContextAutoSyncSession = false;
            } else {
                replayForm.value.persistContextEnabled = true;
                replayForm.value.persistContextAutoSyncSession = true;
            }
        },
    );

    watch(availableBrowserSessionsForRecording, (sessions) => {
        if (recordingForm.value.stateSourceType !== "session") return;
        const selectedSessionId = normalizeIdValue(
            recordingForm.value.browserSessionId,
        );
        if (!selectedSessionId) return;
        if (!sessions.some((item) => isSameId(item.sessionId, selectedSessionId))) {
            recordingForm.value.browserSessionId = undefined;
        }
    });

    watch(availableBrowserSessionsForReplay, (sessions) => {
        if (replayForm.value.stateSourceType !== "session") return;
        const selectedSessionId = normalizeIdValue(replayForm.value.browserSessionId);
        if (!selectedSessionId) return;
        if (!sessions.some((item) => isSameId(item.sessionId, selectedSessionId))) {
            replayForm.value.browserSessionId = undefined;
        }
    });

    watch(availableRuntimeProfilesForRecording, (profiles) => {
        if (recordingForm.value.stateSourceType !== "cookie") return;
        const selectedProfileId = normalizeIdValue(
            recordingForm.value.runtimeProfileId,
        );
        if (!selectedProfileId) return;
        if (!profiles.some((item) => isSameId(item.profileId, selectedProfileId))) {
            recordingForm.value.runtimeProfileId = undefined;
        }
    });

    watch(availableRuntimeProfilesForReplay, (profiles) => {
        if (replayForm.value.stateSourceType !== "cookie") return;
        const selectedProfileId = normalizeIdValue(replayForm.value.runtimeProfileId);
        if (!selectedProfileId) return;
        if (!profiles.some((item) => isSameId(item.profileId, selectedProfileId))) {
            replayForm.value.runtimeProfileId = undefined;
        }
    });

    onBeforeUnmount(() => {
        stopRecordingPoll();
        stopRecordingDetailPoll();
    });

    return {
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
        openBrowserSessionDialog,
        openRuntimeProfileDialog,
        formatRuntimeProfileLabel,
        formatBrowserSessionLabel,
        searchCaseOptions,
        handleCaseSelectVisibleChange,
        caseSelectOptions,
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
        getActionLabel,
        describeStepTarget,
        summarizeStepParams,
        getCaseName,
        getRecordingStatusMeta,
        formatTime,
        getStepStatusTagType,
        getStepFailureReason,
        formatDuration,
        canUseRecordingResult,
    };
}
