<template>
    <div class="task-tab-content">
        <el-form :inline="true" class="mb8">
            <el-form-item label="任务名称">
                <el-input
                    v-model="keyword"
                    placeholder="请输入任务名称"
                    clearable
                    style="width: 200px"
                    @keyup.enter="getList"
                />
            </el-form-item>
            <el-form-item>
                <el-button type="primary" icon="Search" @click="getList">查询</el-button>
                <el-button type="primary" icon="Plus" @click="openCreateDialog">新增任务</el-button>
                <el-button type="warning" icon="VideoCamera" @click="$emit('open-recording')">新建录制</el-button>
            </el-form-item>
        </el-form>

        <el-table v-loading="loading" :data="taskList" border>
            <el-table-column label="任务名称" prop="taskName" min-width="160" show-overflow-tooltip />
            <el-table-column label="描述" prop="description" min-width="160" show-overflow-tooltip />
            <el-table-column label="执行Agent" prop="agentCode" width="140" show-overflow-tooltip />
            <el-table-column label="当前版本" width="100">
                <template #default="{ row }">
                    <el-tag v-if="row.currentVersionNo" type="success">v{{ row.currentVersionNo }}</el-tag>
                    <el-tag v-else type="info">未发布</el-tag>
                </template>
            </el-table-column>
            <el-table-column label="状态" prop="status" width="90">
                <template #default="{ row }">
                    <el-tag :type="row.status === 'ACTIVE' ? 'success' : 'danger'">
                        {{ row.status === 'ACTIVE' ? '启用' : '停用' }}
                    </el-tag>
                </template>
            </el-table-column>
            <el-table-column label="更新时间" prop="updateTime" width="160" />
            <el-table-column label="操作" width="330" fixed="right">
                <template #default="{ row }">
                    <el-button link type="primary" icon="Edit" @click="openEditDialog(row)">编辑</el-button>
                    <el-button link type="primary" icon="Files" @click="$emit('open-versions', row)">版本</el-button>
                    <el-button link type="success" icon="VideoPlay" @click="$emit('open-run', row)">运行</el-button>
                    <el-button link type="warning" icon="Timer" @click="$emit('open-schedule', row)">定时</el-button>
                    <el-button link type="info" icon="MagicStick" @click="$emit('open-convert', row)">录制转模板</el-button>
                </template>
            </el-table-column>
        </el-table>

        <!-- 新增/编辑任务 -->
        <el-dialog v-model="editVisible" :title="editForm.taskId ? '编辑任务' : '新增任务'" width="560px">
            <el-form :model="editForm" label-width="100px">
                <el-form-item label="任务名称" required>
                    <el-input v-model="editForm.taskName" maxlength="128" />
                </el-form-item>
                <el-form-item label="描述">
                    <el-input v-model="editForm.description" type="textarea" :rows="2" maxlength="500" />
                </el-form-item>
                <el-form-item label="执行Agent" required>
                    <el-select
                        v-model="editForm.agentCode"
                        placeholder="请选择执行 Agent"
                        filterable
                        :loading="agentsLoading"
                        style="width: 100%"
                    >
                        <el-option
                            v-for="item in agentOptions"
                            :key="item.agentCode"
                            :label="`${item.agentName || item.agentCode} [${item.agentCode}]`"
                            :value="item.agentCode"
                        >
                            <span>{{ item.agentName || item.agentCode }} [{{ item.agentCode }}]</span>
                            <span class="agent-status" :class="item.status === 2 ? 'is-online' : 'is-offline'">
                                {{ item.status === 2 ? "在线" : "离线" }}
                            </span>
                        </el-option>
                    </el-select>
                </el-form-item>
                <el-form-item label="业务变量">
                    <el-input
                        v-model="variablesText"
                        type="textarea"
                        :rows="4"
                        placeholder='JSON 对象，如 {"store": {"id": "2625868"}}'
                    />
                </el-form-item>
                <el-form-item label="状态" v-if="editForm.taskId">
                    <el-radio-group v-model="editForm.status">
                        <el-radio value="ACTIVE">启用</el-radio>
                        <el-radio value="DISABLED">停用</el-radio>
                    </el-radio-group>
                </el-form-item>
                <el-form-item label="备注">
                    <el-input v-model="editForm.remark" type="textarea" :rows="2" maxlength="2000" />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="editVisible = false">取消</el-button>
                <el-button type="primary" :loading="saving" @click="saveTask">保存</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup name="ConfigTaskTab">
import { ref, reactive, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { listTasks, addTask, updateTask } from "@/api/hrm/configuration_task";
import { useAgentOptions } from "../composables/useAgentOptions";

defineEmits(["open-versions", "open-run", "open-schedule", "open-convert", "open-recording"]);

const loading = ref(false);
const keyword = ref("");
const taskList = ref([]);
const editVisible = ref(false);
const saving = ref(false);
const variablesText = ref("{}");
const editForm = reactive({ taskId: "", taskName: "", description: "", agentCode: "", status: "ACTIVE", remark: "" });
const { agentOptions, ensureAgentOptions, agentsLoading } = useAgentOptions();

onMounted(() => {
    getList();
    ensureAgentOptions().catch((e) => ElMessage.error(e.message || "Agent 列表查询失败"));
});

async function getList() {
    loading.value = true;
    try {
        const res = await listTasks({ keyword: keyword.value, limit: 100 });
        taskList.value = res.data || [];
    } catch (e) {
        ElMessage.error(e.message || "任务列表查询失败");
    } finally {
        loading.value = false;
    }
}

function openCreateDialog() {
    Object.assign(editForm, { taskId: "", taskName: "", description: "", agentCode: "", status: "ACTIVE", remark: "" });
    variablesText.value = "{}";
    editVisible.value = true;
}

function openEditDialog(row) {
    Object.assign(editForm, {
        taskId: row.taskId,
        taskName: row.taskName,
        description: row.description,
        agentCode: row.agentCode,
        status: row.status,
        remark: row.remark
    });
    variablesText.value = JSON.stringify(row.variables || {}, null, 2);
    editVisible.value = true;
}

async function saveTask() {
    if (!editForm.taskName || !editForm.agentCode) {
        ElMessage.warning("任务名称与执行 Agent 不能为空");
        return;
    }
    let variables = {};
    try {
        variables = JSON.parse(variablesText.value || "{}");
    } catch (e) {
        ElMessage.warning("业务变量必须是合法 JSON 对象");
        return;
    }
    saving.value = true;
    try {
        if (editForm.taskId) {
            await updateTask(editForm.taskId, { ...editForm, variables });
            ElMessage.success("任务更新成功");
        } else {
            await addTask({ ...editForm, variables });
            ElMessage.success("任务创建成功");
        }
        editVisible.value = false;
        getList();
    } catch (e) {
        ElMessage.error(e.message || "保存失败");
    } finally {
        saving.value = false;
    }
}

defineExpose({ getList });
</script>

<style lang="scss" scoped>
.agent-status {
    float: right;
    font-size: 12px;

    &.is-online {
        color: var(--el-color-success);
    }

    &.is-offline {
        color: var(--el-color-danger);
    }
}
</style>
