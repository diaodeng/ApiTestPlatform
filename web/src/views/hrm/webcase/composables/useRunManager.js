import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";

/**
 * 执行业务域组合式逻辑。
 * @param {Object} options 依赖项
 * @returns {Object} 执行相关状态与方法
 */
export function useRunManager(options) {
    const {
        ElMessage,
        loading,
        activeTab,
        runTabRef,
        webCredentialBindingOptions,
        syncCaseOptions,
        refreshRunTab,
        normalizeCaseOption,
        normalizeIdValue,
        normalizeManualLoginWaitSec,
        normalizeLocatorIndexMode,
        parseBooleanFlag,
        isPlainObject,
        cloneData,
        safeJsonStringify,
        getCaseName,
        getRunRowFailureReason,
        shouldStopRunDetailPoll,
        confirmAndContinueRunManualLogin,
        runWebCase,
        getWebRun,
    } = options;

    const selectedCase = ref(null);
    const runTargetCases = ref([]);
    const runDetail = ref(null);
    const showRunDialog = ref(false);
    const showRunDetailDialog = ref(false);
    const runDetailTab = ref("steps");
    const runAdvancedPanels = ref([]);
    const runForm = ref({
        agentId: undefined,
        browserName: "chromium",
        headless: true,
        closeBrowserOnFinish: true,
        immediateLocatorIndexMode: false,
        credentialBindingId: undefined,
        persistContextEnabled: false,
        persistContextAutoSyncSession: false,
        manualLoginEnabled: false,
        manualLoginRequireConfirm: false,
        manualLoginWaitSec: 120,
        stepTimeoutMs: undefined,
        stepThinkTimeMs: undefined,
    });

    let runDetailTimer = null;

    const runDetailTitle = computed(() => {
        if (!runDetail.value) return "执行详情";
        return `执行详情 - ${runDetail.value.caseName || getCaseName(runDetail.value.webCaseId) || runDetail.value.webCaseId}`;
    });

    const runTargetLabel = computed(() => {
        const targets = Array.isArray(runTargetCases.value)
            ? runTargetCases.value
            : [];
        if (!targets.length) return "";
        if (targets.length === 1) {
            const target = targets[0];
            return `${target.caseName || target.webCaseId} [${target.webCaseId}]`;
        }
        const previewText = targets
            .slice(0, 5)
            .map((item) => `${item.caseName || item.webCaseId} [${item.webCaseId}]`)
            .join("，");
        return `已选择 ${targets.length} 条用例：${previewText}${targets.length > 5 ? " ..." : ""}`;
    });

    const runStepResults = computed(() =>
        Array.isArray(runDetail.value?.result?.steps)
            ? runDetail.value.result.steps
            : [],
    );

    const runRuntimeDebug = computed(() =>
        isPlainObject(runDetail.value?.result?.runtimeDebug)
            ? runDetail.value.result.runtimeDebug
            : null,
    );

    const runDetailStateSourceType = computed(() => {
        const resultPayload = isPlainObject(runDetail.value?.result)
            ? runDetail.value.result
            : {};
        const runtimeDebug = isPlainObject(resultPayload.runtimeDebug)
            ? resultPayload.runtimeDebug
            : {};
        const runtimeOptions = isPlainObject(resultPayload.runtimeOptions)
            ? resultPayload.runtimeOptions
            : {};
        const credentialBindingId = normalizeIdValue(
            runtimeDebug.credentialBindingId ??
                runtimeDebug.credential_binding_id ??
                runtimeOptions.credentialBindingId ??
                runtimeOptions.credential_binding_id,
        );
        return credentialBindingId ? "credential" : "none";
    });

    const runDetailFailureMessage = computed(() => {
        const message = getRunRowFailureReason(runDetail.value);
        return message === "-" ? "" : message;
    });

    const runCookieApplySummary = computed(() => {
        if (runDetailStateSourceType.value !== "cookie") {
            return "";
        }
        const runtimeDebug = runRuntimeDebug.value;
        if (!runtimeDebug) {
            return "";
        }
        const cookieApply = isPlainObject(runtimeDebug.beforeStartCookieApply)
            ? runtimeDebug.beforeStartCookieApply
            : null;
        if (!cookieApply) {
            return "";
        }
        const appliedCount = Number(cookieApply.appliedCount || 0);
        const rules = Array.isArray(cookieApply.rules)
            ? cookieApply.rules
                  .map((item) => `${item || ""}`.trim())
                  .filter(Boolean)
            : [];
        if (appliedCount > 0) {
            return `启动前已注入 ${appliedCount} 个 Cookie${rules.length ? `（规则：${rules.join("，")}）` : ""}`;
        }
        return "启动前未注入 Cookie，请检查配置规则的 host/domain/path 与目标站点是否匹配";
    });

    const runCookieApplySummaryType = computed(() => {
        if (runDetailStateSourceType.value !== "cookie") {
            return "info";
        }
        const runtimeDebug = runRuntimeDebug.value;
        if (!runtimeDebug) {
            return "info";
        }
        const cookieApply = isPlainObject(runtimeDebug.beforeStartCookieApply)
            ? runtimeDebug.beforeStartCookieApply
            : null;
        if (!cookieApply) {
            return "info";
        }
        const appliedCount = Number(cookieApply.appliedCount || 0);
        return appliedCount > 0 ? "success" : "warning";
    });

    const runStepsJsonText = computed(() =>
        safeJsonStringify(runStepResults.value),
    );

    /**
     * 按用例初始化执行表单。
     * @param {Record<string, any>} row 用例数据
     * @returns {void}
     */
    function initRunFormByCase(row) {
        const runtimeSettings = isPlainObject(
            row?.runtimeSettings || row?.runtime_settings,
        )
            ? cloneData(row.runtimeSettings || row.runtime_settings)
            : {};
        const credentialBindingId = normalizeIdValue(
            runtimeSettings.credentialBindingId ?? runtimeSettings.credential_binding_id,
        );
        const stepTimeoutCandidate = Number(
            runtimeSettings.stepTimeoutMs ??
                runtimeSettings.step_timeout_ms ??
                runtimeSettings.timeoutMs ??
                runtimeSettings.timeout_ms,
        );
        const stepThinkCandidate = Number(
            runtimeSettings.stepThinkTimeMs ??
                runtimeSettings.step_think_time_ms ??
                runtimeSettings.thinkTimeMs ??
                runtimeSettings.think_time_ms,
        );
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
        const closeBrowserOnFinish = parseBooleanFlag(
            runtimeSettings.closeBrowserOnFinish ??
                runtimeSettings.close_browser_on_finish,
            true,
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
        const locatorIndexMode = normalizeLocatorIndexMode(
            runtimeSettings.locatorIndexMode ??
                runtimeSettings.locator_index_mode ??
                runtimeSettings.locatorIndexStrategy ??
                runtimeSettings.locator_index_strategy ??
                runtimeSettings.locatorImmediateIndex ??
                runtimeSettings.locator_immediate_index,
        );
        runForm.value = {
            agentId: undefined,
            browserName: row?.browserName || "chromium",
            headless: row?.headless ?? true,
            closeBrowserOnFinish,
            immediateLocatorIndexMode: locatorIndexMode === "always",
            credentialBindingId,
            persistContextEnabled: credentialBindingId ? Boolean(persistContextEnabled) : false,
            persistContextAutoSyncSession,
            manualLoginEnabled,
            manualLoginRequireConfirm: manualLoginEnabled
                ? manualLoginRequireConfirm
                : false,
            manualLoginWaitSec,
            stepTimeoutMs:
                Number.isFinite(stepTimeoutCandidate) && stepTimeoutCandidate >= 500
                    ? Math.round(stepTimeoutCandidate)
                    : undefined,
            stepThinkTimeMs:
                Number.isFinite(stepThinkCandidate) && stepThinkCandidate >= 0
                    ? Math.round(stepThinkCandidate)
                    : undefined,
        };
    }

    /**
     * 打开执行弹窗。
     * @param {Record<string, any>} row 用例数据
     * @returns {void}
     */
    function openRunDialog(row) {
        const normalized = normalizeCaseOption(row) || row;
        selectedCase.value = normalized;
        runTargetCases.value = normalized?.webCaseId ? [normalized] : [];
        initRunFormByCase(normalized);
        runAdvancedPanels.value = [];
        showRunDialog.value = true;
    }

    /**
     * 打开批量执行弹窗。
     * @param {Array<Record<string, any>>} rows 用例列表
     * @returns {void}
     */
    function openBatchRunDialog(rows = []) {
        const candidates = (Array.isArray(rows) ? rows : [])
            .map((item) => normalizeCaseOption(item) || item)
            .filter((item) => item?.webCaseId);
        if (!candidates.length) {
            ElMessage.warning("请先勾选至少一条用例");
            return;
        }
        const uniqueTargets = Array.from(
            new Map(candidates.map((item) => [item.webCaseId, item])).values(),
        );
        selectedCase.value = uniqueTargets[0];
        runTargetCases.value = uniqueTargets;
        initRunFormByCase(uniqueTargets[0]);
        runAdvancedPanels.value = [];
        showRunDialog.value = true;
    }

    /**
     * 打开执行历史标签页。
     * @param {Record<string, any>} row 用例数据
     * @returns {void}
     */
    function openRunHistory(row) {
        activeTab.value = "run";
        nextTick(() => {
            runTabRef.value?.openHistoryByCase?.(row.webCaseId);
        });
    }

    /**
     * 停止执行详情轮询。
     * @returns {void}
     */
    function stopRunDetailPoll() {
        if (runDetailTimer) {
            window.clearInterval(runDetailTimer);
            runDetailTimer = null;
        }
    }

    /**
     * 刷新执行详情。
     * @returns {Promise<Record<string, any>|null>} 最新详情
     */
    function refreshRunDetail() {
        const runId = normalizeIdValue(runDetail.value?.webCaseRunId);
        if (!runId || !showRunDetailDialog.value) {
            return Promise.resolve(null);
        }
        return getWebRun(runId).then((response) => {
            runDetail.value = response.data || null;
            syncCaseOptions(runDetail.value);
            if (shouldStopRunDetailPoll(runDetail.value?.status)) {
                stopRunDetailPoll();
            }
            return runDetail.value;
        });
    }

    /**
     * 启动执行详情轮询。
     * @returns {void}
     */
    function startRunDetailPoll() {
        stopRunDetailPoll();
        if (
            !runDetail.value?.webCaseRunId ||
            shouldStopRunDetailPoll(runDetail.value?.status)
        ) {
            return;
        }
        runDetailTimer = window.setInterval(() => {
            refreshRunDetail();
        }, 3000);
    }

    /**
     * 打开执行详情。
     * @param {Record<string, any>} row 执行记录
     * @returns {void}
     */
    function openRunDetail(row) {
        const runId = normalizeIdValue(row?.webCaseRunId);
        if (!runId) return;
        stopRunDetailPoll();
        runDetailTab.value = "steps";
        loading.value.runDetail = true;
        getWebRun(runId)
            .then((response) => {
                runDetail.value = response.data || null;
                syncCaseOptions(runDetail.value);
                showRunDetailDialog.value = true;
                startRunDetailPoll();
            })
            .finally(() => {
                loading.value.runDetail = false;
            });
    }

    /**
     * 提交执行请求。
     * @returns {Promise<void>} 提交完成
     */
    async function submitRun() {
        const runTargets =
            Array.isArray(runTargetCases.value) && runTargetCases.value.length
                ? runTargetCases.value.filter((item) => item?.webCaseId)
                : selectedCase.value?.webCaseId
                  ? [selectedCase.value]
                  : [];
        if (!runTargets.length) {
            ElMessage.error("请选择要执行的用例");
            return;
        }
        if (!runForm.value.agentId) {
            ElMessage.error("请选择执行 Agent");
            return;
        }

        const runtimeOverrides = {
            locatorIndexMode: runForm.value.immediateLocatorIndexMode
                ? "always"
                : "auto",
        };
        if (
            runForm.value.stepTimeoutMs !== undefined &&
            runForm.value.stepTimeoutMs !== null &&
            runForm.value.stepTimeoutMs !== ""
        ) {
            const stepTimeoutMs = Math.round(Number(runForm.value.stepTimeoutMs));
            if (!Number.isFinite(stepTimeoutMs) || stepTimeoutMs < 500) {
                ElMessage.error("单步超时覆盖必须大于等于 500ms");
                return;
            }
            runtimeOverrides.stepTimeoutMs = stepTimeoutMs;
        }
        if (
            runForm.value.stepThinkTimeMs !== undefined &&
            runForm.value.stepThinkTimeMs !== null &&
            runForm.value.stepThinkTimeMs !== ""
        ) {
            const stepThinkTimeMs = Math.round(
                Number(runForm.value.stepThinkTimeMs),
            );
            if (!Number.isFinite(stepThinkTimeMs) || stepThinkTimeMs < 0) {
                ElMessage.error("步骤思考时间必须大于等于 0ms");
                return;
            }
            runtimeOverrides.stepThinkTimeMs = stepThinkTimeMs;
        }
        const manualLoginEnabled = Boolean(runForm.value.manualLoginEnabled);
        const manualLoginRequireConfirm =
            manualLoginEnabled && Boolean(runForm.value.manualLoginRequireConfirm);
        const manualLoginWaitSec = normalizeManualLoginWaitSec(
            runForm.value.manualLoginWaitSec,
            120,
        );
        const selectedCredentialBindingId = normalizeIdValue(runForm.value.credentialBindingId);
        const stateSourceType = selectedCredentialBindingId ? "credential" : "none";
        const persistContextEnabled = Boolean(
            Boolean(selectedCredentialBindingId && runForm.value.persistContextEnabled),
        );
        const persistContextAutoSyncSession = Boolean(
            stateSourceType !== "none" &&
                persistContextEnabled &&
                runForm.value.persistContextAutoSyncSession,
        );

        loading.value.run = true;
        try {
            if (manualLoginEnabled && !manualLoginRequireConfirm) {
                ElMessage.info(
                    `浏览器启动后将预留 ${manualLoginWaitSec} 秒手动登录时间，再开始正式执行`,
                );
            }
            if (manualLoginRequireConfirm) {
                ElMessage.info(
                    "已开启“登录后确认继续”：仅首条执行会暂停等待你确认，后续用例直接执行",
                );
            }
            let successCount = 0;
            let failedCount = 0;
            let reuseRetainedSessionId = "";
            const runResponses = [];
            for (let index = 0; index < runTargets.length; index++) {
                const target = runTargets[index];
                const enableManualForCurrent =
                    manualLoginEnabled &&
                    (!manualLoginRequireConfirm || index === 0);
                const requireConfirmForCurrent =
                    manualLoginRequireConfirm && index === 0;
                const runtimeOverridesForCurrent = { ...runtimeOverrides };
                if (!runForm.value.closeBrowserOnFinish && reuseRetainedSessionId) {
                    runtimeOverridesForCurrent.reuseRetainedSessionId =
                        reuseRetainedSessionId;
                }
                const payload = {
                    webCaseId: target.webCaseId,
                    agentId: runForm.value.agentId,
                    browserName: runForm.value.browserName,
                    headless: runForm.value.headless,
                    closeBrowserOnFinish: runForm.value.closeBrowserOnFinish,
                    stateSourceType,
                    credentialBindingId: selectedCredentialBindingId,
                    persistContextEnabled,
                    persistContextAutoSyncSession,
                    manualLoginEnabled: enableManualForCurrent,
                    manualLoginRequireConfirm: requireConfirmForCurrent,
                    manualLoginWaitSec,
                };
                if (Object.keys(runtimeOverridesForCurrent).length) {
                    payload.runtimeOverrides = runtimeOverridesForCurrent;
                }
                try {
                    let response = await runWebCase(payload);
                    if (requireConfirmForCurrent) {
                        const runId = response?.data?.webCaseRunId;
                        if (!runId) {
                            throw new Error("执行准备成功但未返回执行记录ID，无法继续");
                        }
                        response = await confirmAndContinueRunManualLogin({
                            runId,
                            agentId: runForm.value.agentId,
                            caseName: target.caseName || `${target.webCaseId}`,
                        });
                    }
                    const retainedSessionId =
                        `${response?.data?.result?.retainedSessionId || ""}`.trim();
                    reuseRetainedSessionId =
                        !runForm.value.closeBrowserOnFinish && retainedSessionId
                            ? retainedSessionId
                            : "";
                    successCount += 1;
                    runResponses.push({ target, response });
                } catch (error) {
                    reuseRetainedSessionId = "";
                    failedCount += 1;
                    runResponses.push({ target, error });
                    if (requireConfirmForCurrent) {
                        break;
                    }
                }
            }
            showRunDialog.value = false;
            activeTab.value = "run";
            await nextTick();
            if (runTargets.length === 1) {
                await runTabRef.value?.openHistoryByCase?.(runTargets[0].webCaseId);
            } else {
                await refreshRunTab();
            }
            if (runTargets.length === 1) {
                const first = runResponses[0];
                if (first?.response) {
                    ElMessage.success(first.response.msg || "执行完成");
                    if (first.response.data?.webCaseRunId) {
                        openRunDetail(first.response.data);
                    }
                } else {
                    const msg =
                        first?.error?.response?.data?.msg ||
                        first?.error?.message ||
                        "执行失败";
                    ElMessage.error(msg);
                }
                return;
            }
            if (failedCount === 0) {
                ElMessage.success(`批量执行完成：成功 ${successCount} 条`);
            } else if (successCount === 0) {
                ElMessage.error(`批量执行完成：失败 ${failedCount} 条`);
            } else {
                ElMessage.warning(
                    `批量执行完成：成功 ${successCount} 条，失败 ${failedCount} 条`,
                );
            }
        } catch (error) {
            const msg = error?.response?.data?.msg || error?.message || "执行失败";
            ElMessage.error(msg);
        } finally {
            loading.value.run = false;
        }
    }

    onBeforeUnmount(() => {
        stopRunDetailPoll();
    });

    return {
        selectedCase,
        runTargetCases,
        runDetail,
        showRunDialog,
        showRunDetailDialog,
        runDetailTab,
        runAdvancedPanels,
        runForm,
        webCredentialBindingOptions,
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
    };
}
