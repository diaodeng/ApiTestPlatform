<template>
    <div class="run-tab-content">
        <el-form :inline="true" :model="queryParams" class="mb8">
            <el-form-item label="所属用例">
                <el-select
                    v-model="queryParams.webCaseId"
                    clearable
                    filterable
                    remote
                    reserve-keyword
                    placeholder="输入用例名称搜索"
                    style="width: 240px"
                    :remote-method="searchCaseOptions"
                    :loading="caseSelectLoading"
                    @visible-change="handleCaseSelectVisibleChange"
                >
                    <el-option
                        v-for="item in caseSelectOptions"
                        :key="item.webCaseId"
                        :label="item.caseName"
                        :value="item.webCaseId"
                    />
                </el-select>
            </el-form-item>
            <el-form-item label="执行状态">
                <el-select
                    v-model="queryParams.status"
                    clearable
                    placeholder="全部状态"
                    style="width: 160px"
                >
                    <el-option
                        v-for="item in runStatusOptions"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                    />
                </el-select>
            </el-form-item>
            <el-form-item label="Agent编码">
                <el-input
                    v-model="queryParams.agentCode"
                    placeholder="支持精确筛选"
                    clearable
                />
            </el-form-item>
            <el-form-item>
                <el-button type="primary" icon="Search" @click="getRunList"
                    >搜索</el-button
                >
                <el-button icon="Refresh" @click="resetRunQuery"
                    >重置</el-button
                >
            </el-form-item>
        </el-form>

        <el-row :gutter="10" class="mb8">
            <el-col :span="1.5">
                <el-button
                    type="default"
                    plain
                    icon="Refresh"
                    @click="getRunList"
                    >刷新</el-button
                >
            </el-col>
            <el-col :span="2">
                <el-button
                    type="danger"
                    plain
                    icon="Delete"
                    :disabled="!selectedRows.length"
                    @click="handleDeleteRecords()"
                    v-hasPermi="['hrm:webCase:remove']"
                >
                    删除记录
                </el-button>
            </el-col>
        </el-row>

        <el-table
            v-loading="loading"
            :data="dataList"
            border
            table-layout="fixed"
            max-height="calc(100vh - 320px)"
            row-key="webCaseRunId"
            @selection-change="handleSelectionChange"
        >
            <el-table-column
                type="selection"
                width="52"
                align="center"
                :reserve-selection="true"
            />
            <el-table-column
                label="执行记录ID"
                prop="webCaseRunId"
                width="170"
            />
            <el-table-column label="用例名称" min-width="220">
                <template #default="scope">{{
                    getCaseName(scope.row.webCaseId) ||
                    scope.row.webCaseId ||
                    "-"
                }}</template>
            </el-table-column>
            <el-table-column
                label="Agent"
                prop="agentCode"
                min-width="160"
                show-overflow-tooltip
            />
            <el-table-column label="触发方式" prop="triggerType" width="110" />
            <el-table-column label="状态" width="100">
                <template #default="scope">
                    <el-tag :type="getRunStatusMeta(scope.row.status).type">{{
                        getRunStatusMeta(scope.row.status).label
                    }}</el-tag>
                </template>
            </el-table-column>
            <el-table-column label="开始时间" min-width="170">
                <template #default="scope">{{
                    formatTime(scope.row.startedAt)
                }}</template>
            </el-table-column>
            <el-table-column label="耗时" width="120">
                <template #default="scope">{{
                    formatDuration(scope.row.durationMs)
                }}</template>
            </el-table-column>
            <el-table-column label="失败原因" min-width="260" show-overflow-tooltip>
                <template #default="scope">{{
                    getRunRowFailureReason(scope.row)
                }}</template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
                <template #default="scope">
                    <el-button
                        link
                        type="primary"
                        icon="View"
                        @click="openRunDetail(scope.row)"
                        >查看详情</el-button
                    >
                    <el-button
                        v-if="canStopRun(scope.row)"
                        link
                        type="warning"
                        icon="VideoPause"
                        @click="handleStopRun(scope.row)"
                        v-hasPermi="['hrm:webCase:run']"
                    >
                        停止
                    </el-button>
                    <el-button
                        v-if="canCancelPreparedRun(scope.row)"
                        link
                        type="warning"
                        icon="CircleClose"
                        @click="handleCancelPreparedRun(scope.row)"
                        v-hasPermi="['hrm:webCase:run']"
                    >
                        取消准备
                    </el-button>
                    <el-button
                        link
                        type="danger"
                        icon="Delete"
                        @click="handleDeleteRecords(scope.row)"
                        v-hasPermi="['hrm:webCase:remove']"
                        >删除</el-button
                    >
                </template>
            </el-table-column>
        </el-table>

        <div class="pager">
            <el-pagination
                v-model:current-page="queryParams.pageNum"
                v-model:page-size="queryParams.pageSize"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                :total="total"
                @size-change="getRunList"
                @current-change="getRunList"
            />
        </div>
    </div>
