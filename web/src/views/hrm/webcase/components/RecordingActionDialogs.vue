<template>
        <el-dialog
            v-model="showRecordingActionDialog"
            :title="recordingActionDialogTitle"
            width="80%"
            destroy-on-close
            append-to-body
            :close-on-click-modal="false"
            :close-on-press-escape="false"
        >
            <el-alert
                :title="recordingActionDialogTip"
                :type="recordingActionMode === 'replace' ? 'warning' : 'info'"
                :closable="false"
                show-icon
                class="mb16"
            />
            <el-form :model="recordingActionForm" label-width="110px">
                <template v-if="recordingActionMode === 'create'">
                    <el-row :gutter="16">
                        <el-col :span="12">
                            <el-form-item label="用例名称">
                                <el-input
                                    v-model="recordingActionForm.caseName"
                                    placeholder="请输入新用例名称"
                                />
                            </el-form-item>
                        </el-col>
                        <el-col :span="12">
                            <el-form-item label="浏览器">
                                <el-select
                                    v-model="recordingActionForm.browserName"
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
                        <el-col :span="12">
                            <el-form-item label="项目">
                                <el-select
                                    v-model="recordingActionForm.projectId"
                                    clearable
                                    filterable
                                    style="width: 100%"
                                >
                                    <el-option
                                        v-for="item in projectOptions"
                                        :key="item.projectId"
                                        :label="item.projectName"
                                        :value="item.projectId"
                                    />
                                </el-select>
                            </el-form-item>
                        </el-col>
                        <el-col :span="12">
                            <el-form-item label="模块">
                                <el-select
                                    v-model="recordingActionForm.moduleId"
                                    clearable
                                    filterable
                                    style="width: 100%"
                                >
                                    <el-option
                                        v-for="item in filteredRecordingActionModules"
                                        :key="item.moduleId"
                                        :label="item.moduleName"
                                        :value="item.moduleId"
                                    />
                                </el-select>
                            </el-form-item>
                        </el-col>
                        <el-col :span="24">
                            <el-form-item label="起始地址">
                                <el-input
                                    v-model="recordingActionForm.startUrl"
                                    placeholder="https://example.com"
                                />
                            </el-form-item>
                        </el-col>
                        <el-col :span="12">
                            <el-form-item label="无头模式">
                                <el-switch
                                    v-model="recordingActionForm.headless"
                                />
                            </el-form-item>
                        </el-col>
                        <el-col :span="24">
                            <el-form-item label="说明">
                                <el-input
                                    v-model="recordingActionForm.notes"
                                    type="textarea"
                                    :rows="3"
                                />
                            </el-form-item>
                        </el-col>
                    </el-row>
                </template>
                <template v-else>
                    <el-form-item label="目标用例">
                        <el-select
                            v-model="recordingActionForm.webCaseId"
                            clearable
                            filterable
                            remote
                            reserve-keyword
                            style="width: 100%"
                            placeholder="请输入目标用例名称"
                            :remote-method="searchCaseOptions"
                            :loading="caseSelectLoading"
                            @visible-change="handleCaseSelectVisibleChange"
                        >
                            <el-option
                                v-for="item in caseSelectOptions"
                                :key="item.webCaseId"
                                :label="`${item.caseName} [${item.webCaseId}]`"
                                :value="item.webCaseId"
                            />
                        </el-select>
                    </el-form-item>
                </template>
            </el-form>
            <template #footer>
                <el-button @click="showRecordingActionDialog = false">取消</el-button>
                <el-button
                    type="primary"
                    :loading="loading.recordingAction"
                    @click="submitRecordingAction"
                    >{{ recordingActionSubmitText }}</el-button
                >
            </template>
        </el-dialog>

        <el-dialog
            v-model="showReplayDialog"
            title="录制回放"
            width="80%"
            destroy-on-close
            append-to-body
            :close-on-click-modal="false"
            :close-on-press-escape="false"
        >
            <el-form :model="replayForm" label-width="120px">
                <el-form-item label="录制会话">
                    <el-input :model-value="selectedReplayLabel" readonly />
                </el-form-item>
                <el-form-item label="执行 Agent">
                    <el-select
                        v-model="replayForm.agentId"
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
                        v-model="replayForm.browserName"
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
                <el-form-item label="无头模式">
                    <el-switch v-model="replayForm.headless" />
                </el-form-item>
                <el-form-item label="结束后关闭浏览器">
                    <el-switch v-model="replayForm.closeBrowserOnFinish" />
                </el-form-item>
                <el-form-item label="多匹配直接按Nth">
                    <el-switch
                        v-model="replayForm.immediateLocatorIndexMode"
                        inline-prompt
                        active-text="开启"
                        inactive-text="学习"
                    />
                </el-form-item>
                <el-form-item label="状态来源">
                    <el-radio-group v-model="replayForm.stateSourceType">
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
                    v-if="replayForm.stateSourceType === 'session'"
                    label="浏览器Session"
                    v-hasPermi="['hrm:webCase:persistContext']"
                >
                    <el-row :gutter="10" style="width: 100%">
                        <el-col :span="18">
                            <el-select
                                v-model="replayForm.browserSessionId"
                                clearable
                                filterable
                                style="width: 100%"
                                placeholder="可选：选择浏览器Session"
                            >
                                <el-option
                                    v-for="item in availableBrowserSessionsForReplay"
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
                    v-if="replayForm.stateSourceType === 'cookie'"
                    label="Cookie配置"
                >
                    <el-row :gutter="10" style="width: 100%">
                        <el-col :span="18">
                            <el-select
                                v-model="replayForm.runtimeProfileId"
                                clearable
                                filterable
                                style="width: 100%"
                                placeholder="可选：选择Cookie配置"
                            >
                                <el-option
                                    v-for="item in availableRuntimeProfilesForReplay"
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
                <el-row v-if="replayForm.stateSourceType !== 'none'">
                    <el-col :span="12">
                        <el-form-item
                            label="保留浏览器状态"
                            v-hasPermi="['hrm:webCase:persistContext']"
                        >
                            <el-switch
                                v-model="replayForm.persistContextEnabled"
                            />
                        </el-form-item>
                    </el-col>
                    <el-col :span="12">
                        <el-form-item
                            label="自动同步状态"
                            v-hasPermi="['hrm:webCase:persistContext']"
                        >
                            <el-switch
                                v-model="
                                    replayForm.persistContextAutoSyncSession
                                "
                                :disabled="!replayForm.persistContextEnabled"
                            />
                        </el-form-item>
                    </el-col>
                </el-row>
            </el-form>
            <template #footer>
                <el-button @click="showReplayDialog = false">取消</el-button>
                <el-button
                    type="primary"
                    :loading="loading.replay"
                    @click="submitReplay"
                    >开始回放</el-button
                >
            </template>
        </el-dialog>

        <el-dialog
            v-model="showReplayResultDialog"
            :title="replayResultTitle"
            width="80%"
            destroy-on-close
            append-to-body
            :close-on-click-modal="false"
            :close-on-press-escape="false"
        >
            <template v-if="replayResult">
                <el-alert
                    :title="
                        replayFailureMessage ||
                        (replayResult.status === 'passed'
                            ? '回放执行成功'
                            : '回放执行失败')
                    "
                    :type="
                        replayResult.status === 'passed' ? 'success' : 'error'
                    "
                    :closable="false"
                    show-icon
                    class="mb16"
                />
                <el-table
                    :data="replayStepResults"
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
                                :type="getStepStatusTagType(scope.row.status)"
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
                <AceEditor
                    :content="replayResultJsonText"
                    lang="json"
                    :read-only="true"
                    height="260px"
                />
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
} = props.context;
</script>

<style scoped lang="scss">
@import "../styles/dialogs.scss";
</style>
