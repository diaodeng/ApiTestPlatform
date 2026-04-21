<template>
        <el-dialog
            v-model="showRunDialog"
            title="执行 Web 用例"
            width="80%"
            destroy-on-close
            append-to-body
            :close-on-click-modal="false"
            :close-on-press-escape="false"
        >
            <el-form :model="runForm" label-width="120px">
                <el-form-item label="目标用例">
                    <el-input
                        :model-value="runTargetLabel"
                        type="textarea"
                        :rows="2"
                        readonly
                    />
                </el-form-item>
                <el-form-item label="执行 Agent">
                    <el-select
                        v-model="runForm.agentId"
                        filterable
                        style="width: 100%"
                    >
                        <el-option
                            v-for="item in agentOptions"
                            :key="item.agentId"
                            :label="`${item.agentName || item.agentCode} [${item.agentCode}]`"
                            :value="item.agentId"
                        />
                    </el-select>
                </el-form-item>
                <el-form-item label="浏览器">
                    <el-select
                        v-model="runForm.browserName"
                        style="width: 100%"
                    >
                        <el-option
                            v-for="item in browserOptions"
                            :key="item.value"
                            :label="item.label"
                            :value="item.value"
                        />
                    </el-select>
                </el-form-item>
                <el-row>
                    <el-col :span="12">
                        <el-form-item label="无头模式">
                            <el-switch v-model="runForm.headless" />
                        </el-form-item>
                    </el-col>
                    <el-col :span="12">
                        <el-form-item
                            class="label-nowrap"
                            label="每条后重启浏览器"
                        >
                            <el-switch v-model="runForm.closeBrowserOnFinish" />
                        </el-form-item>
                    </el-col>
                </el-row>

                <el-form-item label="状态来源">
                    <el-radio-group v-model="runForm.stateSourceType">
                        <el-radio-button value="none">不使用</el-radio-button>
                        <el-radio-button
                            value="session"
                            v-hasPermi="['hrm:webCase:persistContext']"
                            >浏览器Session</el-radio-button
                        >
                        <el-radio-button value="cookie"
                            >Cookie配置</el-radio-button
                        >
                    </el-radio-group>
                </el-form-item>
                <el-form-item
                    v-if="runForm.stateSourceType === 'session'"
                    label="浏览器Session"
                    v-hasPermi="['hrm:webCase:persistContext']"
                >
                    <el-row :gutter="10" style="width: 100%">
                        <el-col :span="18">
                            <el-select
                                v-model="runForm.browserSessionId"
                                clearable
                                filterable
                                style="width: 100%"
                                placeholder="可选：选择浏览器Session"
                            >
                                <el-option
                                    v-for="item in availableBrowserSessionsForRun"
                                    :key="item.sessionId"
                                    :label="formatBrowserSessionLabel(item)"
                                    :value="item.sessionId"
                                />
                            </el-select>
                        </el-col>
                        <el-col :span="6">
                            <el-button
                                style="width: 100%"
                                @click="openBrowserSessionDialog"
                                >管理Session</el-button
                            >
                        </el-col>
                    </el-row>
                </el-form-item>
                <el-form-item
                    v-if="runForm.stateSourceType === 'cookie'"
                    label="Cookie配置"
                >
                    <el-row :gutter="10" style="width: 100%">
                        <el-col :span="18">
                            <el-select
                                v-model="runForm.runtimeProfileId"
                                clearable
                                filterable
                                style="width: 100%"
                                placeholder="可选：选择Cookie配置"
                            >
                                <el-option
                                    v-for="item in availableRuntimeProfilesForRun"
                                    :key="item.profileId"
                                    :label="formatRuntimeProfileLabel(item)"
                                    :value="item.profileId"
                                />
                            </el-select>
                        </el-col>
                        <el-col :span="6">
                            <el-button
                                style="width: 100%"
                                @click="openRuntimeProfileDialog"
                                >管理Cookie</el-button
                            >
                        </el-col>
                    </el-row>
                </el-form-item>
                <el-row v-if="runForm.stateSourceType !== 'none'">
                    <el-col :span="12">
                        <el-form-item
                            label="保留浏览器状态"
                            v-hasPermi="['hrm:webCase:persistContext']"
                        >
                            <el-switch
                                v-model="runForm.persistContextEnabled"
                            />
                        </el-form-item>
                    </el-col>
                    <el-col :span="12">
                        <el-form-item
                            label="自动同步状态"
                            v-hasPermi="['hrm:webCase:persistContext']"
                        >
                            <el-switch
                                v-model="runForm.persistContextAutoSyncSession"
                                :disabled="!runForm.persistContextEnabled"
                            />
                        </el-form-item>
                    </el-col>
                </el-row>
                <el-collapse v-model="runAdvancedPanels" class="mb12">
                    <el-collapse-item title="高级设置" name="advanced">
                        <el-row :gutter="12">
                            <el-col :span="12">
                                <el-form-item label="手动登录闸门">
                                    <el-switch
                                        v-model="runForm.manualLoginEnabled"
                                    />
                                </el-form-item>
                            </el-col>
                            <el-col :span="12">
                                <el-form-item label="登录等待(秒)">
                                    <el-input-number
                                        v-model="runForm.manualLoginWaitSec"
                                        :min="0"
                                        :max="3600"
                                        :step="10"
                                        controls-position="right"
                                        style="width: 100%"
                                        :disabled="
                                            !runForm.manualLoginEnabled ||
                                            runForm.manualLoginRequireConfirm
                                        "
                                    />
                                </el-form-item>
                            </el-col>
                        </el-row>
                        <el-form-item label="登录后确认继续">
                            <el-switch
                                v-model="runForm.manualLoginRequireConfirm"
                                :disabled="!runForm.manualLoginEnabled"
                                inline-prompt
                                active-text="开启"
                                inactive-text="关闭"
                            />
                        </el-form-item>
                        <el-form-item label="多匹配直接按Nth">
                            <el-switch
                                v-model="runForm.immediateLocatorIndexMode"
                                inline-prompt
                                active-text="开启"
                                inactive-text="学习"
                            />
                        </el-form-item>
                        <el-form-item>
                            <span class="step-detail-tip">
                                开启“登录后确认继续”后，会先启动浏览器等待你手动登录，确认后才继续；批量执行仅首条触发确认。关闭“每条后重启浏览器”可在批量执行中复用同一浏览器会话。
                            </span>
                        </el-form-item>
                    </el-collapse-item>
                </el-collapse>
                <el-row :gutter="12">
                    <el-col :span="12">
                        <el-form-item
                            class="label-nowrap"
                            label="单步超时覆盖(ms)"
                        >
                            <el-input-number
                                v-model="runForm.stepTimeoutMs"
                                :min="500"
                                :step="500"
                                controls-position="right"
                                style="width: 100%"
                            />
                        </el-form-item>
                    </el-col>
                    <el-col :span="12">
                        <el-form-item
                            class="label-nowrap"
                            label="步骤思考时间(ms)"
                        >
                            <el-input-number
                                v-model="runForm.stepThinkTimeMs"
                                :min="0"
                                :step="100"
                                controls-position="right"
                                style="width: 100%"
                            />
                        </el-form-item>
                    </el-col>
                </el-row>
            </el-form>
            <template #footer>
                <el-button @click="showRunDialog = false">取消</el-button>
                <el-button
                    type="primary"
                    :loading="loading.run"
                    @click="submitRun"
                    >执行</el-button
                >
            </template>
        </el-dialog>

        <el-dialog
            v-model="showRunDetailDialog"
            :title="runDetailTitle"
            width="90%"
            destroy-on-close
            append-to-body
            :close-on-click-modal="false"
            :close-on-press-escape="false"
            @close="stopRunDetailPoll"
        >
            <template v-if="runDetail">
                <el-descriptions :column="4" border class="mb16">
                    <el-descriptions-item label="执行记录ID">{{
                        runDetail.webCaseRunId
                    }}</el-descriptions-item>
                    <el-descriptions-item label="所属用例">{{
                        runDetail.caseName ||
                        getCaseName(runDetail.webCaseId) ||
                        runDetail.webCaseId
                    }}</el-descriptions-item>
                    <el-descriptions-item label="Agent">{{
                        runDetail.agentCode || "-"
                    }}</el-descriptions-item>
                    <el-descriptions-item label="状态">
                        <el-tag
                            :type="getRunStatusMeta(runDetail.status).type"
                            >{{
                                getRunStatusMeta(runDetail.status).label
                            }}</el-tag
                        >
                    </el-descriptions-item>
                    <el-descriptions-item label="开始时间">{{
                        formatTime(runDetail.startedAt)
                    }}</el-descriptions-item>
                    <el-descriptions-item label="结束时间">{{
                        formatTime(runDetail.endedAt)
                    }}</el-descriptions-item>
                    <el-descriptions-item label="耗时">{{
                        formatDuration(runDetail.durationMs)
                    }}</el-descriptions-item>
                    <el-descriptions-item label="触发方式">{{
                        runDetail.triggerType || "-"
                    }}</el-descriptions-item>
                </el-descriptions>

                <el-alert
                    v-if="runDetailFailureMessage"
                    :title="runDetailFailureMessage"
                    type="error"
                    show-icon
                    :closable="false"
                    class="mb16"
                />
                <el-alert
                    v-if="runCookieApplySummary"
                    :title="runCookieApplySummary"
                    :type="runCookieApplySummaryType"
                    show-icon
                    :closable="false"
                    class="mb16"
                />

                <div class="recording-toolbar">
                    <el-button @click="refreshRunDetail">刷新详情</el-button>
                    <el-button
                        v-if="canStopRun(runDetail)"
                        type="warning"
                        @click="handleStopRun(runDetail)"
                        v-hasPermi="['hrm:webCase:run']"
                    >
                        停止执行
                    </el-button>
                    <el-button
                        v-if="canCancelPreparedRun(runDetail)"
                        type="warning"
                        plain
                        @click="handleCancelPreparedRun(runDetail)"
                        v-hasPermi="['hrm:webCase:run']"
                    >
                        取消准备
                    </el-button>
                    <el-button
                        type="danger"
                        plain
                        @click="handleDeleteRunRecords(runDetail)"
                        v-hasPermi="['hrm:webCase:remove']"
                        >删除记录</el-button
                    >
                </div>

                <el-tabs v-model="runDetailTab">
                    <el-tab-pane label="步骤列表" name="steps">
                        <el-table
                            :data="runStepResults"
                            border
                            max-height="320px"
                            class="mb16"
                        >
                            <el-table-column
                                label="步骤"
                                prop="stepName"
                                min-width="220"
                            />
                            <el-table-column label="状态" width="110">
                                <template #default="scope">
                                    <el-tag
                                        :type="
                                            getStepStatusTagType(
                                                scope.row.status,
                                            )
                                        "
                                        >{{ scope.row.status || "-" }}</el-tag
                                    >
                                </template>
                            </el-table-column>
                            <el-table-column label="耗时" width="110">
                                <template #default="scope">{{
                                    formatDuration(scope.row.durationMs)
                                }}</template>
                            </el-table-column>
                            <el-table-column
                                label="页面"
                                prop="pageUrl"
                                min-width="220"
                                show-overflow-tooltip
                            />
                            <el-table-column
                                label="失败原因"
                                min-width="260"
                                show-overflow-tooltip
                            >
                                <template #default="scope">{{
                                    getStepFailureReason(scope.row)
                                }}</template>
                            </el-table-column>
                        </el-table>
                    </el-tab-pane>
                    <el-tab-pane label="步骤JSON" name="stepsJson">
                        <AceEditor
                            :content="runStepsJsonText"
                            lang="json"
                            :read-only="true"
                            height="320px"
                        />
                    </el-tab-pane>
                </el-tabs>
            </template>
        </el-dialog>
</template>

<script setup>
import AceEditor from "@/components/hrm/common/ace-editor.vue";

const props = defineProps({
    context: {
        type: Object,
        required: true,
    },
});

const {
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
} = props.context;
</script>

<style scoped lang="scss">
@import "../styles/dialogs.scss";
</style>
