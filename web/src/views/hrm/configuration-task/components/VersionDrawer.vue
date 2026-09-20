<template>
    <el-drawer
        :model-value="modelValue"
        title="版本管理"
        size="70%"
        @update:model-value="$emit('update:modelValue', $event)"
    >
        <div v-if="task">
            <div class="toolbar mb8">
                <el-button type="primary" icon="Plus" @click="createDraft">新建草稿</el-button>
                <el-button icon="Refresh" @click="loadVersions">刷新</el-button>
            </div>

            <el-table v-loading="loading" :data="versions" border>
                <el-table-column label="版本号" width="90">
                    <template #default="{ row }">v{{ row.versionNo }}</template>
                </el-table-column>
                <el-table-column label="状态" width="110">
                    <template #default="{ row }">
                        <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="起始URL" prop="startUrl" min-width="200" show-overflow-tooltip />
                <el-table-column label="输入绑定" min-width="160">
                    <template #default="{ row }">
                        <span v-if="bindingSummary(row)">{{ bindingSummary(row) }}</span>
                        <span v-else class="text-muted">无</span>
                    </template>
                </el-table-column>
                <el-table-column label="发布人" prop="publishBy" width="100" />
                <el-table-column label="发布时间" prop="publishTime" width="160" />
                <el-table-column label="操作" width="260" fixed="right">
                    <template #default="{ row }">
                        <el-button link type="primary" icon="View" @click="openEditor(row)">编辑</el-button>
                        <el-button
                            link
                            type="success"
                            icon="Upload"
                            :disabled="row.status !== 'DRAFT'"
                            @click="publish(row)"
                        >发布</el-button>
                        <el-button link type="warning" icon="SetUp" @click="openStages(row)">阶段</el-button>
                    </template>
                </el-table-column>
            </el-table>

            <!-- 版本编辑器 -->
            <el-dialog v-model="editorVisible" :title="`编辑版本 v${editing?.versionNo || ''}`" width="72%" top="5vh">
                <el-form label-width="110px">
                    <el-row :gutter="16">
                        <el-col :span="12">
                            <el-form-item label="起始URL" required>
                                <el-input v-model="editorForm.startUrl" placeholder="https://..." />
                            </el-form-item>
                        </el-col>
                        <el-col :span="6">
                            <el-form-item label="浏览器">
                                <el-select v-model="editorForm.browserName">
                                    <el-option label="chromium" value="chromium" />
                                    <el-option label="firefox" value="firefox" />
                                    <el-option label="webkit" value="webkit" />
                                </el-select>
                            </el-form-item>
                        </el-col>
                        <el-col :span="6">
                            <el-form-item label="无头模式">
                                <el-switch v-model="editorForm.headless" />
                            </el-form-item>
                        </el-col>
                    </el-row>
                    <el-form-item label="凭证绑定ID">
                        <el-input v-model="editorForm.credentialBindingId" placeholder="统一凭证绑定ID（可选）" style="width: 300px" />
                    </el-form-item>
                    <el-form-item label="步骤JSON">
                        <el-input v-model="stepsText" type="textarea" :rows="14" placeholder="Web 步骤数组 JSON" />
                    </el-form-item>
                    <el-form-item label="输入绑定">
                        <el-input
                            v-model="bindingsText"
                            type="textarea"
                            :rows="4"
                            placeholder='fileKey 到资源ID数组，如 {"price_tag": ["900000000000001"]}'
                        />
                    </el-form-item>
                    <el-form-item label="版本变量">
                        <el-input v-model="versionVariablesText" type="textarea" :rows="3" placeholder="JSON 对象（可选）" />
                    </el-form-item>
                </el-form>
                <template #footer>
                    <el-button @click="editorVisible = false">取消</el-button>
                    <el-button type="primary" :loading="saving" @click="saveVersion">保存草稿</el-button>
                </template>
            </el-dialog>

            <!-- 阶段切分 -->
            <StageEditor v-model="stageVisible" :version="stageVersion" />
        </div>
        <el-empty v-else description="请选择任务" />
    </el-drawer>
</template>

