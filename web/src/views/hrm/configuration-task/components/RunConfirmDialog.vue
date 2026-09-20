<template>
    <el-dialog v-model="visible" title="运行配置任务" width="520px">
        <el-form label-width="120px">
            <el-form-item label="任务">
                <span>{{ task?.taskName }}</span>
            </el-form-item>
            <el-form-item label="执行Agent">
                <el-input v-model="form.agentCode" :placeholder="task?.agentCode || '默认任务 Agent'" />
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
import { ref, reactive, computed } from "vue";
import { ElMessage } from "element-plus";
import { createRun } from "@/api/hrm/configuration_task";

const props = defineProps({ modelValue: Boolean, task: Object });
const emit = defineEmits(["update:modelValue", "started"]);

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
    timeoutSeconds: 1800
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
