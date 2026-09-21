<template>
    <el-dialog v-model="visible" :title="`阶段切分 v${version?.versionNo || ''}`" width="980px">
        <el-alert
            v-if="version && version.status !== 'DRAFT'"
            title="仅草稿版本可修改阶段切分"
            type="warning"
            :closable="false"
            class="mb8"
        />
        <el-alert
            title="阶段优先按稳定 stepId 关联；步骤索引仅用于兼容旧版本。保存前请确认每个步骤只属于一个阶段。"
            type="info"
            :closable="false"
            class="mb8"
        />
        <div v-for="(stage, index) in stages" :key="index" class="stage-card">
            <div class="stage-row">
                <el-input v-model="stage.stageKey" placeholder="阶段标识" style="width: 140px" :disabled="!editable" />
                <el-input v-model="stage.stageName" placeholder="阶段名称" style="width: 160px" :disabled="!editable" />
                <el-select v-model="stage.mode" style="width: 150px" :disabled="!editable">
                    <el-option label="READ（查询）" value="READ" />
                    <el-option label="PREPARE_WRITE（填写）" value="PREPARE_WRITE" />
                    <el-option label="WRITE（写入，需审批）" value="WRITE" />
                    <el-option label="VERIFY（验证）" value="VERIFY" />
                </el-select>
                <el-input
                    :model-value="stepIndexesText(stage)"
                    placeholder="自动生成兼容索引"
                    style="width: 150px"
                    disabled
                />
                <el-button link type="danger" icon="Delete" @click="stages.splice(index, 1)" :disabled="!editable" />
            </div>
            <el-form label-width="110px" size="small" class="stage-policy-form">
                <el-form-item label="阶段步骤">
                    <el-select
                        v-model="stage.stepIds"
                        multiple
                        filterable
                        collapse-tags
                        collapse-tags-tooltip
                        style="width: 100%"
                        placeholder="请选择该阶段包含的步骤"
                        :disabled="!editable"
                    >
                        <el-option
                            v-for="item in stepOptionsFor(stage)"
                            :key="item.value"
                            :label="item.label"
                            :value="item.value"
                            :disabled="item.disabled && !stage.stepIds.includes(item.value)"
                        />
                    </el-select>
                    <div v-if="stage.missingStepIds.length" class="step-selection-warning">
                        已保存但当前版本不存在：{{ stage.missingStepIds.join("、") }}。请删除异常项或恢复对应步骤后再保存。
                    </div>
                </el-form-item>
                <el-form-item label="证据模式">
                    <el-radio-group v-model="stage.evidencePolicy.mode" :disabled="!editable">
                        <el-radio-button label="NONE">不要求</el-radio-button>
                        <el-radio-button label="OPTIONAL">可选</el-radio-button>
                        <el-radio-button label="REQUIRED">必需</el-radio-button>
                        <el-radio-button label="BEFORE_AFTER">前后对照</el-radio-button>
                    </el-radio-group>
                </el-form-item>
                <el-row :gutter="12">
                    <el-col :span="12">
                        <el-form-item label="必需类型">
                            <el-select
                                v-model="stage.evidencePolicy.requiredTypes"
                                multiple
                                :disabled="!editable"
                                collapse-tags
                                collapse-tags-tooltip
                                style="width: 100%"
                                placeholder="选择必需的截图类型"
                            >
                                <el-option label="检查点截图" value="checkpoint_screenshot" />
                                <el-option label="修改前截图" value="before_screenshot" />
                                <el-option label="修改后截图" value="after_screenshot" />
                            </el-select>
                        </el-form-item>
                    </el-col>
                    <el-col :span="12">
                        <el-form-item label="必需证据键">
                            <el-input
                                :model-value="stage.evidenceKeysText"
                                placeholder="多个证据键用逗号分隔"
                                :disabled="!editable"
                                @update:model-value="(value) => (stage.evidenceKeysText = value)"
                            />
                        </el-form-item>
                    </el-col>
                    <el-col :span="8">
                        <el-form-item label="完整性处理">
                            <el-select v-model="stage.evidencePolicy.completenessPolicy" style="width: 100%" :disabled="!editable">
                                <el-option label="仅提示（WARN）" value="WARN" />
                                <el-option label="阻断验收" value="BLOCK_ACCEPTANCE" />
                                <el-option label="阻断运行" value="BLOCK_RUN" />
                            </el-select>
                        </el-form-item>
                    </el-col>
                    <el-col :span="8">
                        <el-form-item label="保留天数">
                            <el-input-number v-model="stage.evidencePolicy.retentionDays" :min="1" :max="3650" controls-position="right" style="width: 100%" :disabled="!editable" />
                        </el-form-item>
                    </el-col>
                    <el-col :span="8">
                        <el-form-item label="遮罩策略ID">
                            <el-input v-model="stage.evidencePolicy.maskProfileId" placeholder="可选" :disabled="!editable" />
                        </el-form-item>
                    </el-col>
                </el-row>
            </el-form>
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

const ACTION_LABELS = {
    goto: "打开页面",
    click: "点击",
    fill: "填写",
    select_option: "下拉选择",
    upload_file: "上传文件",
    capture_screenshot: "截图",
    wait: "等待",
    sleep: "等待",
    assert_page_contains: "页面断言",
    assert_element: "元素断言",
    press: "按键"
};

const versionSteps = computed(() => (Array.isArray(props.version?.steps) ? props.version.steps : []));

