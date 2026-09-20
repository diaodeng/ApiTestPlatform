<template>
    <el-dialog v-model="visible" title="录制转模板" width="560px">
        <el-form label-width="130px">
            <el-form-item label="目标任务">
                <span>{{ task?.taskName }}</span>
            </el-form-item>
            <el-form-item label="录制记录" required>
                <el-select
                    v-model="form.recordingId"
                    placeholder="输入名称搜索或下拉选择录制记录"
                    filterable
                    remote
                    :remote-method="searchRecordings"
                    :loading="recordingsLoading"
                    style="width: 100%"
                >
                    <el-option
                        v-for="item in recordingOptions"
                        :key="item.recordingId"
                        :label="recordingLabel(item)"
                        :value="String(item.recordingId)"
                    >
                        <span>{{ recordingLabel(item) }}</span>
                        <span class="recording-status">{{ statusLabel(item.status) }}</span>
                    </el-option>
                </el-select>
            </el-form-item>
            <el-form-item label="变量标记">
                <el-input
                    v-model="variablesText"
                    type="textarea"
                    :rows="4"
                    placeholder='步骤索引到变量名，如 {"0": "store.id", "2": "store.name"}；将替换 fill/select 的输入值为 ${变量} 占位符'
                />
            </el-form-item>
            <el-form-item label="上传fileKey标记">
                <el-input
                    v-model="fileKeysText"
                    type="textarea"
                    :rows="3"
                    placeholder='步骤索引到 fileKey，如 {"3": "price_tag"}；为上传步骤标注资源绑定键'
                />
            </el-form-item>
            <el-alert
                title="转换会生成新的版本草稿（不发布），步骤可在版本编辑器中继续调整。"
                type="info"
                :closable="false"
            />
        </el-form>
        <template #footer>
            <el-button @click="visible = false">取消</el-button>
            <el-button type="primary" :loading="converting" @click="convert">转换</el-button>
        </template>
    </el-dialog>
</template>

<script setup name="ConfigConvertDialog">
import { ref, reactive, computed, watch } from "vue";
import { ElMessage } from "element-plus";
import { convertRecordingToTemplate } from "@/api/hrm/configuration_task";
import { listWebRecording } from "@/api/hrm/web_case.js";

const props = defineProps({ modelValue: Boolean, task: Object });
const emit = defineEmits(["update:modelValue", "converted"]);

const visible = computed({
    get: () => props.modelValue,
    set: (value) => emit("update:modelValue", value)
});
const converting = ref(false);
const form = reactive({ recordingId: "" });
const variablesText = ref("{}");
const fileKeysText = ref("{}");
const recordingOptions = ref([]);
const recordingsLoading = ref(false);

// 录制状态枚举：与 Web 用例录制页保持一致（1 草稿 / 2 录制中 / 3 已完成 / 4 失败 / 5 已停止）。
const RECORDING_STATUS = {
    1: "草稿",
    2: "录制中",
    3: "已完成",
    4: "失败",
    5: "已停止"
};

function statusLabel(status) {
    return RECORDING_STATUS[status] || `状态${status ?? "-"}`;
}

// 下拉展示文案：名称优先，带 ID 和起始地址，方便在多条同名记录间区分。
function recordingLabel(item) {
    const name = item.sessionName || `录制记录 ${item.recordingId}`;
    return `${name} (#${item.recordingId})`;
}

// 远程搜索录制记录：按会话名称模糊匹配；关键字为空时拉取最近记录。
// 只回传已完成/已停止/失败的历史会话，草稿和录制中的会话没有可转换的完整步骤。
async function searchRecordings(keyword) {
    recordingsLoading.value = true;
    try {
        const res = await listWebRecording({
            sessionName: keyword || undefined,
            pageNum: 1,
            pageSize: 50,
            isPage: false
        });
        const rows = Array.isArray(res.data) ? res.data : res.rows || [];
        recordingOptions.value = rows.filter((row) => row.status !== 1 && row.status !== 2);
    } catch (e) {
        recordingOptions.value = [];
        ElMessage.error(e.message || "录制记录查询失败");
    } finally {
        recordingsLoading.value = false;
    }
}

watch(
    () => props.modelValue,
    (opened) => {
        if (opened) searchRecordings("");
    },
    { immediate: true }
);

async function convert() {
    if (!props.task || !form.recordingId) {
        ElMessage.warning("请选择录制记录");
        return;
    }
    let markVariables = {};
    let uploadFileKeys = {};
    try {
        markVariables = JSON.parse(variablesText.value || "{}");
    } catch {
        ElMessage.warning("变量标记必须是合法 JSON 对象");
        return;
    }
    try {
        uploadFileKeys = JSON.parse(fileKeysText.value || "{}");
    } catch {
        ElMessage.warning("fileKey 标记必须是合法 JSON 对象");
        return;
    }
    converting.value = true;
    try {
        await convertRecordingToTemplate({
            taskId: props.task.taskId,
            recordingId: form.recordingId,
            markVariables,
            uploadFileKeys
        });
        ElMessage.success("转换成功，已生成版本草稿");
        emit("converted");
    } catch (e) {
        ElMessage.error(e.message || "转换失败");
    } finally {
        converting.value = false;
    }
}
</script>

<style lang="scss" scoped>
.recording-status {
    float: right;
    font-size: 12px;
    color: var(--el-text-color-secondary);
}
</style>
