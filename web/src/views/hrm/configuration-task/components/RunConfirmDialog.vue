<template>
    <el-dialog v-model="visible" title="运行配置任务" width="520px">
        <el-form label-width="120px">
            <el-form-item label="任务">
                <span>{{ task?.taskName }}</span>
            </el-form-item>
            <el-form-item label="执行Agent">
                <el-select
                    v-model="form.agentCode"
                    :placeholder="task?.agentCode ? `默认任务 Agent：${task.agentCode}` : '默认任务 Agent'"
                    clearable
                    filterable
                    :loading="agentsLoading"
                    style="width: 100%"
                >
                    <el-option
                        v-for="item in agentOptions"
                        :key="item.agentCode"
                        :label="`${item.agentName || item.agentCode} [${item.agentCode}]`"
                        :value="item.agentCode"
                    />
                </el-select>
            </el-form-item>
            <el-form-item label="版本号">
                <el-input-number v-model="form.versionNo" :min="1" placeholder="默认当前发布版本" />
            </el-form-item>
            <el-form-item label="手动登录">
                <el-switch v-model="form.manualLoginEnabled" />
                <span class="hint">需要扫码/验证码时开启，先打开浏览器等待人工登录</span>
            </el-form-item>
            <el-form-item label="登录等待(秒)" v-if="form.manualLoginEnabled">
                <el-input-number v-model="form.manualLoginWaitSec" :min="1" :max="3600" />
            </el-form-item>
            <el-form-item label="步骤超时(ms)">
                <el-input-number
                    v-model="form.defaultStepTimeoutMs"
                    :min="500"
                    :max="600000"
                    :step="1000"
                    placeholder="默认 10000"
                />
                <span class="hint">单步最长执行时间，留空用步骤自身配置</span>
            </el-form-item>
            <el-form-item label="步骤等待(ms)">
                <el-input-number
                    v-model="form.defaultStepWaitMs"
                    :min="0"
                    :max="600000"
                    :step="500"
                    placeholder="默认 0"
                />
                <span class="hint">每步执行前/后的缓冲等待，留空用步骤自身配置</span>
            </el-form-item>
            <el-form-item label="应用方式">
                <el-radio-group v-model="form.stepParamApplyMode">
                    <el-radio value="default">作为默认值</el-radio>
                    <el-radio value="force">覆盖所有步骤</el-radio>
                </el-radio-group>
                <span class="hint">默认值仅对未单独设置的步骤生效；覆盖会忽略步骤自身配置</span>
            </el-form-item>
            <el-form-item label="失败策略">
                <el-radio-group v-model="form.failureStrategy">
                    <el-radio value="stop">失败后停止</el-radio>
                    <el-radio value="continue">继续执行后续阶段</el-radio>
                </el-radio-group>
                <span class="hint">继续模式下失败阶段照常标记失败，后续阶段依赖上游产出时请自行评估</span>
            </el-form-item>
            <el-form-item label="回写凭证">
                <el-switch v-model="form.writebackCredentialEnabled" />
                <span class="hint">执行结束后把浏览器最终登录态回写到版本绑定的凭证（需绑定允许回写）</span>
            </el-form-item>
            <el-form-item label="强制刷新登录态">
                <el-switch v-model="form.forceRefreshSeedState" />
                <span class="hint">忽略 Agent 本地缓存的浏览器状态，强制用本次凭证合并的登录态初始化（凭证更新后建议开启）</span>
            </el-form-item>
            <el-form-item label="超时(秒)">
                <el-input-number v-model="form.timeoutSeconds" :min="30" :max="21600" :step="60" />
            </el-form-item>
            <el-alert
                title="运行会同步等待执行完成（可能持续数分钟）；同一 Agent 同时只允许一个运行。"
                type="info"
                :closable="false"
            />
        </el-form>
        <template #footer>
            <el-button @click="visible = false">取消</el-button>
            <el-button type="primary" :loading="running" @click="startRun">开始运行</el-button>
        </template>
    </el-dialog>
</template>

<script setup name="ConfigRunConfirmDialog">
import { ref, reactive, computed, watch } from "vue";
import { ElMessage } from "element-plus";
import { createRun } from "@/api/hrm/configuration_task";
import { useAgentOptions } from "../composables/useAgentOptions";

const props = defineProps({ modelValue: Boolean, task: Object });
const emit = defineEmits(["update:modelValue", "started"]);

const { agentOptions, ensureAgentOptions, agentsLoading } = useAgentOptions();

watch(
    () => props.modelValue,
    (opened) => {
        if (opened) ensureAgentOptions().catch(() => {});
    },
    { immediate: true }
);

const visible = computed({
    get: () => props.modelValue,
    set: (value) => emit("update:modelValue", value)
});
const running = ref(false);
const form = reactive({
    agentCode: "",
    versionNo: undefined,
    manualLoginEnabled: false,
    manualLoginWaitSec: 120,
    timeoutSeconds: 1800,
    defaultStepTimeoutMs: undefined,
    defaultStepWaitMs: undefined,
    stepParamApplyMode: "default",
    failureStrategy: "stop",
    writebackCredentialEnabled: false,
    forceRefreshSeedState: false
});

async function startRun() {
    if (!props.task) return;
    running.value = true;
    try {
        const payload = {
            agentCode: form.agentCode || undefined,
            versionNo: form.versionNo || undefined,
            manualLoginEnabled: form.manualLoginEnabled,
            manualLoginWaitSec: form.manualLoginWaitSec,
            timeoutSeconds: form.timeoutSeconds,
            // 运行级步骤参数覆盖：留空表示完全沿用步骤自身配置。
            defaultStepTimeoutMs: form.defaultStepTimeoutMs || undefined,
            defaultStepWaitMs: form.defaultStepWaitMs || undefined,
            stepParamApplyMode: form.stepParamApplyMode,
            failureStrategy: form.failureStrategy,
            writebackCredentialEnabled: form.writebackCredentialEnabled,
            forceRefreshSeedState: form.forceRefreshSeedState,
            triggerType: "manual"
        };
        const res = await createRun(props.task.taskId, payload);
        ElMessage.success(`运行完成：${res.data?.status || "已提交"}`);
        emit("started", res.data);
    } catch (e) {
        ElMessage.error(e.message || "运行失败");
    } finally {
        running.value = false;
    }
}
</script>

<style lang="scss" scoped>
.hint {
    margin-left: 8px;
    color: var(--el-text-color-secondary);
    font-size: 12px;
}
</style>
