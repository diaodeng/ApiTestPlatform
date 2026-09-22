<template>
    <div class="run-record-tab">
        <el-form :inline="true" class="mb8">
            <el-form-item label="任务ID">
                <el-input v-model="queryTaskId" placeholder="按任务ID过滤（可选）" clearable style="width: 220px" />
            </el-form-item>
            <el-form-item label="状态">
                <el-select v-model="queryStatus" clearable placeholder="全部" style="width: 140px">
                    <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
            </el-form-item>
            <el-form-item>
                <el-button type="primary" icon="Search" @click="getList">查询</el-button>
                <el-button icon="Refresh" @click="reset">重置</el-button>
            </el-form-item>
        </el-form>

        <el-table v-loading="loading" :data="runList" border>
            <el-table-column label="运行ID" prop="taskRunId" width="180" show-overflow-tooltip />
            <el-table-column label="任务ID" prop="taskId" width="180" show-overflow-tooltip />
            <el-table-column label="版本" width="70">
                <template #default="{ row }">v{{ row.versionNo }}</template>
            </el-table-column>
            <el-table-column label="Agent" prop="agentCode" width="130" show-overflow-tooltip />
            <el-table-column label="触发" prop="triggerType" width="90" />
            <el-table-column label="状态" width="110">
                <template #default="{ row }">
                    <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
                </template>
            </el-table-column>
            <el-table-column label="开始时间" prop="startedAt" width="160" />
            <el-table-column label="时长(ms)" prop="durationMs" width="100" />
            <el-table-column label="错误" prop="errorMessage" min-width="180" show-overflow-tooltip />
            <el-table-column label="操作" width="200" fixed="right">
                <template #default="{ row }">
                    <el-button link type="primary" icon="View" @click="$emit('open-detail', row)">详情</el-button>
                    <el-button
                        v-if="row.status === 'RUNNING'"
                        link
                        type="danger"
                        icon="VideoPause"
                        @click="stop(row)"
                    >停止</el-button>
                    <el-button
                        v-if="['SUCCESS', 'FAILED'].includes(row.status)"
                        link
                        type="warning"
                        icon="RefreshRight"
                        :loading="rerunningId === row.taskRunId"
                        @click="rerun(row)"
                    >重跑</el-button>
                </template>
            </el-table-column>
        </el-table>
    </div>
</template>

<script setup name="ConfigRunRecordTab">
import { ref, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { listRuns, stopRun, createRun } from "@/api/hrm/configuration_task";

const emit = defineEmits(["open-detail"]);

const loading = ref(false);
const rerunningId = ref("");
const queryTaskId = ref("");
const queryStatus = ref("");
const runList = ref([]);

const statusOptions = [
    { value: "PENDING", label: "等待中" },
    { value: "RUNNING", label: "运行中" },
    { value: "SUCCESS", label: "成功" },
    { value: "FAILED", label: "失败" },
    { value: "CANCELLED", label: "已取消" }
];

onMounted(() => getList());

async function getList() {
    // 运行列表接口按任务维度查询；未填任务ID时不支持全量查询，提示用户。
    if (!queryTaskId.value.trim()) {
        ElMessage.info("请输入任务ID查询运行记录（任务列表页可复制）");
        return;
    }
    loading.value = true;
    try {
        const res = await listRuns(queryTaskId.value.trim(), { status: queryStatus.value || undefined, limit: 100 });
        runList.value = res.data || [];
    } catch (e) {
        ElMessage.error(e.message || "运行记录查询失败");
    } finally {
        loading.value = false;
    }
}

function reset() {
    queryTaskId.value = "";
    queryStatus.value = "";
    runList.value = [];
}

async function stop(row) {
    try {
        await ElMessageBox.confirm(`停止运行 ${row.taskRunId}？`, "停止确认", { type: "warning" });
    } catch {
        return;
    }
    try {
        await stopRun(row.taskRunId, { reason: "用户从运行记录页停止" });
        ElMessage.success("已发送停止命令");
        getList();
    } catch (e) {
        ElMessage.error(e.message || "停止失败");
    }
}

// 历史记录重跑：按原版本号重新创建运行（凭证/映射取最新配置，登录态回写后重跑即生效）。
// 注意：会真实执行外站操作，弹二次确认；与停止共用"同步等待执行完成"的交互。
async function rerun(row) {
    try {
        await ElMessageBox.confirm(
            `按 v${row.versionNo} 重新发起运行？将使用当前最新的凭证映射与登录态，并真实执行外站操作。`,
            "重跑确认",
            { type: "warning" }
        );
    } catch {
        return;
    }
    try {
        await ElMessageBox.confirm(
            `再次确认：对任务 ${row.taskId} 发起 v${row.versionNo} 重跑？`,
            "重跑二次确认",
            { type: "warning" }
        );
    } catch {
        return;
    }
    rerunningId.value = row.taskRunId;
    try {
        const res = await createRun(row.taskId, {
            versionNo: row.versionNo,
            triggerType: "manual",
            failureStrategy: "stop"
        });
        ElMessage.success(`重跑完成：${res.data?.status || "已提交"}`);
        getList();
    } catch (e) {
        ElMessage.error(e.message || "重跑失败");
    } finally {
        rerunningId.value = "";
    }
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

function statusLabel(status) {
    return {
        SUCCESS: "成功",
        FAILED: "失败",
        CANCELLED: "已取消",
        RUNNING: "运行中",
        PENDING: "等待中"
    }[status] || status;
}

defineExpose({ getList });
</script>
