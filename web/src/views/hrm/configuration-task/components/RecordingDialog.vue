<template>
    <el-dialog
        v-model="visible"
        title="新建录制"
        width="720px"
        destroy-on-close
        :close-on-click-modal="false"
        @close="handleDialogClose"
    >
        <!-- 失败提示条：独立于表单展示完整错误信息，不会被列宽截断 -->
        <el-alert
            v-if="startFailed"
            :title="`录制失败：${startFailedReason}`"
            type="error"
            :closable="false"
            class="mb12"
            show-icon
        />

        <el-form :model="recordingForm" label-width="120px">
            <el-row :gutter="16">
                <el-col :span="12">
                    <el-form-item label="录制名称">
                        <el-input
                            v-model="recordingForm.sessionName"
                            placeholder="为空则自动生成录制名称"
                            maxlength="128"
                        />
                    </el-form-item>
                </el-col>
                <el-col :span="12">
                    <el-form-item label="执行Agent" required>
                        <el-select
                            v-model="recordingForm.agentId"
                            placeholder="请选择执行 Agent"
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
                <el-col :span="12">
                    <el-form-item label="浏览器">
                        <el-select v-model="recordingForm.browserName" style="width: 100%">
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
                    <el-form-item label="无头模式">
                        <el-switch v-model="recordingForm.headless" />
                    </el-form-item>
                </el-col>
                <el-col :span="24">
                    <el-form-item label="起始地址" required>
                        <el-input v-model="recordingForm.startUrl" placeholder="https://example.com" />
                    </el-form-item>
                </el-col>
                <el-col :span="24">
                    <el-form-item label="登录凭证">
                        <el-select
                            v-model="recordingForm.credentialBindingId"
                            placeholder="需要登录态时选择 Web 凭证绑定，可留空"
                            clearable
                            filterable
                            style="width: 100%"
                        >
                            <el-option
                                v-for="item in credentialOptions"
                                :key="item.bindingId"
                                :label="item.bindingName || item.bindingId"
                                :value="item.bindingId"
                            />
                        </el-select>
                    </el-form-item>
                </el-col>
                <el-col :span="12">
                    <el-form-item label="手动登录">
                        <el-switch v-model="recordingForm.manualLoginEnabled" />
                        <span class="hint">需要扫码/验证码时开启</span>
                    </el-form-item>
                </el-col>
                <el-col :span="12" v-if="recordingForm.manualLoginEnabled">
                    <el-form-item label="登录等待(秒)">
                        <el-input-number v-model="recordingForm.manualLoginWaitSec" :min="1" :max="3600" />
                    </el-form-item>
                </el-col>
                <el-col :span="12">
                    <el-form-item :label="saveSwitchLabel">
                        <el-switch
                            v-model="recordingForm.saveCredentialAfterRecording"
                            :disabled="saveSwitchDisabled"
                        />
                        <span class="hint">{{ saveSwitchHint }}</span>
                    </el-form-item>
                </el-col>
                <el-col
                    :span="12"
                    v-if="recordingForm.saveCredentialAfterRecording && !isWritebackMode"
                >
                    <el-form-item label="新凭证名称">
                        <el-input
                            v-model="recordingForm.credentialName"
                            placeholder="为空则自动生成：录制凭证-{录制ID}"
                            maxlength="128"
                        />
                    </el-form-item>
                </el-col>
            </el-row>
        </el-form>

        <!-- 录制中/已结束的运行态视图；失败时不展示（回到表单态允许重新开始） -->
        <template v-if="recordingForm.recordingId && !startFailed">
            <el-alert
                v-if="liveStatusText"
                :title="liveStatusText"
                :type="liveStatusType"
                :closable="false"
                class="mb12"
                show-icon
            />
            <el-descriptions :column="1" border class="mb12">
                <el-descriptions-item label="当前录制ID">
                    <span class="recording-id">{{ recordingForm.recordingId }}</span>
                </el-descriptions-item>
            </el-descriptions>
            <el-alert
                title="录制过程中请保持本弹窗打开；完成后点「停止录制」，再去任务列表点「录制转模板」。"
                type="warning"
                :closable="false"
                class="mb12"
            />
            <el-alert
                title="录制技巧：按住 Alt 键点击目标元素可增加断言；有文本时生成“文本包含”断言，没有文本时生成“元素可见”断言。Alt+点击不会触发实际点击，当前默认把断言追加到上一条步骤；普通点击不会自动生成断言。"
                type="info"
                :closable="false"
                class="mb12"
                show-icon
            />
        </template>
        <el-alert
            v-if="!recordingForm.recordingId || startFailed"
            title="录制在执行 Agent 的机器上拉起浏览器，操作过程会被记录为步骤；录制完成后回到任务列表用「录制转模板」生成版本草稿。"
            type="info"
            :closable="false"
            class="mb12"
        />

        <template #footer>
            <template v-if="recordingForm.recordingId && !startFailed">
                <el-button @click="visible = false">关闭弹窗（后台继续录制）</el-button>
                <el-button type="danger" :loading="submitting" @click="stopRecording">停止录制</el-button>
            </template>
            <template v-else>
                <el-button @click="visible = false">{{ startFailed ? "关闭" : "取消" }}</el-button>
                <el-button type="primary" :loading="submitting" @click="startRecording">
                    {{ startFailed ? "重新开始录制" : "开始录制" }}
                </el-button>
            </template>
        </template>
    </el-dialog>
