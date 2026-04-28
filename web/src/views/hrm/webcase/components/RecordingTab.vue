<template>
    <div class="recording-tab-content">
        <el-form :inline="true" :model="queryParams" class="mb8">
            <el-form-item label="录制名称">
                <el-input
                    v-model="queryParams.sessionName"
                    placeholder="请输入录制名称"
                    clearable
                    @keyup.enter="getRecordingList"
                />
            </el-form-item>
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
            <el-form-item label="录制状态">
                <el-select
                    v-model="queryParams.status"
                    clearable
                    placeholder="全部状态"
                    style="width: 160px"
                >
                    <el-option
                        v-for="item in recordingStatusOptions"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                    />
                </el-select>
            </el-form-item>
            <el-form-item>
                <el-button type="primary" icon="Search" @click="getRecordingList"
                    >搜索</el-button
                >
                <el-button icon="Refresh" @click="resetRecordingQuery"
                    >重置</el-button
                >
            </el-form-item>
        </el-form>

        <el-row :gutter="10" class="mb8">
            <el-col :span="1.5">
                <el-button
                    type="warning"
                    plain
                    icon="VideoPlay"
                    @click="openRecordingDialog()"
                    v-hasPermi="['hrm:webCase:record']"
                    >新建录制</el-button
                >
            </el-col>
            <el-col :span="1.5">
                <el-button
                    type="default"
                    plain
                    icon="Refresh"
                    @click="getRecordingList"
                    >刷新</el-button
                >
            </el-col>
            <el-col :span="1.5">
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
            max-height="calc(100vh - 360px)"
            row-key="recordingId"
            @selection-change="handleSelectionChange"
        >
            <el-table-column
                type="selection"
                width="52"
                align="center"
                :reserve-selection="true"
            />
            <el-table-column label="录制ID" prop="recordingId" width="170" />
            <el-table-column
                label="录制名称"
                prop="sessionName"
                min-width="220"
            />
            <el-table-column label="所属用例" min-width="220">
                <template #default="scope">{{
                    getCaseName(scope.row.webCaseId) ||
                    scope.row.webCaseId ||
                    "独立录制"
                }}</template>
            </el-table-column>
            <el-table-column
                label="Agent"
                prop="agentCode"
                min-width="150"
                show-overflow-tooltip
            />
            <el-table-column label="浏览器" width="120">
                <template #default="scope"
                    >{{ scope.row.browserName
                    }}{{ scope.row.headless ? " / 无头" : "" }}</template
                >
            </el-table-column>
            <el-table-column label="状态" width="110">
                <template #default="scope">
                    <el-tag :type="getRecordingStatusMeta(scope.row.status).type"
                        >{{
                            getRecordingStatusMeta(scope.row.status).label
                        }}</el-tag
                    >
                </template>
            </el-table-column>
            <el-table-column label="开始时间" min-width="170">
                <template #default="scope">{{
                    formatTime(scope.row.startedAt)
                }}</template>
            </el-table-column>
            <el-table-column label="最近事件" min-width="170">
                <template #default="scope">{{
                    formatTime(scope.row.lastEventAt)
                }}</template>
            </el-table-column>
            <el-table-column
                label="失败原因"
                min-width="220"
                show-overflow-tooltip
            >
                <template #default="scope">{{
                    scope.row.errorMessage || "-"
                }}</template>
            </el-table-column>
            <el-table-column label="操作" width="330" fixed="right">
                <template #default="scope">
                    <el-button
                        link
                        type="primary"
                        icon="View"
                        @click="openRecordingDetail(scope.row)"
                        >查看</el-button
                    >
                    <el-button
                        v-if="canStopRecording(scope.row)"
                        link
                        type="warning"
                        icon="VideoPause"
                        @click="handleStopRecording(scope.row)"
                        v-hasPermi="['hrm:webCase:record']"
                    >
                        停止
                    </el-button>
                    <el-button
                        v-if="canCancelPreparedRecording(scope.row)"
                        link
                        type="warning"
                        icon="CircleClose"
                        @click="handleCancelPreparedRecording(scope.row)"
                        v-hasPermi="['hrm:webCase:record']"
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
                    <el-button
                        link
                        type="success"
                        icon="VideoPlay"
                        :disabled="!canUseRecordingResult(scope.row.status)"
                        @click="openReplayDialog(scope.row)"
                        v-hasPermi="['hrm:webCase:run']"
                        >回放</el-button
                    >
                    <el-button
                        link
                        type="warning"
                        icon="Plus"
                        :disabled="!canUseRecordingResult(scope.row.status)"
                        @click="
                            openRecordingActionDialog('create', scope.row)
                        "
                        v-hasPermi="['hrm:webCase:add']"
                        >保存新用例</el-button
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
                @size-change="getRecordingList"
                @current-change="getRecordingList"
            />
        </div>
    </div>