</template>

<script setup>
import { getCurrentInstance, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
    cancelWebRun,
    delWebRun,
    listWebCase,
    listWebRun,
    stopWebRun,
} from "@/api/hrm/web_case.js";
import {
    extractRows,
    mergeCaseOptions,
    normalizeIdValue,
    runStatusOptions,
} from "../utils/shared.js";

/**
 * RunTab 组件事件定义。
 * @property {(rows: Array) => void} sync-case-options 同步父组件可复用的用例选项
 * @property {(row: object) => void} open-detail 打开执行详情弹窗
 * @property {(ids: Array<string>) => void} deleted 删除记录后通知父组件清理详情状态
 */
const emit = defineEmits(["sync-case-options", "open-detail", "deleted"]);

const { proxy } = getCurrentInstance();

const loading = ref(false);
const total = ref(0);
const dataList = ref([]);
const selectedRows = ref([]);
const queryParams = ref({
    pageNum: 1,
    pageSize: 10,
    webCaseId: undefined,
    status: undefined,
    agentCode: undefined,
});
const caseSelectOptions = ref([]);
const caseSelectLoading = ref(false);

/**
 * 标准化主键值。
 * @param {any} value 原始值
 * @returns {string|undefined} 标准化主键
 */
/**
 * 格式化时间。
 * @param {string|number|Date} value 时间值
 * @returns {string} 格式化文本
 */
function formatTime(value) {
    return value ? proxy.parseTime(value) : "-";
}

/**
 * 格式化执行耗时。
 * @param {number|string} value 毫秒数
 * @returns {string} 可读耗时
 */
