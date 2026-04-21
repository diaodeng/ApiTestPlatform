<template>
        <el-dialog
            v-model="showRecordingDialog"
            :title="recordingDialogTitle"
            width="90%"
            destroy-on-close
            append-to-body
            :close-on-click-modal="false"
            :close-on-press-escape="false"
            @close="stopRecordingPoll"
        >
            <el-form :model="recordingForm" label-width="120px" class="mb12">
                <el-row :gutter="16">
                    <el-col :span="12">
                        <el-form-item label="关联用例">
                            <el-input
                                :model-value="recordingLinkedCaseLabel"
                                readonly
                            />
                        </el-form-item>
                    </el-col>
                    <el-col :span="12">
                        <el-form-item label="录制名称">
                            <el-input
                                v-model="recordingForm.sessionName"
                                placeholder="为空则自动生成录制名称"
                            />
                        </el-form-item>
                    </el-col>
                    <el-col :span="12">
                        <el-form-item label="执行 Agent">
                            <el-select
                                v-model="recordingForm.agentId"
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
                    </el-col>
                    <el-col :span="6">
                        <el-form-item label="浏览器">
                            <el-select
                                v-model="recordingForm.browserName"
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
                    </el-col>
                    <el-col :span="6">
                        <el-form-item label="无头模式">
                            <el-switch v-model="recordingForm.headless" />
                        </el-form-item>
                    </el-col>
                    <el-col :span="24">
                        <el-form-item label="起始地址">
                            <el-input
                                v-model="recordingForm.startUrl"
                                placeholder="https://example.com"
                            />
                        </el-form-item>
                    </el-col>
                    <el-col :span="12">
                        <el-form-item label="当前录制ID">
                            <el-input
                                :model-value="recordingForm.recordingId || '-'"
                                readonly
                            />
                        </el-form-item>
                    </el-col>

                    <el-col :span="24">
                        <el-collapse v-model="recordingAdvancedPanels">
                            <el-collapse-item title="高级设置" name="advanced">
                                <el-row :gutter="16">
                                    <el-col :span="24">
                                        <el-form-item label="状态来源">
                                            <el-radio-group
                                                v-model="
                                                    recordingForm.stateSourceType
                                                "
                                            >
                                                <el-radio-button value="none"
                                                    >不使用</el-radio-button
                                                >
                                                <el-radio-button
                                                    value="session"
                                                    v-hasPermi="[
                                                        'hrm:webCase:persistContext',
                                                    ]"
                                                    >浏览器Session</el-radio-button
                                                >
                                                <el-radio-button value="cookie"
                                                    >Cookie配置</el-radio-button
                                                >
                                            </el-radio-group>
                                        </el-form-item>
                                    </el-col>
                                    <el-col
                                        v-if="
                                            recordingForm.stateSourceType ===
                                            'session'
                                        "
                                        :span="24"
                                        v-hasPermi="[
                                            'hrm:webCase:persistContext',
                                        ]"
                                    >
                                        <el-form-item label="浏览器Session">
                                            <el-row
                                                :gutter="10"
                                                style="width: 100%"
                                            >
                                                <el-col :span="18">
                                                    <el-select
                                                        v-model="
                                                            recordingForm.browserSessionId
                                                        "
                                                        clearable
                                                        filterable
                                                        style="width: 100%"
                                                        placeholder="可选：选择浏览器Session"
                                                    >
                                                        <el-option
                                                            v-for="item in availableBrowserSessionsForRecording"
                                                            :key="
                                                                item.sessionId
                                                            "
                                                            :label="
                                                                formatBrowserSessionLabel(
                                                                    item,
                                                                )
                                                            "
                                                            :value="
                                                                item.sessionId
                                                            "
                                                        />
                                                    </el-select>
                                                </el-col>
                                                <el-col :span="6">
                                                    <el-button
                                                        style="width: 100%"
                                                        @click="
                                                            openBrowserSessionDialog
                                                        "
                                                        >管理Session</el-button
                                                    >
                                                </el-col>
                                            </el-row>
                                        </el-form-item>
                                    </el-col>
                                    <el-col
                                        v-if="
                                            recordingForm.stateSourceType ===
                                            'cookie'
                                        "
                                        :span="24"
                                    >
                                        <el-form-item label="Cookie配置">
                                            <el-row
                                                :gutter="10"
                                                style="width: 100%"
                                            >
                                                <el-col :span="18">
                                                    <el-select
                                                        v-model="
                                                            recordingForm.runtimeProfileId
                                                        "
                                                        clearable
                                                        filterable
                                                        style="width: 100%"
                                                        placeholder="可选：选择Cookie配置"
                                                    >
                                                        <el-option
                                                            v-for="item in availableRuntimeProfilesForRecording"
                                                            :key="
                                                                item.profileId
                                                            "
                                                            :label="
                                                                formatRuntimeProfileLabel(
                                                                    item,
                                                                )
                                                            "
                                                            :value="
                                                                item.profileId
                                                            "
                                                        />
                                                    </el-select>
                                                </el-col>
                                                <el-col :span="6">
                                                    <el-button
                                                        style="width: 100%"
                                                        @click="
                                                            openRuntimeProfileDialog
                                                        "
                                                        >管理Cookie</el-button
                                                    >
                                                </el-col>
                                            </el-row>
                                        </el-form-item>
                                    </el-col>

                                    <el-col
                                        :span="12"
                                        v-hasPermi="[
                                            'hrm:webCase:persistContext',
                                        ]"
                                        v-if="
                                            recordingForm.stateSourceType !==
                                            'none'
                                        "
                                    >
                                        <el-form-item label="保留浏览器状态">
                                            <el-switch
                                                v-model="
                                                    recordingForm.persistContextEnabled
                                                "
                                            />
                                        </el-form-item>
                                    </el-col>
                                    <el-col
                                        :span="12"
                                        v-hasPermi="[
                                            'hrm:webCase:persistContext',
                                        ]"
                                        v-if="
                                            recordingForm.stateSourceType !==
                                            'none'
                                        "
                                    >
                                        <el-form-item label="自动同步状态">
                                            <el-switch
                                                v-model="
                                                    recordingForm.persistContextAutoSyncSession
                                                "
                                                :disabled="
                                                    !recordingForm.persistContextEnabled
                                                "
                                            />
                                        </el-form-item>
                                    </el-col>
                                    <el-col :span="6">
                                        <el-form-item label="窗口最大化">
                                            <el-switch
                                                v-model="
                                                    recordingForm.windowMaximize
                                                "
                                            />
                                        </el-form-item>
                                    </el-col>
                                    <el-col :span="6">
                                        <el-form-item label="窗口宽度">
                                            <el-input-number
                                                v-model="
                                                    recordingForm.windowWidth
                                                "
                                                :min="1"
                                                :step="100"
                                                controls-position="right"
                                                style="width: 100%"
                                                :disabled="
                                                    recordingForm.windowMaximize
                                                "
                                                placeholder="例如 1600"
                                            />
                                        </el-form-item>
                                    </el-col>
                                    <el-col :span="6">
                                        <el-form-item label="窗口高度">
                                            <el-input-number
                                                v-model="
                                                    recordingForm.windowHeight
                                                "
                                                :min="1"
                                                :step="100"
                                                controls-position="right"
                                                style="width: 100%"
                                                :disabled="
                                                    recordingForm.windowMaximize
                                                "
                                                placeholder="例如 900"
                                            />
                                        </el-form-item>
                                    </el-col>
                                    <el-col :span="6">
                                        <el-form-item
                                            class="label-nowrap"
                                            label="停止时关闭浏览器"
                                        >
                                            <el-switch
                                                v-model="
                                                    recordingForm.closeBrowserOnStop
                                                "
                                            />
                                        </el-form-item>
                                    </el-col>
                                    <el-col :span="6">
                                        <el-form-item label="启用断言录制">
                                            <el-switch
                                                v-model="
                                                    recordingForm.captureAssertions
                                                "
                                            />
                                        </el-form-item>
                                    </el-col>
                                    <el-col :span="6">
                                        <el-form-item label="断言归属方式">
                                            <el-switch
                                                v-model="
                                                    recordingForm.attachAssertionsToPreviousStep
                                                "
                                                :disabled="
                                                    !recordingForm.captureAssertions
                                                "
                                                inline-prompt
                                                active-text="步骤内"
                                                inactive-text="平级"
                                            />
                                        </el-form-item>
                                    </el-col>
                                    <el-col :span="6">
                                        <el-form-item label="点击前自动断言">
                                            <el-switch
                                                v-model="
                                                    recordingForm.autoAssertTextOnClick
                                                "
                                                :disabled="
                                                    !recordingForm.captureAssertions
                                                "
                                            />
                                        </el-form-item>
                                    </el-col>
                                    <el-col :span="6">
                                        <el-form-item label="手动登录闸门">
                                            <el-switch
                                                v-model="
                                                    recordingForm.manualLoginEnabled
                                                "
                                            />
                                        </el-form-item>
                                    </el-col>
                                    <el-col :span="6">
                                        <el-form-item label="登录后确认继续">
                                            <el-switch
                                                v-model="
                                                    recordingForm.manualLoginRequireConfirm
                                                "
                                                :disabled="
                                                    !recordingForm.manualLoginEnabled
                                                "
                                                inline-prompt
                                                active-text="开启"
                                                inactive-text="关闭"
                                            />
                                        </el-form-item>
                                    </el-col>
                                    <el-col :span="6">
                                        <el-form-item label="登录等待(秒)">
                                            <el-input-number
                                                v-model="
                                                    recordingForm.manualLoginWaitSec
                                                "
                                                :min="0"
                                                :max="3600"
                                                :step="10"
                                                controls-position="right"
                                                style="width: 100%"
                                                :disabled="
                                                    !recordingForm.manualLoginEnabled ||
                                                    recordingForm.manualLoginRequireConfirm
                                                "
                                            />
                                        </el-form-item>
                                    </el-col>
                                </el-row>
                            </el-collapse-item>
                        </el-collapse>
                    </el-col>
                </el-row>
            </el-form>

            <div class="recording-toolbar">
                <el-button
                    type="primary"
                    :loading="loading.recording"
                    @click="startRecording"
                    >开始录制</el-button
                >
                <el-button
                    type="warning"
                    :disabled="!recordingForm.recordingId"
                    @click="stopRecording"
                    >停止录制</el-button
                >
                <el-button
                    :disabled="!recordingForm.recordingId"
                    @click="refreshRecording"
                    >刷新详情</el-button
                >
                <el-button
                    type="success"
                    :disabled="!recordingForm.recordingId"
                    @click="openRecordingDetail(recordingForm.recordingId)"
                    >查看录制详情</el-button
                >
                <el-button
                    type="success"
                    plain
                    :disabled="!recordingResultReady"
                    @click="
                        openRecordingActionDialog(
                            'create',
                            recordingForm.recordingId,
                        )
                    "
                    >保存为新用例</el-button
                >
                <el-button
                    type="info"
                    plain
                    :disabled="!recordingResultReady"
                    @click="
                        openRecordingActionDialog(
                            'append',
                            recordingForm.recordingId,
                        )
                    "
                    >追加到用例</el-button
                >
                <el-button
                    type="danger"
                    plain
                    :disabled="!recordingResultReady"
                    @click="
                        openRecordingActionDialog(
                            'replace',
                            recordingForm.recordingId,
                        )
                    "
                    >覆盖到用例</el-button
                >
            </div>
            <el-alert
                :title="recordingAssertionTipText"
                type="info"
                :closable="false"
                show-icon
                class="mb12"
            />

            <el-alert
                :title="recordingLiveStatusText"
                :type="recordingLiveStatusType"
                :closable="false"
                show-icon
                class="mb16"
            />

            <el-tabs v-model="recordingLiveTab">
                <el-tab-pane label="步骤列表" name="steps">
                    <el-table
                        :data="liveRecordingSteps"
                        border
                        max-height="300px"
                        class="mb16"
                    >
                        <el-table-column
                            label="序号"
                            prop="stepIndex"
                            width="80"
                        />
                        <el-table-column label="动作" width="120">
                            <template #default="scope">{{
                                getActionLabel(scope.row.actionType)
                            }}</template>
                        </el-table-column>
                        <el-table-column
                            label="步骤名称"
                            prop="stepName"
                            min-width="220"
                        />
                        <el-table-column label="定位信息" min-width="260">
                            <template #default="scope">{{
                                describeStepTarget(scope.row)
                            }}</template>
                        </el-table-column>
                        <el-table-column
                            label="输入/参数"
                            min-width="220"
                            show-overflow-tooltip
                        >
                            <template #default="scope">{{
                                summarizeStepParams(scope.row)
                            }}</template>
                        </el-table-column>
                    </el-table>
                </el-tab-pane>
                <el-tab-pane label="步骤JSON" name="json">
                    <AceEditor
                        :content="recordingDetailText"
                        lang="json"
                        :read-only="true"
                        height="300px"
                    />
                </el-tab-pane>
            </el-tabs>
        </el-dialog>

        <el-dialog
            v-model="showRecordingDetailDialog"
            :title="recordingDetailTitle"
            width="90%"
            destroy-on-close
            append-to-body
            :close-on-click-modal="false"
            :close-on-press-escape="false"
            @close="stopRecordingDetailPoll"
        >
            <template v-if="recordingDetail">
                <el-descriptions :column="4" border class="mb16">
                    <el-descriptions-item label="录制ID">{{
                        recordingDetail.recordingId
                    }}</el-descriptions-item>
                    <el-descriptions-item label="录制名称">{{
                        recordingDetail.sessionName || "-"
                    }}</el-descriptions-item>
                    <el-descriptions-item label="所属用例">{{
                        getCaseName(recordingDetail.webCaseId) ||
                        recordingDetail.webCaseId ||
                        "独立录制"
                    }}</el-descriptions-item>
                    <el-descriptions-item label="状态">
                        <el-tag
                            :type="
                                getRecordingStatusMeta(recordingDetail.status)
                                    .type
                            "
                            >{{
                                getRecordingStatusMeta(recordingDetail.status)
                                    .label
                            }}</el-tag
                        >
                    </el-descriptions-item>
                    <el-descriptions-item label="Agent">{{
                        recordingDetail.agentCode || "-"
                    }}</el-descriptions-item>
                    <el-descriptions-item label="浏览器">{{
                        recordingDetail.browserName || "-"
                    }}</el-descriptions-item>
                    <el-descriptions-item label="开始时间">{{
                        formatTime(recordingDetail.startedAt)
                    }}</el-descriptions-item>
                    <el-descriptions-item label="结束时间">{{
                        formatTime(recordingDetail.endedAt)
                    }}</el-descriptions-item>
                </el-descriptions>

                <el-alert
                    v-if="recordingDetail.errorMessage"
                    :title="recordingDetail.errorMessage"
                    type="error"
                    :closable="false"
                    show-icon
                    class="mb16"
                />

                <div class="recording-toolbar mb16">
                    <el-button @click="refreshRecordingDetail"
                        >刷新详情</el-button
                    >
                    <el-button
                        v-if="canStopRecording(recordingDetail)"
                        type="warning"
                        icon="VideoPause"
                        @click="handleStopRecording(recordingDetail)"
                        v-hasPermi="['hrm:webCase:record']"
                    >
                        停止录制
                    </el-button>
                    <el-button
                        v-if="canCancelPreparedRecording(recordingDetail)"
                        type="warning"
                        plain
                        icon="CircleClose"
                        @click="handleCancelPreparedRecording(recordingDetail)"
                        v-hasPermi="['hrm:webCase:record']"
                    >
                        取消准备
                    </el-button>
                    <el-button
                        type="danger"
                        plain
                        icon="Delete"
                        @click="handleDeleteRecordingRecords(recordingDetail)"
                        v-hasPermi="['hrm:webCase:remove']"
                        >删除记录</el-button
                    >
                    <el-button
                        type="success"
                        icon="VideoPlay"
                        :disabled="
                            !canUseRecordingResult(recordingDetail.status)
                        "
                        @click="openReplayDialog(recordingDetail)"
                        v-hasPermi="['hrm:webCase:run']"
                        >回放录制</el-button
                    >
                    <el-button
                        type="success"
                        plain
                        icon="Plus"
                        :disabled="
                            !canUseRecordingResult(recordingDetail.status)
                        "
                        @click="
                            openRecordingActionDialog('create', recordingDetail)
                        "
                        v-hasPermi="['hrm:webCase:add']"
                        >保存为新用例</el-button
                    >
                    <el-button
                        type="info"
                        plain
                        icon="DocumentAdd"
                        :disabled="
                            !canUseRecordingResult(recordingDetail.status)
                        "
                        @click="
                            openRecordingActionDialog('append', recordingDetail)
                        "
                        v-hasPermi="['hrm:webCase:edit']"
                        >追加到用例</el-button
                    >
                    <el-button
                        type="danger"
                        plain
                        icon="EditPen"
                        :disabled="
                            !canUseRecordingResult(recordingDetail.status)
                        "
                        @click="
                            openRecordingActionDialog(
                                'replace',
                                recordingDetail,
                            )
                        "
                        v-hasPermi="['hrm:webCase:edit']"
                        >覆盖到用例</el-button
                    >
                </div>

                <el-tabs v-model="recordingDetailTab">
                    <el-tab-pane label="步骤预览" name="steps">
                        <el-table
                            :data="recordingPreviewSteps"
                            border
                            max-height="380px"
                        >
                            <el-table-column
                                label="序号"
                                prop="stepIndex"
                                width="80"
                            />
                            <el-table-column label="动作" width="120">
                                <template #default="scope">{{
                                    getActionLabel(scope.row.actionType)
                                }}</template>
                            </el-table-column>
                            <el-table-column
                                label="步骤名称"
                                prop="stepName"
                                min-width="220"
                            />
                            <el-table-column label="定位信息" min-width="280">
                                <template #default="scope">{{
                                    describeStepTarget(scope.row)
                                }}</template>
                            </el-table-column>
                            <el-table-column
                                label="输入/参数"
                                min-width="220"
                                show-overflow-tooltip
                            >
                                <template #default="scope">{{
                                    summarizeStepParams(scope.row)
                                }}</template>
                            </el-table-column>
                        </el-table>
                    </el-tab-pane>
                    <el-tab-pane label="原始事件" name="events">
                        <el-table
                            :data="recordingEventRows"
                            border
                            max-height="380px"
                        >
                            <el-table-column
                                label="序号"
                                prop="eventIndex"
                                width="80"
                            />
                            <el-table-column
                                label="事件类型"
                                prop="eventType"
                                width="140"
                            />
                            <el-table-column label="动作" min-width="160">
                                <template #default="scope">{{
                                    scope.row.payload?.actionType || "-"
                                }}</template>
                            </el-table-column>
                            <el-table-column label="步骤名称" min-width="220">
                                <template #default="scope">{{
                                    scope.row.payload?.stepName || "-"
                                }}</template>
                            </el-table-column>
                            <el-table-column label="元素文本" min-width="220">
                                <template #default="scope">{{
                                    scope.row.payload?.targetSnapshot
                                        ?.elementText || "-"
                                }}</template>
                            </el-table-column>
                        </el-table>
                    </el-tab-pane>
                    <el-tab-pane label="原始 JSON" name="json">
                        <AceEditor
                            :content="recordingDetailJsonText"
                            lang="json"
                            :read-only="true"
                            height="400px"
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
} = props.context;
</script>

<style scoped lang="scss">
@import "../styles/dialogs.scss";
</style>