</template>

<script setup>
import { getCurrentInstance, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
    cancelWebRecording,
    delWebRecording,
    listWebCase,
    listWebRecording,
    stopWebRecording,
} from "@/api/hrm/web_case.js";
import {
    extractRows,
    mergeCaseOptions,
    normalizeIdValue,
    recordingStatusOptions,
} from "../utils/shared.js";

/**
 * RecordingTab 组件事件定义。
 * @property {(rows: Array) => void} sync-case-options 同步父组件可复用的用例选项
 * @property {() => void} open-recording-dialog 打开新建录制弹窗
 * @property {(row: object) => void} open-detail 打开录制详情弹窗
 * @property {(row: object) => void} open-replay 打开回放弹窗
 * @property {(mode: string, row: object) => void} open-action 打开录制结果保存弹窗
 * @property {(ids: Array<string>) => void} deleted 删除记录后通知父组件清理详情状态
 */
const emit = defineEmits([
    "sync-case-options",
    "open-recording-dialog",
    "open-detail",
    "open-replay",
    "open-action",
    "deleted",
]);

const { proxy } = getCurrentInstance();

const loading = ref(false);
const total = ref(0);
const dataList = ref([]);
const selectedRows = ref([]);
const queryParams = ref({
    pageNum: 1,
    pageSize: 10,
    sessionName: undefined,
    webCaseId: undefined,
    status: undefined,
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
 * 获取录制状态标签配置。
 * @param {number|string} status 状态值
 * @returns {{label: string, type: string}} 状态配置
 */
function getRecordingStatusMeta(status) {
    return (
        recordingStatusOptions.find((item) => item.value === status) || {
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
 * 判断录制结果是否可回放或保存。
 * @param {number|string} status 录制状态
 * @returns {boolean} 是否可用
 */
function canUseRecordingResult(status) {
    return [3, 4, 5].includes(Number(status));
}

/**
 * 判断录制是否等待手动确认。
 * @param {Record<string, any>} row 录制记录
 * @returns {boolean} 是否等待确认
 */
function isRecordingWaitingManualConfirm(row) {
    const payload = row?.result || {};
    if (payload.awaitingManualConfirm === true) return true;

    const runtimeDebug = payload.runtimeDebug || null;
    const manualGate = runtimeDebug?.manualLoginGate || null;
    if (manualGate && manualGate.waitingConfirm === true) return true;

    const statusText = `${payload.status || ""}`.trim().toLowerCase();
    return statusText === "waiting_manual_login";
}

/**
 * 判断是否允许停止录制。
 * @param {Record<string, any>} row 录制记录
 * @returns {boolean} 是否允许停止
 */
function canStopRecording(row) {
    return Number(row?.status) === 2 && !isRecordingWaitingManualConfirm(row);
}

/**
 * 判断是否允许取消录制准备。
 * @param {Record<string, any>} row 录制记录
 * @returns {boolean} 是否允许取消准备
 */
function canCancelPreparedRecording(row) {
    return Number(row?.status) === 2 && isRecordingWaitingManualConfirm(row);
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
 * 获取录制记录列表。
 * @returns {Promise<void>} 列表加载任务
 */
function getRecordingList() {
    loading.value = true;
    return listWebRecording(queryParams.value)
        .then((response) => {
            dataList.value = response.rows || [];
            total.value = response.total || 0;
            const merged = mergeCaseOptions(
                caseSelectOptions.value,
                dataList.value,
            );
            caseSelectOptions.value = merged;
            emit("sync-case-options", merged);
        })
        .finally(() => {
            loading.value = false;
        });
}

/**
 * 重置录制记录查询条件并刷新列表。
 * @returns {Promise<void>} 列表加载任务
 */
function resetRecordingQuery() {
    queryParams.value = {
        pageNum: 1,
        pageSize: 10,
        sessionName: undefined,
        webCaseId: undefined,
        status: undefined,
    };
    selectedRows.value = [];
    return getRecordingList();
}

/**
 * 收集要删除的录制记录 ID。
 * @param {Record<string, any>|null} row 指定行
 * @returns {Array<string>} 录制记录 ID 列表
 */
function collectRecordingIds(row) {
    if (row?.recordingId) {
        return [normalizeIdValue(row.recordingId)].filter(Boolean);
    }
    const ids = selectedRows.value
        .map((item) => normalizeIdValue(item?.recordingId))
        .filter(Boolean);
    return Array.from(new Set(ids));
}

/**
 * 停止录制。
 * @param {Record<string, any>} row 录制记录
 * @returns {Promise<void>} 停止任务
 */
async function handleStopRecording(row) {
    const recordingId = normalizeIdValue(row?.recordingId);
    if (!recordingId) return;
    try {
        await ElMessageBox.confirm(
            `确认停止录制【${recordingId}】吗？`,
            "提示",
            { type: "warning" },
        );
    } catch {
        return;
    }
    try {
        const response = await stopWebRecording({
            recordingId,
            agentId: row?.agentId || undefined,
            closeBrowserOnStop: true,
        });
        ElMessage.success(response.msg || "已发送停止录制指令");
        await getRecordingList();
    } catch (error) {
        const msg =
            error?.response?.data?.msg || error?.message || "停止录制失败";
        ElMessage.error(msg);
    }
}

/**
 * 取消录制准备。
 * @param {Record<string, any>} row 录制记录
 * @returns {Promise<void>} 取消任务
 */
async function handleCancelPreparedRecording(row) {
    const recordingId = normalizeIdValue(row?.recordingId);
    if (!recordingId) return;
    try {
        await ElMessageBox.confirm(
            `确认取消录制准备【${recordingId}】吗？`,
            "提示",
            { type: "warning" },
        );
    } catch {
        return;
    }
    try {
        const response = await cancelWebRecording({
            recordingId,
            agentId: row?.agentId || undefined,
            reason: "已取消录制准备",
        });
        ElMessage.success(response.msg || "已取消录制准备");
        await getRecordingList();
    } catch (error) {
        const msg =
            error?.response?.data?.msg || error?.message || "取消录制准备失败";
        ElMessage.error(msg);
    }
}

/**
 * 删除录制记录。
 * @param {Record<string, any>|null} row 指定行
 * @returns {Promise<void>} 删除任务
 */
async function handleDeleteRecords(row = null) {
    const ids = collectRecordingIds(row);
    if (!ids.length) {
        ElMessage.warning("请先选择要删除的录制记录");
        return;
    }
    try {
        await ElMessageBox.confirm(
            `确认删除 ${ids.length} 条录制记录吗？`,
            "提示",
            { type: "warning" },
        );
    } catch {
        return;
    }
    try {
        const response = await delWebRecording(ids.join(","));
        ElMessage.success(response.msg || "删除成功");
        selectedRows.value = [];
        emit("deleted", ids);
        await getRecordingList();
    } catch (error) {
        const msg =
            error?.response?.data?.msg || error?.message || "删除录制记录失败";
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
 * 打开新建录制弹窗。
 * @returns {void}
 */
function openRecordingDialog() {
    emit("open-recording-dialog");
}

/**
 * 打开录制详情。
 * @param {Record<string, any>} row 录制记录
 * @returns {void}
 */
function openRecordingDetail(row) {
    emit("open-detail", row);
}

/**
 * 打开回放弹窗。
 * @param {Record<string, any>} row 录制记录
 * @returns {void}
 */
function openReplayDialog(row) {
    emit("open-replay", row);
}

/**
 * 打开录制结果操作弹窗。
 * @param {string} mode 操作模式
 * @param {Record<string, any>} recording 录制记录
 * @returns {void}
 */
function openRecordingActionDialog(mode, recording) {
    emit("open-action", mode, recording);
}

/**
 * 供父组件直接查询记录。
 * @param {string|number} recordingId 录制记录 ID
 * @returns {Record<string, any>|null} 命中的录制记录
 */
function findRecordingById(recordingId) {
    return (
        dataList.value.find(
            (item) =>
                normalizeIdValue(item?.recordingId) ===
                normalizeIdValue(recordingId),
        ) || null
    );
}

defineExpose({
    getRecordingList,
    resetRecordingQuery,
    findRecordingById,
    searchCaseOptions,
    handleStopRecording,
    handleCancelPreparedRecording,
    handleDeleteRecords,
});
</script>

<style scoped lang="scss">
.recording-tab-content {
    width: 100%;
}

.pager {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
}
</style>