function formatDuration(value) {
    if (value === undefined || value === null || value === "") return "-";
    const ms = Number(value);
    if (!Number.isFinite(ms)) return `${value}`;
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)}s`;
    const minutes = Math.floor(ms / 60000);
    const seconds = ((ms % 60000) / 1000).toFixed(1);
    return `${minutes}m ${seconds}s`;
}

/**
 * 获取状态标签配置。
 * @param {number|string} status 状态值
 * @returns {{label: string, type: string}} 状态配置
 */
function getRunStatusMeta(status) {
    return (
        runStatusOptions.find((item) => item.value === status) || {
            label: `${status ?? "-"}`,
            type: "info",
        }
    );
}

/**
 * 根据用例 ID 获取名称。
 * @param {string|number} webCaseId 用例 ID
 * @returns {string} 用例名称
 */
function getCaseName(webCaseId) {
    if (!webCaseId) return "";
    const caseItem = caseSelectOptions.value.find(
        (item) => item.webCaseId === normalizeIdValue(webCaseId),
    );
    return caseItem?.caseName || "";
}

/**
 * 获取失败原因文本。
 * @param {Record<string, any>} row 执行记录
 * @returns {string} 失败原因
 */
function getRunRowFailureReason(row) {
    if (!row) return "-";
    const direct = `${row?.errorMessage ?? ""}`.trim();
    if (direct) return direct;

    const steps = Array.isArray(row?.result?.steps) ? row.result.steps : [];
    const failedStep = steps.find(
        (item) =>
            item &&
            ![
                "passed",
                "success",
                "ok",
                "skipped",
                "skip",
                "disabled",
                "running",
                "in_progress",
                "processing",
            ].includes(`${item.status ?? ""}`.trim().toLowerCase()) &&
            ![1, true].includes(item.status),
    );
    if (!failedStep) return "-";

    const candidates = [
        failedStep.error,
        failedStep.errorMessage,
        failedStep.message,
        failedStep.reason,
        failedStep.errorType,
        failedStep.error_type,
    ];
    for (const item of candidates) {
        const text = `${item ?? ""}`.trim();
        if (text) return text;
    }
    return "执行失败（无详细错误）";
}

/**
 * 判断执行记录是否处于等待手动确认状态。
 * @param {Record<string, any>} row 执行记录
 * @returns {boolean} 是否等待确认
 */
function isRunWaitingManualConfirm(row) {
    const resultPayload = row?.result || {};
    if (resultPayload.awaitingManualConfirm === true) return true;

    const directGate = resultPayload.manualLoginGate || null;
    const runtimeDebug = resultPayload.runtimeDebug || null;
    const runtimeGate = runtimeDebug?.manualLoginGate || null;
    const gate = directGate || runtimeGate;
    if (gate && gate.waitingConfirm === true) return true;

    const statusText = `${resultPayload.manualLoginStatus || ""}`
        .trim()
        .toLowerCase();
    return statusText === "waiting_manual_login";
}

/**
 * 判断是否允许停止执行。
 * @param {Record<string, any>} row 执行记录
 * @returns {boolean} 是否允许停止
 */
function canStopRun(row) {
    return Number(row?.status) === 9 && !isRunWaitingManualConfirm(row);
}

/**
 * 判断是否允许取消执行准备。
 * @param {Record<string, any>} row 执行记录
 * @returns {boolean} 是否允许取消准备
 */
function canCancelPreparedRun(row) {
    return Number(row?.status) === 9 && isRunWaitingManualConfirm(row);
}

/**
 * 搜索可选用例。
 * @param {string} keyword 搜索关键字
 * @returns {Promise<Array>} 搜索结果
 */
function searchCaseOptions(keyword = "") {
    const searchKeyword = keyword?.trim();
    caseSelectLoading.value = true;
    return listWebCase({
        pageNum: 1,
        pageSize: searchKeyword ? 50 : 200,
        caseName: searchKeyword || undefined,
    })
        .then((response) => {
            const rows = mergeCaseOptions(extractRows(response));
            caseSelectOptions.value = rows;
            emit("sync-case-options", rows);
            return rows;
        })
        .finally(() => {
            caseSelectLoading.value = false;
        });
}

/**
 * 下拉展开时初始化用例选项。
 * @param {boolean} visible 是否展开
 * @returns {void}
 */
function handleCaseSelectVisibleChange(visible) {
    if (visible && !caseSelectOptions.value.length) {
        searchCaseOptions("");
    }
}

/**
 * 获取执行记录列表。
 * @returns {Promise<void>} 列表加载任务
 */
function getRunList() {
    loading.value = true;
    return listWebRun(queryParams.value)
        .then((response) => {
            dataList.value = response.rows || [];
            total.value = response.total || 0;
            const merged = mergeCaseOptions(caseSelectOptions.value, dataList.value);
            caseSelectOptions.value = merged;
            emit("sync-case-options", merged);
        })
        .finally(() => {
            loading.value = false;
        });
}

/**
 * 重置执行记录查询条件并刷新列表。
 * @returns {Promise<void>} 列表加载任务
 */
function resetRunQuery() {
    queryParams.value = {
        pageNum: 1,
        pageSize: 10,
        webCaseId: undefined,
        status: undefined,
        agentCode: undefined,
    };
    selectedRows.value = [];
    return getRunList();
}

/**
 * 供父组件切换到执行记录页并设置筛选。
 * @param {string|number} webCaseId 用例 ID
 * @returns {Promise<void>} 列表加载任务
 */
function openHistoryByCase(webCaseId) {
    queryParams.value.webCaseId = normalizeIdValue(webCaseId);
    queryParams.value.pageNum = 1;
    return getRunList();
}

/**
 * 收集要删除的执行记录 ID。
 * @param {Record<string, any>|null} row 指定行
 * @returns {Array<string>} 执行记录 ID 列表
 */
function collectRunRecordIds(row) {
    if (row?.webCaseRunId) {
        return [normalizeIdValue(row.webCaseRunId)].filter(Boolean);
    }
    const ids = selectedRows.value
        .map((item) => normalizeIdValue(item?.webCaseRunId))
        .filter(Boolean);
    return Array.from(new Set(ids));
}

/**
 * 停止执行记录。
 * @param {Record<string, any>} row 执行记录
 * @returns {Promise<void>} 停止任务
 */
async function handleStopRun(row) {
    const runId = normalizeIdValue(row?.webCaseRunId);
    if (!runId) return;
    try {
        await ElMessageBox.confirm(`确认停止执行记录【${runId}】吗？`, "提示", {
            type: "warning",
        });
    } catch {
        return;
    }
    try {
        const response = await stopWebRun({
            webCaseRunId: runId,
            agentId: row?.agentId || undefined,
        });
        ElMessage.success(response.msg || "已停止执行");
        await getRunList();
    } catch (error) {
        const msg =
            error?.response?.data?.msg || error?.message || "停止执行失败";
        ElMessage.error(msg);
    }
}

/**
 * 取消执行准备。
 * @param {Record<string, any>} row 执行记录
 * @returns {Promise<void>} 取消任务
 */
async function handleCancelPreparedRun(row) {
    const runId = normalizeIdValue(row?.webCaseRunId);
    if (!runId) return;
    try {
        await ElMessageBox.confirm(`确认取消执行准备【${runId}】吗？`, "提示", {
            type: "warning",
        });
    } catch {
        return;
    }
    try {
        const response = await cancelWebRun({
            webCaseRunId: runId,
            agentId: row?.agentId || undefined,
            reason: "已取消执行准备",
        });
        ElMessage.success(response.msg || "已取消执行准备");
        await getRunList();
    } catch (error) {
        const msg =
            error?.response?.data?.msg || error?.message || "取消执行准备失败";
        ElMessage.error(msg);
    }
}

/**
 * 删除执行记录。
 * @param {Record<string, any>|null} row 指定行
 * @returns {Promise<void>} 删除任务
 */
async function handleDeleteRecords(row = null) {
    const ids = collectRunRecordIds(row);
    if (!ids.length) {
        ElMessage.warning("请先选择要删除的执行记录");
        return;
    }
    try {
        await ElMessageBox.confirm(
            `确认删除 ${ids.length} 条执行记录吗？`,
            "提示",
            { type: "warning" },
        );
    } catch {
        return;
    }
    try {
        const response = await delWebRun(ids.join(","));
        ElMessage.success(response.msg || "删除成功");
        selectedRows.value = [];
        emit("deleted", ids);
        await getRunList();
    } catch (error) {
        const msg =
            error?.response?.data?.msg || error?.message || "删除执行记录失败";
        ElMessage.error(msg);
    }
}

/**
 * 处理表格勾选变更。
 * @param {Array} selection 当前选中项
 * @returns {void}
 */
function handleSelectionChange(selection) {
    selectedRows.value = Array.isArray(selection) ? selection : [];
}

/**
 * 打开执行详情。
 * @param {Record<string, any>} row 执行记录
 * @returns {void}
 */
function openRunDetail(row) {
    emit("open-detail", row);
}

/**
 * 供父组件直接查询记录。
 * @param {string|number} runId 执行记录 ID
 * @returns {Record<string, any>|null} 命中的执行记录
 */
function findRunById(runId) {
    return (
        dataList.value.find((item) =>
            normalizeIdValue(item?.webCaseRunId) === normalizeIdValue(runId),
        ) || null
    );
}

defineExpose({
    getRunList,
    resetRunQuery,
    openHistoryByCase,
    findRunById,
    searchCaseOptions,
    handleStopRun,
    handleCancelPreparedRun,
    handleDeleteRecords,
});
</script>

<style scoped lang="scss">
.run-tab-content {
    width: 100%;
}

.pager {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
}
</style>
