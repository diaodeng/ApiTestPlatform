<template>
    <el-drawer :model-value="modelValue" title="运行详情" size="60%" @update:model-value="$emit('update:modelValue', $event)">
        <div v-loading="loading">
            <template v-if="run">
                <el-descriptions :column="2" border size="small" class="mb8">
                    <el-descriptions-item label="业务状态">
                        <el-tag :type="statusType(run.businessStatus || run.status)">{{ run.businessStatus || run.status }}</el-tag>
                    </el-descriptions-item>
                    <el-descriptions-item label="证据状态">
                        <el-tag :type="evidenceStatusType(run.evidenceStatus)">{{ run.evidenceStatus || "NOT_REQUIRED" }}</el-tag>
                    </el-descriptions-item>
                    <el-descriptions-item label="运行ID">{{ run.taskRunId }}</el-descriptions-item>
                    <el-descriptions-item label="版本">v{{ run.versionNo }}</el-descriptions-item>
                    <el-descriptions-item label="Agent">{{ run.agentCode }}</el-descriptions-item>
                    <el-descriptions-item label="触发方式">{{ run.triggerType }}</el-descriptions-item>
                    <el-descriptions-item label="时长">{{ run.durationMs }} ms</el-descriptions-item>
                    <el-descriptions-item label="开始时间">{{ run.startedAt || "-" }}</el-descriptions-item>
                    <el-descriptions-item label="结束时间">{{ run.endedAt || "-" }}</el-descriptions-item>
                </el-descriptions>
                <el-alert
                    v-if="run.evidenceMissing?.length"
                    title="业务执行状态与证据完整状态独立计算，以下证据尚未满足策略要求。"
                    type="warning"
                    :closable="false"
                    class="mb8"
                >
                    <ul class="missing-list">
                        <li v-for="(item, index) in run.evidenceMissing" :key="`${item.evidenceKey || item.evidenceType}-${index}`">
                            {{ item.evidenceType || "证据" }}{{ item.evidenceKey ? ` / ${item.evidenceKey}` : "" }}：{{ item.reason || "未满足" }}
                        </li>
                    </ul>
                </el-alert>
                <el-alert
                    v-if="run.errorMessage"
                    :title="run.errorMessage"
                    type="error"
                    :closable="false"
                    class="mb8"
                />

                <el-tabs>
                    <el-tab-pane label="阶段">
                        <el-table :data="stages" border size="small">
                            <el-table-column label="顺序" prop="stageOrder" width="60" />
                            <el-table-column label="阶段" prop="stageName" min-width="120" />
                            <el-table-column label="模式" prop="mode" width="140" />
                                    <el-table-column label="状态" width="150">
                                <template #default="{ row }">
                                    <el-tag :type="stageStatusType(row.status)" size="small">{{ row.status }}</el-tag>
                                    <el-tag :type="evidenceStatusType(row.evidenceStatus)" size="small" class="ml4">证据 {{ row.evidenceStatus || "NOT_REQUIRED" }}</el-tag>
                                </template>
                            </el-table-column>
                            <el-table-column label="审批人" prop="approvedBy" width="90" />
                            <el-table-column label="重试" prop="retryCount" width="60" />
                            <el-table-column label="操作" width="140">
                                <template #default="{ row }">
                                    <el-button
                                        v-if="row.status === 'WAITING_APPROVAL' && row.mode === 'WRITE'"
                                        link
                                        type="success"
                                        @click="approve(row, true)"
                                    >通过</el-button>
                                    <el-button
                                        v-if="row.status === 'WAITING_APPROVAL' && row.mode === 'WRITE'"
                                        link
                                        type="danger"
                                        @click="approve(row, false)"
                                    >拒绝</el-button>
                                    <el-button
                                        v-if="row.status === 'FAILED'"
                                        link
                                        type="warning"
                                        @click="retry(row)"
                                    >重试</el-button>
                                </template>
                            </el-table-column>
                        </el-table>
                    </el-tab-pane>
                    <el-tab-pane label="步骤结果">
                        <el-table :data="stepResults" border size="small">
                            <el-table-column label="序号" prop="stepIndex" width="60" />
                            <el-table-column label="步骤" prop="stepName" min-width="140" />
                            <el-table-column label="状态" prop="status" width="90" />
                            <el-table-column label="耗时(ms)" prop="durationMs" width="90" />
                            <el-table-column label="消息" prop="message" min-width="180" show-overflow-tooltip />
                        </el-table>
                    </el-tab-pane>
                    <el-tab-pane label="产物">
                        <el-table :data="artifacts" border size="small">
                            <el-table-column label="类型" prop="artifactType" width="150" />
                            <el-table-column label="证据键" prop="evidenceKey" min-width="140" show-overflow-tooltip />
                            <el-table-column label="步骤ID" prop="stepId" min-width="150" show-overflow-tooltip />
                            <el-table-column label="可取回状态" prop="availabilityStatus" width="130" />
                            <el-table-column label="文件名" prop="originalFileName" min-width="160" />
                            <el-table-column label="资源ID" prop="resourceId" width="180" />
                            <el-table-column label="大小" prop="fileSize" width="90" />
                        </el-table>
                        <div class="mt8">
                            <el-button type="primary" size="small" :loading="reporting" @click="generateReport(false)">
                                生成报告
                            </el-button>
                            <el-button type="success" size="small" :loading="reporting" @click="generateReport(true)">
                                生成报告并通知飞书
                            </el-button>
                        </div>
                    </el-tab-pane>
                </el-tabs>
            </template>
            <el-empty v-else-if="!loading" description="运行不存在" />
        </div>
    </el-drawer>
