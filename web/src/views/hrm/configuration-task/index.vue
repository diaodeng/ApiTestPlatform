<template>
    <div class="app-container config-task-page">
        <el-tabs v-model="activeTab" class="config-task-tabs">
            <el-tab-pane label="任务管理" name="tasks">
                <TaskTab
                    ref="taskTabRef"
                    @open-versions="openVersionDialog"
                    @open-run="openRunDialog"
                    @open-schedule="openScheduleDialog"
                    @open-convert="openConvertDialog"
                />
            </el-tab-pane>
            <el-tab-pane label="运行记录" name="runs">
                <RunRecordTab ref="runTabRef" @open-detail="openRunDetailDialog" />
            </el-tab-pane>
        </el-tabs>

        <!-- 版本管理抽屉 -->
        <VersionDrawer
            v-model="versionDrawerVisible"
            :task="currentTask"
            @published="refreshTasks"
        />

        <!-- 运行确认弹窗 -->
        <RunConfirmDialog
            v-model="runDialogVisible"
            :task="currentTask"
            @started="handleRunStarted"
        />

        <!-- 定时配置弹窗 -->
        <ScheduleDialog
            v-model="scheduleDialogVisible"
            :task="currentTask"
            @saved="refreshTasks"
        />

        <!-- 录制转模板弹窗 -->
        <ConvertDialog
            v-model="convertDialogVisible"
            :task="currentTask"
            @converted="handleConverted"
        />

        <!-- 运行详情抽屉 -->
        <RunDetailDrawer
            v-model="runDetailVisible"
            :task-run-id="currentRunId"
        />
    </div>
</template>

<script setup name="ConfigurationTask">
import { ref } from "vue";
import TaskTab from "./components/TaskTab.vue";
import RunRecordTab from "./components/RunRecordTab.vue";
import VersionDrawer from "./components/VersionDrawer.vue";
import RunConfirmDialog from "./components/RunConfirmDialog.vue";
import ScheduleDialog from "./components/ScheduleDialog.vue";
import ConvertDialog from "./components/ConvertDialog.vue";
import RunDetailDrawer from "./components/RunDetailDrawer.vue";

const activeTab = ref("tasks");
const taskTabRef = ref();
const runTabRef = ref();

const versionDrawerVisible = ref(false);
const runDialogVisible = ref(false);
const scheduleDialogVisible = ref(false);
const convertDialogVisible = ref(false);
const runDetailVisible = ref(false);
const currentTask = ref(null);
const currentRunId = ref("");

function openVersionDialog(task) {
    currentTask.value = task;
    versionDrawerVisible.value = true;
}

function openRunDialog(task) {
    currentTask.value = task;
    runDialogVisible.value = true;
}

function openScheduleDialog(task) {
    currentTask.value = task;
    scheduleDialogVisible.value = true;
}

function openConvertDialog(task) {
    currentTask.value = task;
    convertDialogVisible.value = true;
}

function openRunDetailDialog(run) {
    currentRunId.value = run.taskRunId;
    runDetailVisible.value = true;
}

function refreshTasks() {
    taskTabRef.value?.getList?.();
}

function handleRunStarted() {
    runDialogVisible.value = false;
    activeTab.value = "runs";
    runTabRef.value?.getList?.();
}

function handleConverted() {
    convertDialogVisible.value = false;
    const task = currentTask.value;
    if (task) {
        openVersionDialog(task);
    }
}
</script>

<style lang="scss" scoped>
.config-task-tabs {
    :deep(.el-tabs__content) {
        overflow: visible;
    }
}
</style>
