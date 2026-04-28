<template>
    <div class="case-tab-content">
        <el-form :inline="true" :model="queryParams" class="mb8">
            <el-form-item label="用例名称">
                <el-input
                    v-model="queryParams.caseName"
                    placeholder="请输入 Web 用例名称"
                    clearable
                    @keyup.enter="getList"
                />
            </el-form-item>
            <el-form-item label="项目">
                <el-select
                    v-model="queryParams.projectId"
                    clearable
                    filterable
                    placeholder="全部项目"
                    style="width: 180px"
                >
                    <el-option
                        v-for="item in projectOptions"
                        :key="item.projectId"
                        :label="item.projectName"
                        :value="item.projectId"
                    />
                </el-select>
            </el-form-item>
            <el-form-item label="模块">
                <el-select
                    v-model="queryParams.moduleId"
                    clearable
                    filterable
                    placeholder="全部模块"
                    style="width: 180px"
                >
                    <el-option
                        v-for="item in filteredSearchModules"
                        :key="item.moduleId"
                        :label="item.moduleName"
                        :value="item.moduleId"
                    />
                </el-select>
            </el-form-item>
            <el-form-item>
                <el-button type="primary" icon="Search" @click="getList"
                    >搜索</el-button
                >
                <el-button icon="Refresh" @click="resetQuery">重置</el-button>
            </el-form-item>
        </el-form>

        <el-row :gutter="10" class="mb8">
            <el-col :span="1.5">
                <el-button
                    type="primary"
                    plain
                    icon="Plus"
                    @click="handleAdd"
                    v-hasPermi="['hrm:webCase:add']"
                    >新增</el-button
                >
            </el-col>
            <el-col :span="1.5">
                <el-button
                    type="success"
                    plain
                    icon="CaretRight"
                    :disabled="!selectedRows.length"
                    @click="openBatchRunDialog"
                    v-hasPermi="['hrm:webCase:run']"
                >
                    批量执行
                </el-button>
            </el-col>
            <el-col :span="1.5">
                <el-button
                    type="warning"
                    plain
                    icon="VideoPlay"
                    @click="openRecordingDialog()"
                    v-hasPermi="['hrm:webCase:record']"
                    >独立录制</el-button
                >
            </el-col>
            <el-col :span="1.5">
                <el-button
                    type="default"
                    plain
                    icon="Refresh"
                    @click="getList"
                    >刷新</el-button
                >
            </el-col>
            <el-col :span="1.5">
                <el-button
                    type="info"
                    plain
                    icon="Setting"
                    @click="openRuntimeProfileDialog"
                    v-hasPermi="['hrm:webCase:edit']"
                    >Cookie配置</el-button
                >
            </el-col>
            <el-col :span="2">
                <el-button
                    type="info"
                    plain
                    icon="Lock"
                    @click="openBrowserSessionDialog"
                    v-hasPermi="['hrm:webCase:persistContext']"
                    >浏览器Session</el-button
                >
            </el-col>
        </el-row>

        <el-table
            v-loading="loading"
            :data="dataList"
            border
            table-layout="fixed"
            max-height="calc(100vh - 340px)"
            row-key="webCaseId"
            @selection-change="handleSelectionChange"
        >
            <el-table-column
                type="selection"
                width="52"
                align="center"
                :reserve-selection="true"
            />
            <el-table-column label="Web用例ID" prop="webCaseId" width="170" />
            <el-table-column label="用例名称" prop="caseName" min-width="220" />
            <el-table-column label="项目" min-width="140">
                <template #default="scope">{{
                    getProjectName(scope.row.projectId) ||
                    scope.row.projectId ||
                    "-"
                }}</template>
            </el-table-column>
            <el-table-column label="模块" min-width="140">
                <template #default="scope">{{
                    getModuleName(scope.row.moduleId) ||
                    scope.row.moduleId ||
                    "-"
                }}</template>
            </el-table-column>
            <el-table-column
                label="起始地址"
                prop="startUrl"
                min-width="220"
                show-overflow-tooltip
            />
            <el-table-column label="浏览器" prop="browserName" width="120" />
            <el-table-column label="无头" width="90">
                <template #default="scope">{{
                    scope.row.headless ? "是" : "否"
                }}</template>
            </el-table-column>
            <el-table-column label="更新时间" min-width="170">
                <template #default="scope">{{
                    formatTime(scope.row.updateTime || scope.row.createTime)
                }}</template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
                <template #default="scope">
                    <el-button
                        link
                        type="primary"
                        icon="Edit"
                        @click="handleEdit(scope.row)"
                        v-hasPermi="['hrm:webCase:edit']"
                        >编辑</el-button
                    >
                    <el-button
                        link
                        type="success"
                        icon="CaretRight"
                        @click="openRunDialog(scope.row)"
                        v-hasPermi="['hrm:webCase:run']"
                        >执行</el-button
                    >
                    <el-button
                        link
                        type="info"
                        icon="Histogram"
                        @click="openRunHistory(scope.row)"
                        v-hasPermi="['hrm:webCase:history']"
                        >记录</el-button
                    >
                    <el-button
                        link
                        type="danger"
                        icon="Delete"
                        @click="handleDelete(scope.row)"
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
                @size-change="getList"
                @current-change="getList"
            />
        </div>
    </div>