</template>

<script setup name="ConfigRunDetailDrawer">
import { ref, computed, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
    getRun,
    listRunStages,
    listRunArtifacts,
    approveRunStage,
    retryRunStage,
    generateRunReport
} from "@/api/hrm/configuration_task";

const props = defineProps({ modelValue: Boolean, taskRunId: String });
const emit = defineEmits(["update:modelValue"]);

const visible = computed({
    get: () => props.modelValue,
    set: (value) => emit("update:modelValue", value)
});
const loading = ref(false);
const reporting = ref(false);
const run = ref(null);
const stages = ref([]);
const artifacts = ref([]);

const stepResults = computed(() => {
    const steps = run.value?.result?.steps;
    return Array.isArray(steps) ? steps : [];
});

watch(
    () => [props.modelValue, props.taskRunId],
    async ([opened]) => {
        if (!opened || !props.taskRunId) return;
        await loadAll();
    },
    { immediate: true }
);

async function loadAll() {
    loading.value = true;
    try {
        const [runRes, stageRes, artifactRes] = await Promise.all([
            getRun(props.taskRunId),
            listRunStages(props.taskRunId),
            listRunArtifacts(props.taskRunId)
        ]);
        run.value = runRes.data || null;
        stages.value = stageRes.data || [];
        artifacts.value = artifactRes.data || [];
    } catch (e) {
        ElMessage.error(e.message || "运行详情加载失败");
    } finally {
        loading.value = false;
    }
}

async function approve(row, approved) {
    let comment = "";
    if (!approved) {
        try {
            const res = await ElMessageBox.prompt("请输入拒绝原因", "拒绝审批", { type: "warning" });
            comment = res.value || "";
        } catch {
            return;
        }
    } else {
        try {
            await ElMessageBox.confirm(
                `确认允许执行 WRITE 阶段「${row.stageName}」？该阶段将执行保存/导入等写操作。`,
                "审批确认",
                { type: "warning" }
            );
        } catch {
            return;
        }
    }
    try {
        await approveRunStage(row.runStageId, { approved, comment });
        ElMessage.success(approved ? "审批通过" : "已拒绝");
        loadAll();
    } catch (e) {
        ElMessage.error(e.message || "审批操作失败");
    }
}

async function retry(row) {
    try {
        await ElMessageBox.confirm(`重试阶段「${row.stageName}」？WRITE 阶段重试需重新审批。`, "重试确认", {
            type: "warning"
        });
    } catch {
        return;
    }
    try {
        await retryRunStage(row.runStageId);
        ElMessage.success("阶段已重置");
        loadAll();
    } catch (e) {
        ElMessage.error(e.message || "重试失败");
    }
}

async function generateReport(notifyFeishu) {
    reporting.value = true;
    try {
        await generateRunReport(props.taskRunId, notifyFeishu);
        ElMessage.success("报告归档成功");
        loadAll();
    } catch (e) {
        ElMessage.error(e.message || "报告生成失败");
    } finally {
        reporting.value = false;
    }
}

function evidenceStatusType(status) {
    return {
        NOT_REQUIRED: "info",
        PENDING: "warning",
        COMPLETE: "success",
        INCOMPLETE: "warning",
        FAILED: "danger"
    }[status] || "info";
}

function statusType(status) {
    return {
        SUCCESS: "success",
        FAILED: "danger",
        CANCELLED: "info",
        RUNNING: "primary",
        PENDING: "info"
    }[status] || "info";
}

function stageStatusType(status) {
    return {
        SUCCESS: "success",
        FAILED: "danger",
        CANCELLED: "info",
        SKIPPED: "info",
        WAITING_APPROVAL: "warning",
        RUNNING: "primary",
        PENDING: "info"
    }[status] || "info";
}
</script>

<style scoped>
.missing-list {
    margin: 0;
    padding-left: 18px;
}
.ml4 {
    margin-left: 4px;
}
</style>