<script setup name="ConfigVersionDrawer">
import { ref, reactive, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import StageEditor from "./StageEditor.vue";
import {
    listVersions,
    createVersion,
    updateVersion,
    publishVersion
} from "@/api/hrm/configuration_task";

const props = defineProps({ modelValue: Boolean, task: Object });
const emit = defineEmits(["update:modelValue", "published"]);

const loading = ref(false);
const saving = ref(false);
const versions = ref([]);
const editorVisible = ref(false);
const stageVisible = ref(false);
const stageVersion = ref(null);
const editing = ref(null);
const editorForm = reactive({ startUrl: "", browserName: "chromium", headless: false, credentialBindingId: "" });
const stepsText = ref("[]");
const bindingsText = ref("{}");
const versionVariablesText = ref("{}");

watch(
    () => [props.modelValue, props.task?.taskId],
    ([visible]) => {
        if (visible && props.task) {
            loadVersions();
        }
    },
    { immediate: true }
);

async function loadVersions() {
    if (!props.task) return;
    loading.value = true;
    try {
        const res = await listVersions(props.task.taskId);
        versions.value = res.data || [];
    } catch (e) {
        ElMessage.error(e.message || "版本列表查询失败");
    } finally {
        loading.value = false;
    }
}

async function createDraft() {
    try {
        await ElMessageBox.confirm("以空步骤创建新的版本草稿？", "新建草稿", { type: "info" });
    } catch {
        return;
    }
    try {
        await createVersion(props.task.taskId, {
            startUrl: "https://example.invalid/",
            browserName: "chromium",
            headless: true,
            steps: [],
            inputBindings: {}
        });
        ElMessage.success("草稿已创建，请编辑后发布");
        loadVersions();
    } catch (e) {
        ElMessage.error(e.message || "创建草稿失败");
    }
}

function bindingSummary(row) {
    const entries = Object.entries(row.inputBindings || {});
    if (!entries.length) return "";
    return entries.map(([key, ids]) => `${key}(${ids.length})`).join(", ");
}

function statusType(status) {
    return { DRAFT: "info", PUBLISHED: "success", DEPRECATED: "danger" }[status] || "info";
}

function statusLabel(status) {
    return { DRAFT: "草稿", PUBLISHED: "已发布", DEPRECATED: "已废弃" }[status] || status;
}

function openEditor(row) {
    editing.value = row;
    Object.assign(editorForm, {
        startUrl: row.startUrl,
        browserName: row.browserName,
        headless: row.headless,
        credentialBindingId: row.credentialBindingId
    });
    stepsText.value = JSON.stringify(row.steps || [], null, 2);
    bindingsText.value = JSON.stringify(row.inputBindings || {}, null, 2);
    versionVariablesText.value = JSON.stringify(row.variables || {}, null, 2);
    editorVisible.value = true;
}

async function saveVersion() {
    if (!editing.value) return;
    let steps, bindings, variables;
    try {
        steps = JSON.parse(stepsText.value || "[]");
    } catch {
        ElMessage.warning("步骤必须是合法 JSON 数组");
        return;
    }
    try {
        bindings = JSON.parse(bindingsText.value || "{}");
    } catch {
        ElMessage.warning("输入绑定必须是合法 JSON 对象");
        return;
    }
    try {
        variables = JSON.parse(versionVariablesText.value || "{}");
    } catch {
        ElMessage.warning("版本变量必须是合法 JSON 对象");
        return;
    }
    saving.value = true;
    try {
        await updateVersion(editing.value.versionId, {
            startUrl: editorForm.startUrl,
            browserName: editorForm.browserName,
            headless: editorForm.headless,
            credentialBindingId: editorForm.credentialBindingId,
            steps,
            inputBindings: bindings,
            variables
        });
        ElMessage.success("草稿已保存");
        editorVisible.value = false;
        loadVersions();
    } catch (e) {
        ElMessage.error(e.message || "保存失败");
    } finally {
        saving.value = false;
    }
}

async function publish(row) {
    try {
        await ElMessageBox.confirm(
            `发布 v${row.versionNo} 后不可修改，且将成为任务当前版本。确认发布？`,
            "发布版本",
            { type: "warning" }
        );
    } catch {
        return;
    }
    try {
        await publishVersion(row.versionId);
        ElMessage.success("版本发布成功");
        loadVersions();
        emit("published");
    } catch (e) {
        ElMessage.error(e.message || "发布失败");
    }
}

function openStages(row) {
    stageVersion.value = row;
    stageVisible.value = true;
}
</script>

<style lang="scss" scoped>
.text-muted {
    color: var(--el-text-color-secondary);
}
.toolbar {
    display: flex;
    gap: 8px;
}
</style>
