<template>
    <el-dialog v-model="visible" title="定时触发配置" width="520px">
        <el-form label-width="130px">
            <el-form-item label="任务">
                <span>{{ task?.taskName }}</span>
            </el-form-item>
            <el-form-item label="启用定时">
                <el-switch v-model="form.enabled" />
            </el-form-item>
            <template v-if="form.enabled">
                <el-form-item label="cron 表达式" required>
                    <el-input v-model="form.cron" placeholder="5 字段：分 时 日 月 周，如 0 9 * * 1-5" />
                    <div class="hint">每天 9 点：0 9 * * *；工作日 9 点：0 9 * * 1-5；每 30 分钟：*/30 * * * *</div>
                </el-form-item>
                <el-form-item label="执行版本号">
                    <el-input-number v-model="form.versionNo" :min="1" placeholder="默认当前发布版本" />
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
                <el-alert
                    :title="scheduleHint"
                    type="warning"
                    :closable="false"
                />
            </template>
        </el-form>
        <template #footer>
            <el-button @click="visible = false">取消</el-button>
            <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        </template>
    </el-dialog>
</template>

<script setup name="ConfigScheduleDialog">
import { ref, reactive, computed, watch } from "vue";
import { ElMessage } from "element-plus";
import { getTaskSchedule, saveTaskSchedule } from "@/api/hrm/configuration_task";
import { useAgentOptions } from "../composables/useAgentOptions";

const props = defineProps({ modelValue: Boolean, task: Object });
const emit = defineEmits(["update:modelValue", "saved"]);

const { agentOptions, ensureAgentOptions, agentsLoading } = useAgentOptions();

const visible = computed({
    get: () => props.modelValue,
    set: (value) => emit("update:modelValue", value)
});
const saving = ref(false);
const form = reactive({ enabled: false, cron: "", versionNo: undefined, agentCode: "" });
// 提示用户：这里的保存只是记录偏好，不会自动创建调度任务，必须去定时任务页手工创建。
const scheduleHint =
    '注意：保存本配置只是记录定时偏好，系统不会自动创建调度任务。还需到「系统监控 → 定时任务」手工创建一条定时任务：调用目标填 module_task.scheduler_configuration.trigger_configuration_task_run，参数填 {"task_id": 任务ID}，cron 与此处保持一致；两处都没配置时不会定时执行。';

watch(
    () => [props.modelValue, props.task?.taskId],
    async ([opened]) => {
        if (!opened || !props.task) return;
        ensureAgentOptions().catch(() => {});
        try {
            const res = await getTaskSchedule(props.task.taskId);
            const data = res.data || {};
            Object.assign(form, {
                enabled: !!data.enabled,
                cron: data.cron || "",
                versionNo: data.versionNo || undefined,
                agentCode: data.agentCode || ""
            });
        } catch {
            Object.assign(form, { enabled: false, cron: "", versionNo: undefined, agentCode: "" });
        }
    },
    { immediate: true }
);

async function save() {
    if (!props.task) return;
    if (form.enabled && !form.cron.trim()) {
        ElMessage.warning("启用定时必须填写 cron 表达式");
        return;
    }
    saving.value = true;
    try {
        await saveTaskSchedule(props.task.taskId, {
            enabled: form.enabled,
            cron: form.cron.trim(),
            versionNo: form.versionNo || undefined,
            agentCode: form.agentCode || undefined
        });
        ElMessage.success("定时配置已保存");
        emit("saved");
        visible.value = false;
    } catch (e) {
        ElMessage.error(e.message || "保存失败");
    } finally {
        saving.value = false;
    }
}
</script>

<style lang="scss" scoped>
.hint {
    color: var(--el-text-color-secondary);
    font-size: 12px;
    line-height: 1.6;
}
</style>