</template>

<script setup name="ConfigRecordingDialog">
import { computed, watch } from "vue";
import { browserOptions } from "@/components/hrm/case/webcase/utils/shared.js";
import {
    useStandaloneRecording
} from "../composables/useStandaloneRecording.js";

const props = defineProps({
    modelValue: Boolean,
    agentOptions: { type: Array, default: () => [] },
    credentialOptions: { type: Array, default: () => [] }
});
const emit = defineEmits(["update:modelValue"]);

const visible = computed({
    get: () => props.modelValue,
    set: (value) => emit("update:modelValue", value)
});

// 登录凭证选项：与 Web 用例录制共用统一凭证的 Web 投影绑定（playwright_storage 类型）。
// 注意：必须先于 useStandaloneRecording 声明——组合函数的停止逻辑要按选中绑定分派保存/回写。
const credentialOptions = computed(() => props.credentialOptions || []);

const {
    submitting,
    recordingForm,
    liveStatusText,
    liveStatusType,
    startFailed,
    startFailedReason,
    resetRecordingState,
    startRecording,
    stopRecording,
    handleDialogClose
} = useStandaloneRecording({ credentialBindingOptions: credentialOptions });

// 开关语义随凭证选择切换：
// - 未选凭证 → 保存为新凭证；
// - 已选凭证 → 回写到该凭证（仅当绑定开启"允许回写"时可用）。
const selectedBinding = computed(() =>
    credentialOptions.value.find(
        (item) => String(item.bindingId) === String(recordingForm.value.credentialBindingId || "")
    )
);
const isWritebackMode = computed(() => Boolean(selectedBinding.value));
const writebackAllowed = computed(() => Boolean(selectedBinding.value?.writebackEnabled));
const saveSwitchLabel = computed(() =>
    isWritebackMode.value ? "停止后回写所选凭证" : "停止后保存为新凭证"
);
const saveSwitchDisabled = computed(() => isWritebackMode.value && !writebackAllowed.value);
const saveSwitchHint = computed(() => {
    if (!isWritebackMode.value) return "把本次登录后的浏览器状态保存为新凭证";
    if (writebackAllowed.value) return `登录态将覆盖写回「${selectedBinding.value.bindingName}」`;
    return "该绑定未开启「允许回写」，请到统一凭证管理开启，或清除凭证选择改为保存新凭证";
});

// 每次打开弹窗都复位到全新状态：el-dialog 关闭不会销毁组合函数里的表单状态，
// 不复位会残留上一次的录制数据（表单值、录制 ID、失败提示等）。
watch(visible, (opened) => {
    if (opened) resetRecordingState();
});
</script>

<style lang="scss" scoped>
.hint {
    margin-left: 8px;
    color: var(--el-text-color-secondary);
    font-size: 12px;
}

.mb12 {
    margin-bottom: 12px;
}

.recording-id {
    word-break: break-all;
}
</style>
