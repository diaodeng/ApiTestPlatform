<template>
    <el-dialog v-model="visible" :title="`阶段切分 v${version?.versionNo || ''}`" width="720px">
        <el-alert
            v-if="version && version.status !== 'DRAFT'"
            title="仅草稿版本可修改阶段切分"
            type="warning"
            :closable="false"
            class="mb8"
        />
        <div v-for="(stage, index) in stages" :key="index" class="stage-row">
            <el-input v-model="stage.stageKey" placeholder="阶段标识" style="width: 140px" />
            <el-input v-model="stage.stageName" placeholder="阶段名称" style="width: 160px" />
            <el-select v-model="stage.mode" style="width: 150px">
                <el-option label="READ（查询）" value="READ" />
                <el-option label="PREPARE_WRITE（填写）" value="PREPARE_WRITE" />
                <el-option label="WRITE（写入，需审批）" value="WRITE" />
                <el-option label="VERIFY（验证）" value="VERIFY" />
            </el-select>
            <el-input v-model="stage.stepIndexesText" placeholder="步骤索引，如 0,1" style="width: 150px" />
            <el-button link type="danger" icon="Delete" @click="stages.splice(index, 1)" />
        </div>
        <el-button icon="Plus" @click="addStage" :disabled="!editable">添加阶段</el-button>
        <template #footer>
            <el-button @click="visible = false">取消</el-button>
            <el-button type="primary" :loading="saving" :disabled="!editable" @click="save">保存切分</el-button>
        </template>
    </el-dialog>
</template>

<script setup name="ConfigStageEditor">
import { ref, watch, computed } from "vue";
import { ElMessage } from "element-plus";
import { listVersionStages, saveVersionStages } from "@/api/hrm/configuration_task";

const props = defineProps({ modelValue: Boolean, version: Object });
const emit = defineEmits(["update:modelValue"]);

const visible = computed({
    get: () => props.modelValue,
    set: (value) => emit("update:modelValue", value)
});
const saving = ref(false);
const stages = ref([]);

const editable = computed(() => props.version?.status === "DRAFT");

watch(
    () => [props.modelValue, props.version?.versionId],
    async ([opened]) => {
        if (!opened || !props.version) return;
        try {
            const res = await listVersionStages(props.version.versionId);
            stages.value = (res.data || []).map((item) => ({
                stageKey: item.stageKey,
                stageName: item.stageName,
                mode: item.mode,
                stepIndexesText: (item.stepIndexes || []).join(",")
            }));
        } catch (e) {
            stages.value = [];
        }
    },
    { immediate: true }
);

function addStage() {
    stages.value.push({ stageKey: "", stageName: "", mode: "READ", stepIndexesText: "" });
}

async function save() {
    if (!props.version) return;
    const payload = [];
    for (const stage of stages.value) {
        const indexes = (stage.stepIndexesText || "")
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean)
            .map(Number);
        payload.push({
            stageKey: stage.stageKey,
            stageName: stage.stageName,
            mode: stage.mode,
            stepIndexes: indexes
        });
    }
    saving.value = true;
    try {
        await saveVersionStages(props.version.versionId, payload);
        ElMessage.success("阶段切分已保存");
        visible.value = false;
    } catch (e) {
        ElMessage.error(e.message || "保存失败");
    } finally {
        saving.value = false;
    }
}
</script>

<style lang="scss" scoped>
.stage-row {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 8px;
}
</style>
