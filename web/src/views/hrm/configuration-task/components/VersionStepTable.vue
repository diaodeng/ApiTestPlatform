<template>
    <div class="version-step-table">
        <div class="step-table-toolbar">
            <span class="panel-title">测试步骤</span>
            <div class="toolbar-actions">
                <el-button type="primary" icon="Plus" size="small" @click="addStep">新增步骤</el-button>
            </div>
        </div>
        <el-table
            :data="steps"
            border
            size="small"
            max-height="420px"
            empty-text="暂无步骤，可手动新增或通过「录制转模板」生成"
            :row-class-name="rowClassName"
            @row-click="handleRowClick"
        >
            <el-table-column label="#" width="90" fixed="left">
                <template #default="{ $index, row }">
                    <div class="step-order-cell">
                        <span>{{ $index + 1 }}</span>
                        <el-switch
                            v-model="row.enabled"
                            size="small"
                            inline-prompt
                            active-text="启"
                            inactive-text="停"
                            @click.stop
                        />
                    </div>
                </template>
            </el-table-column>
            <el-table-column label="动作" width="150">
                <template #default="{ row }">
                    {{ actionLabel(row.actionType) }}
                </template>
            </el-table-column>
            <el-table-column label="步骤名称" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">
                    {{ row.stepName || "-" }}
                </template>
            </el-table-column>
            <el-table-column label="定位信息" min-width="220" show-overflow-tooltip>
                <template #default="{ row }">
                    {{ targetSummary(row) }}
                </template>
            </el-table-column>
            <el-table-column label="参数摘要" min-width="200" show-overflow-tooltip>
                <template #default="{ row }">
                    {{ paramsSummary(row) }}
                </template>
            </el-table-column>
            <el-table-column v-if="hasEvidenceStep" label="证据" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">
                    <template v-if="row.actionType === 'capture_screenshot'">
                        <el-tag size="small" type="info">{{ row.params?.evidenceType || 'checkpoint_screenshot' }}</el-tag>
                        <el-tag v-if="row.params?.required" size="small" type="warning" class="ml4">必需</el-tag>
                        <span v-if="row.params?.evidenceKey" class="evidence-key">{{ row.params.evidenceKey }}</span>
                    </template>
                    <span v-else>-</span>
                </template>
            </el-table-column>
            <el-table-column label="操作" width="190" fixed="right">
                <template #default="{ $index }">
                    <el-button link type="primary" icon="Edit" @click.stop="openDetail($index)">详情</el-button>
                    <el-button link icon="Top" :disabled="$index === 0" @click.stop="moveStep($index, -1)" />
                    <el-button
                        link
                        icon="Bottom"
                        :disabled="$index === steps.length - 1"
                        @click.stop="moveStep($index, 1)"
                    />
                    <el-button link type="danger" icon="Delete" @click.stop="removeStep($index)" />
                </template>
            </el-table-column>
        </el-table>

        <!-- 步骤详情编辑弹窗：复用 Web 用例的自包含组件，数据结构同为 WebStepModel -->
        <StepDetail
            v-if="showStepDetail"
            v-model:show-step-detail-dialog="showStepDetail"
            :current-step="currentStep"
            :step-index="currentStepIndex"
            @update="handleStepUpdated"
        />
    </div>
</template>

<script setup name="VersionStepTable">
import { ref, computed } from "vue";
import StepDetail from "@/components/hrm/case/webcase/components/StepDetail.vue";
import { actionOptions } from "@/components/hrm/case/webcase/utils/shared.js";
import {
    stepNeedsTarget,
    normalizeStepParams,
    createDefaultStep
} from "@/components/hrm/case/webcase/domain/stepDomain";
import { createDefaultTargetSnapshot } from "@/components/hrm/case/webcase/domain/snapshotDomain";

const props = defineProps({
    steps: { type: Array, required: true }
});
const emit = defineEmits(["change"]);