</template>

<script setup>
import { computed, getCurrentInstance, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { delWebCase, listWebCase } from "@/api/hrm/web_case.js";
import {
    isSameId,
    normalizeCaseOption,
    normalizeIdValue,
} from "../utils/shared.js";

/**
 * CaseTab 组件属性定义。
 * @property {Array} projectOptions 项目下拉选项
 * @property {Array} moduleOptions 模块下拉选项
 */
const props = defineProps({
    projectOptions: {
        type: Array,
        default: () => [],
    },
    moduleOptions: {
        type: Array,
        default: () => [],
    },
});

/**
 * CaseTab 组件事件定义。
 * @property {(rows: Array) => void} sync-case-options 同步父组件可复用的用例选项
 * @property {(row?: object) => void} add 打开新增用例弹窗
 * @property {(row: object) => void} edit 打开编辑用例弹窗
 * @property {(row: object) => void} open-run-dialog 打开执行弹窗
 * @property {(rows: Array) => void} open-batch-run-dialog 打开批量执行弹窗
 * @property {(row: object) => void} open-run-history 切换到执行记录并按用例筛选
 * @property {(row?: object) => void} open-recording-dialog 打开录制弹窗
 * @property {() => void} open-runtime-profile-dialog 打开 Cookie 配置弹窗
 * @property {() => void} open-browser-session-dialog 打开浏览器 Session 弹窗
 * @property {() => void} refresh-case-options 触发父组件刷新全量用例缓存
 */
const emit = defineEmits([
    "sync-case-options",
    "add",
    "edit",
    "open-run-dialog",
    "open-batch-run-dialog",
    "open-run-history",
    "open-recording-dialog",
    "open-runtime-profile-dialog",
    "open-browser-session-dialog",
    "refresh-case-options",
]);

const { proxy } = getCurrentInstance();

const loading = ref(false);
const total = ref(0);
const dataList = ref([]);
const selectedRows = ref([]);
const queryParams = ref({
    pageNum: 1,
    pageSize: 10,
    caseName: undefined,
    projectId: undefined,
    moduleId: undefined,
});

/**
 * 标准化主键值，统一字符串化比较。
 * @param {any} value 原始值
 * @returns {string|undefined} 标准化后的主键
 */
const filteredSearchModules = computed(() => {
    if (!queryParams.value.projectId) return props.moduleOptions;
    return props.moduleOptions.filter((item) =>
        isSameId(item.projectId, queryParams.value.projectId),
    );
});

watch(
    () => queryParams.value.projectId,
    () => {
        if (!queryParams.value.projectId) {
            return;
        }
        if (
            !filteredSearchModules.value.some((item) =>
                isSameId(item.moduleId, queryParams.value.moduleId),
            )
        ) {
            queryParams.value.moduleId = undefined;
        }
    },
);

/**
 * 格式化时间展示。
 * @param {string|number|Date} value 时间值
 * @returns {string} 格式化后的时间文本
 */
function formatTime(value) {
    return value ? proxy.parseTime(value) : "-";
}

/**
 * 根据项目 ID 获取项目名称。
 * @param {string|number} projectId 项目 ID
 * @returns {string} 项目名称
 */
function getProjectName(projectId) {
    if (!projectId) return "";
    return (
        props.projectOptions.find((item) =>
            isSameId(item.projectId, projectId),
        )?.projectName || ""
    );
}

/**
 * 根据模块 ID 获取模块名称。
 * @param {string|number} moduleId 模块 ID
 * @returns {string} 模块名称
 */
function getModuleName(moduleId) {
    if (!moduleId) return "";
    return (
        props.moduleOptions.find((item) => isSameId(item.moduleId, moduleId))
            ?.moduleName || ""
    );
}

/**
 * 获取用例管理列表。
 * @returns {Promise<void>} 列表加载任务
 */
function getList() {
    loading.value = true;
    return listWebCase(queryParams.value)
        .then((response) => {
            const rows = (response.rows || [])
                .map((item) => normalizeCaseOption(item) || item)
                .filter(Boolean);
            dataList.value = rows;
            total.value = response.total || 0;
            emit("sync-case-options", rows);
        })
        .finally(() => {
            loading.value = false;
        });
}

/**
 * 重置查询条件并刷新列表。
 * @returns {Promise<void>} 列表加载任务
 */
function resetQuery() {
    queryParams.value = {
        pageNum: 1,
        pageSize: 10,
        caseName: undefined,
        projectId: undefined,
        moduleId: undefined,
    };
    selectedRows.value = [];
    return getList();
}

/**
 * 处理表格勾选变更。
 * @param {Array} selection 当前选中行
 * @returns {void}
 */
function handleSelectionChange(selection) {
    selectedRows.value = Array.isArray(selection)
        ? selection.map((item) => normalizeCaseOption(item) || item)
        : [];
}

/**
 * 触发新增用例。
 * @returns {void}
 */
function handleAdd() {
    emit("add");
}

/**
 * 触发编辑用例。
 * @param {Record<string, any>} row 用例行数据
 * @returns {void}
 */
function handleEdit(row) {
    emit("edit", row);
}

/**
 * 删除单条用例并刷新列表。
 * @param {Record<string, any>} row 用例行数据
 * @returns {void}
 */
function handleDelete(row) {
    ElMessageBox.confirm(`是否确认删除 Web 用例【${row.caseName}】？`, "提示", {
        type: "warning",
    })
        .then(() => delWebCase(row.webCaseId))
        .then(async () => {
            ElMessage.success("删除成功");
            selectedRows.value = selectedRows.value.filter(
                (item) => !isSameId(item.webCaseId, row.webCaseId),
            );
            await getList();
            emit("refresh-case-options");
        })
        .catch(() => {});
}

/**
 * 打开单用例执行弹窗。
 * @param {Record<string, any>} row 用例行数据
 * @returns {void}
 */
function openRunDialog(row) {
    emit("open-run-dialog", row);
}

/**
 * 打开批量执行弹窗。
 * @returns {void}
 */
function openBatchRunDialog() {
    if (!selectedRows.value.length) {
        ElMessage.warning("请先勾选至少一条用例");
        return;
    }
    emit("open-batch-run-dialog", selectedRows.value);
}

/**
 * 跳转执行记录页并按用例筛选。
 * @param {Record<string, any>} row 用例行数据
 * @returns {void}
 */
function openRunHistory(row) {
    emit("open-run-history", row);
}

/**
 * 打开录制弹窗。
 * @returns {void}
 */
function openRecordingDialog() {
    emit("open-recording-dialog");
}

/**
 * 打开运行时配置弹窗。
 * @returns {void}
 */
function openRuntimeProfileDialog() {
    emit("open-runtime-profile-dialog");
}

/**
 * 打开浏览器 Session 弹窗。
 * @returns {void}
 */
function openBrowserSessionDialog() {
    emit("open-browser-session-dialog");
}

/**
 * 提供给父组件的用例 ID 查询接口。
 * @param {string|number} webCaseId 用例 ID
 * @returns {Record<string, any>|null} 命中的用例
 */
function findCaseById(webCaseId) {
    return (
        dataList.value.find((item) => isSameId(item.webCaseId, webCaseId)) ||
        null
    );
}

defineExpose({
    getList,
    resetQuery,
    findCaseById,
});

onMounted(() => {
    getList();
});
</script>

<style scoped lang="scss">
.case-tab-content {
    width: 100%;
}

.pager {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
}
</style>