const stepOptions = computed(() =>
    versionSteps.value
        .map((step, index) => {
            const value = stepIdOf(step);
            if (!value) return null;
            const actionType = String(step.actionType || step.action_type || "").trim();
            const actionLabel = ACTION_LABELS[actionType] || actionType || "未知动作";
            const stepName = String(step.stepName || step.step_name || "").trim() || "未命名步骤";
            return {
                value,
                label: `第${index + 1}步 · ${actionLabel} · ${stepName}`,
                stepIndex: index,
                disabled: false
            };
        })
        .filter(Boolean)
);

function stepIdOf(step) {
    return String(step?.stepId ?? step?.step_id ?? "").trim();
}

function normalizeStringArray(value) {
    const values = Array.isArray(value) ? value : value ? [value] : [];
    return [...new Set(values.map((item) => String(item ?? "").trim()).filter(Boolean))];
}

function normalizeIndexArray(value) {
    const values = Array.isArray(value) ? value : value ? [value] : [];
    return [...new Set(values.map((item) => Number(item)).filter((item) => Number.isInteger(item) && item >= 0))];
}

function stepOptionsFor(stage) {
    const knownIds = new Set(stepOptions.value.map((item) => item.value));
    const missingIds = normalizeStringArray(stage.missingStepIds).filter((id) => !knownIds.has(id));
    return [
        ...stepOptions.value,
        ...missingIds.map((id) => ({
            value: id,
            label: `已保存但当前版本不存在：${id}`,
            disabled: true
        }))
    ];
}

function stepIndexesFor(stage) {
    const indexById = new Map(stepOptions.value.map((item) => [item.value, item.stepIndex]));
    return normalizeStringArray(stage.stepIds)
        .map((id) => indexById.get(id))
        .filter((index) => Number.isInteger(index));
}

function stepIndexesText(stage) {
    return stepIndexesFor(stage).join(",");
}

function normalizePolicy(policy = {}) {
    return {
        mode: policy.mode || "NONE",
        requiredTypes: Array.isArray(policy.requiredTypes || policy.required_types)
            ? [...(policy.requiredTypes || policy.required_types)]
            : [],
        requiredEvidenceKeys: Array.isArray(policy.requiredEvidenceKeys || policy.required_evidence_keys)
            ? [...(policy.requiredEvidenceKeys || policy.required_evidence_keys)]
            : [],
        completenessPolicy: policy.completenessPolicy || policy.completeness_policy || "WARN",
        retentionDays: Number(policy.retentionDays || policy.retention_days || 90),
        maskProfileId: policy.maskProfileId || policy.mask_profile_id || ""
    };
}

function stageFromResponse(item) {
    const policy = normalizePolicy(item.evidencePolicy || item.evidence_policy);
    const stepIndexes = normalizeIndexArray(item.stepIndexes || item.step_indexes);
    const responseStepIds = normalizeStringArray(item.stepIds || item.step_ids);
    const stepIds = responseStepIds.length
        ? responseStepIds
        : stepIndexes.map((index) => stepIdOf(versionSteps.value[index])).filter(Boolean);
    const knownIds = new Set(stepOptions.value.map((option) => option.value));
    const missingStepIds = stepIds.filter((id) => !knownIds.has(id));
    return {
        stageKey: item.stageKey || item.stage_key || "",
        stageName: item.stageName || item.stage_name || "",
        mode: item.mode || "READ",
        stepIds,
        missingStepIds,
        evidenceKeysText: policy.requiredEvidenceKeys.join(","),
        evidencePolicy: policy
    };
}

watch(
    () => [props.modelValue, props.version?.versionId],
    async ([opened]) => {
        if (!opened || !props.version) return;
        try {
            const res = await listVersionStages(props.version.versionId);
            stages.value = (res.data || []).map(stageFromResponse);
        } catch (e) {
            stages.value = [];
        }
    },
    { immediate: true }
);

function addStage() {
    stages.value.push({
        stageKey: "",
        stageName: "",
        mode: "READ",
        stepIds: [],
        missingStepIds: [],
        evidenceKeysText: "",
        evidencePolicy: normalizePolicy()
    });
}

function parseStrings(text) {
    return normalizeStringArray((text || "").split(","));
}

async function save() {
    if (!props.version) return;
    const indexById = new Map(stepOptions.value.map((item) => [item.value, item.stepIndex]));
    const invalidStepIds = new Set();
    const emptyStageIndex = stages.value.findIndex((stage) => {
        const stepIds = normalizeStringArray(stage.stepIds);
        stepIds.forEach((id) => {
            if (!indexById.has(id)) invalidStepIds.add(id);
        });
        return stepIds.length === 0;
    });
    if (invalidStepIds.size) {
        ElMessage.warning(`阶段包含当前版本不存在的步骤：${[...invalidStepIds].join("、")}`);
        return;
    }
    if (emptyStageIndex >= 0) {
        ElMessage.warning(`第${emptyStageIndex + 1}个阶段至少选择一个步骤`);
        return;
    }
    const payload = stages.value.map((stage) => {
        const stepIds = normalizeStringArray(stage.stepIds);
        const stepIndexes = stepIds.map((id) => indexById.get(id));
        return {
            stageKey: stage.stageKey,
            stageName: stage.stageName,
            mode: stage.mode,
            stepIndexes,
            stepIds,
            evidencePolicy: {
                ...stage.evidencePolicy,
                requiredEvidenceKeys: parseStrings(stage.evidenceKeysText)
            }
        };
    });
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
.stage-card {
    padding: 10px;
    margin-bottom: 12px;
    border: 1px solid var(--el-border-color-light);
    border-radius: 4px;
}
.stage-row {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 8px;
}
.stage-policy-form {
    margin-top: 8px;
}
.step-selection-warning {
    margin-top: 6px;
    color: var(--el-color-warning);
    line-height: 1.5;
    font-size: 12px;
}
</style>