const showStepDetail = ref(false);
const currentStepIndex = ref(-1);
// StepDetail 通过 props 直接改写 currentStep 对象内部字段，这里给它一个稳定引用；
// 弹窗关闭时 emit('update')，表格整体通知父组件"已变化"。
const currentStep = computed(() => props.steps[currentStepIndex.value] || {});
const hasEvidenceStep = computed(() => props.steps.some((step) => step.actionType === "capture_screenshot"));

function actionLabel(actionType) {
    return actionOptions.find((item) => item.value === actionType)?.label || actionType || "-";
}

// 定位信息摘要：主定位器类型 + 值，无目标动作显示 -。
function targetSummary(row) {
    if (!stepNeedsTarget(row.actionType)) return "-";
    const target = row.targetSnapshot;
    const locators = target?.locators;
    if (Array.isArray(locators) && locators.length) {
        const primary = locators[0];
        const value = primary.locatorValue;
        const text =
            typeof value === "object" && value !== null
                ? value.name || value.text || value.role || JSON.stringify(value)
                : String(value ?? "");
        return `${primary.locatorType}: ${text}`;
    }
    return "(未设置)";
}

// 参数摘要：剔除空值后展示关键键值，给表格一个可扫读的概览。
function paramsSummary(row) {
    const params = row.params || {};
    const parts = [];
    for (const [key, value] of Object.entries(params)) {
        if (value === undefined || value === null || value === "") continue;
        if (key === "thinkTimeMs") continue;
        const text = typeof value === "object" ? JSON.stringify(value) : String(value);
        parts.push(`${key}=${text.length > 40 ? `${text.slice(0, 40)}…` : text}`);
    }
    return parts.join("; ") || "-";
}

function rowClassName({ rowIndex }) {
    return rowIndex === currentStepIndex.value ? "current-step-row" : "";
}

function handleRowClick(row) {
    const index = props.steps.indexOf(row);
    if (index >= 0) currentStepIndex.value = index;
}

function notifyChange() {
    emit("change", props.steps);
}

// 新增一个步骤到末尾：统一走 createDefaultStep 工厂，保证需要定位的动作
// 自动带上默认 targetSnapshot（缺它会触发详情弹窗 elementText 空指针）。
function addStep() {
    props.steps.push(createDefaultStep("fill"));
    currentStepIndex.value = props.steps.length - 1;
    notifyChange();
    openDetail(props.steps.length - 1);
}

// 打开详情前兜底：历史草稿或手工 JSON 可能没有 targetSnapshot，
// 而详情弹窗的定位卡片直接绑定 targetSnapshot 内部字段，必须先补齐。
function ensureTargetSnapshot(step) {
    if (step && stepNeedsTarget(step.actionType) && !step.targetSnapshot) {
        step.targetSnapshot = createDefaultTargetSnapshot();
    }
}

function openDetail(index) {
    if (index < 0 || index >= props.steps.length) return;
    currentStepIndex.value = index;
    ensureTargetSnapshot(props.steps[index]);
    showStepDetail.value = true;
}

function moveStep(index, offset) {
    const target = index + offset;
    if (target < 0 || target >= props.steps.length) return;
    const [step] = props.steps.splice(index, 1);
    props.steps.splice(target, 0, step);
    currentStepIndex.value = target;
    notifyChange();
}

function removeStep(index) {
    props.steps.splice(index, 1);
    if (currentStepIndex.value >= props.steps.length) {
        currentStepIndex.value = props.steps.length - 1;
    }
    notifyChange();
}

function handleStepUpdated() {
    // StepDetail 关闭时已直接改写步骤对象（引用相同），这里触发校验与同步。
    const step = props.steps[currentStepIndex.value];
    if (step) {
        step.params = normalizeStepParams(step.actionType, step.params);
    }
    notifyChange();
}
</script>

<style lang="scss" scoped>
.version-step-table {
    .step-table-toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;

        .panel-title {
            font-weight: 600;
        }
    }

    :deep(.current-step-row) {
        background: var(--el-fill-color-light);
    }

    .step-order-cell {
        display: flex;
        align-items: center;
        gap: 6px;
    }
}
</style>
