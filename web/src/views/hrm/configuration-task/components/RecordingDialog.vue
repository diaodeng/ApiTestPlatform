<template>
    <el-dialog
        v-model="visible"
        title="新建录制"
        width="720px"
        destroy-on-close
        :close-on-click-modal="false"
        @close="handleDialogClose"
    >
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
                            <el-option label="Chromium" value="chromium" />
                            <el-option label="Firefox" value="firefox" />
                            <el-option label="WebKit" value="webkit" />
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
            </el-row>
        </el-form>

        <el-alert
            v-if="!recordingForm.recordingId"
            title="录制在执行 Agent 的机器上拉起浏览器，操作过程会被记录为步骤；录制完成后回到任务列表用「录制转模板」生成版本草稿。"
            type="info"
            :closable="false"
            class="mb12"
        />
        <template v-else>
            <el-descriptions :column="2" border class="mb12">
                <el-descriptions-item label="当前录制ID">{{ recordingForm.recordingId }}</el-descriptions-item>
                <el-descriptions-item label="状态">
                    <el-tag :type="liveStatusType">{{ liveStatusText || "已启动" }}</el-tag>
                </el-descriptions-item>
            </el-descriptions>
            <el-alert
                title="录制过程中请保持本弹窗打开；完成后点「停止录制」，再去任务列表点「录制转模板」。"
                type="warning"
                :closable="false"
                class="mb12"
            />
        </template>

        <template #footer>
            <template v-if="!recordingForm.recordingId">
                <el-button @click="visible = false">取消</el-button>
                <el-button type="primary" :loading="submitting" @click="startRecording">开始录制</el-button>
            </template>
            <template v-else>
                <el-button @click="visible = false">关闭弹窗（后台继续录制）</el-button>
                <el-button type="danger" :loading="submitting" @click="stopRecording">停止录制</el-button>
            </template>
        </template>
    </el-dialog>
</template>

<script setup name="ConfigRecordingDialog">
import { computed } from "vue";
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

const {
    submitting,
    recordingForm,
    liveStatusText,
    liveStatusType,
    startRecording,
    stopRecording,
    handleDialogClose
} = useStandaloneRecording();

// 登录凭证选项：与 Web 用例录制共用统一凭证的 Web 投影绑定（playwright_storage 类型）。
const credentialOptions = computed(() => props.credentialOptions || []);
</script>
