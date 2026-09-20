<template>
    <el-dialog v-model="visible" title="录制转模板" width="560px">
        <el-form label-width="130px">
            <el-form-item label="目标任务">
                <span>{{ task?.taskName }}</span>
            </el-form-item>
            <el-form-item label="录制记录ID" required>
                <el-input v-model="form.recordingId" placeholder="录制会话 ID（录制记录页可查看）" />
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
import { ref, reactive, computed } from "vue";
import { ElMessage } from "element-plus";
import { convertRecordingToTemplate } from "@/api/hrm/configuration_task";

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

async function convert() {
    if (!props.task || !form.recordingId.trim()) {
        ElMessage.warning("请填写录制记录 ID");
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
            recordingId: form.recordingId.trim(),
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
