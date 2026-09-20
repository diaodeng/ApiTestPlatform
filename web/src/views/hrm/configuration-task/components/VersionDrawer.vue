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
            <el-dialog
                v-model="editorVisible"
                :title="`编辑版本 v${editing?.versionNo || ''}`"
                width="72%"
                top="5vh"
                destroy-on-close
            >
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
                                    <el-option
                                        v-for="item in browserOptions"
                                        :key="item.value"
                                        :label="item.label"
                                        :value="item.value"
                                    />
                                </el-select>
                            </el-form-item>
                        </el-col>
                        <el-col :span="6">
                            <el-form-item label="无头模式">
                                <el-switch v-model="editorForm.headless" />
                            </el-form-item>
                        </el-col>
                    </el-row>
                    <el-form-item label="凭证绑定">
                        <el-select
                            v-model="editorForm.credentialBindingId"
                            placeholder="统一凭证的浏览器状态绑定，可留空"
                            clearable
                            filterable
                            style="width: 100%"
                        >
                            <el-option
                                v-for="item in credentialOptions"
                                :key="item.bindingId"
                                :label="`${item.bindingName}（${item.credentialName || '-'}）`"
                                :value="item.bindingId"
                            />
                        </el-select>
                    </el-form-item>
                    <el-form-item label="步骤">
                        <el-tabs v-model="stepsEditorTab" type="card" class="steps-editor-tabs">
                            <!-- 可视化模式：复用 Web 用例的 StepDetail 编辑能力（自包含组件） -->
                            <el-tab-pane label="可视化编辑" name="visual">
                                <VersionStepTable :steps="editorSteps" @change="syncStepsToJson" />
                            </el-tab-pane>
                            <el-tab-pane label="JSON" name="json">
                                <el-input
                                    v-model="stepsText"
                                    type="textarea"
                                    :rows="14"
                                    placeholder="Web 步骤数组 JSON"
                                />
                            </el-tab-pane>
                        </el-tabs>
                    </el-form-item>
                    <el-form-item>
                        <template #label>
                            <span class="form-label-with-help">
                                输入绑定
                                <PromptButton
                                    title="输入绑定怎么填写"
                                    width="470"
                                    placement="top-start"
                                    class="field-help"
                                >
                                    <div>用于给步骤中的 <code>upload_file</code> 动作提供文件资源。JSON 键必须与步骤参数中的 <code>fileKey</code> 完全一致。</div>
                                    <div>值是资源 ID 字符串数组，例如 <code>{"price_tag": ["900000000000001"]}</code>。每个 fileKey 最多绑定 20 个资源，不能填写 Agent 本地绝对路径。</div>
                                    <div>资源必须已上传、状态为 READY，且属于任务执行 Agent；保存后发布版本时服务端会再次校验。</div>
                                </PromptButton>
                            </span>
                        </template>
                        <el-input
                            v-model="bindingsText"
                            type="textarea"
                            :rows="4"
                            placeholder='fileKey 到资源ID数组，如 {"price_tag": ["900000000000001"]}'
                        />
                    </el-form-item>
                    <el-form-item>
                        <template #label>
                            <span class="form-label-with-help">
                                版本变量
                                <PromptButton
                                    title="版本变量怎么使用"
                                    width="470"
                                    placement="top-start"
                                    class="field-help"
                                >
                                    <div>用于本版本运行时的变量值。步骤中的 <code>${store.id}</code> 或 <code>&#123;&#123;store.id&#125;&#125;</code> 会从运行变量中查找对应名称。</div>
                                    <div>任务变量先作为基础值，版本变量后合并；同名顶层变量以版本变量为准，适合保存本版本专用值或覆盖任务默认值。</div>
                                    <div>当前建议使用扁平键名，例如 <code>{"store.id": "2625868"}</code>，以确保与占位符名称直接匹配。已发布版本不可直接修改，修改变量请创建新草稿并重新发布。</div>
                                </PromptButton>
                            </span>
                        </template>
                        <el-input v-model="versionVariablesText" type="textarea" :rows="3" placeholder='JSON 对象，例如 {"store.id": "2625868"}' />
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
import VersionStepTable from "./VersionStepTable.vue";
import PromptButton from "@/components/PromptButton/index.vue";
import { browserOptions } from "@/components/hrm/case/webcase/utils/shared.js";
import { listWebCredentialOptions } from "../composables/recordingOptions.js";
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
// 凭证绑定选项：统一凭证的 web_case + playwright_storage 投影，弹窗打开时加载。
const credentialOptions = ref([]);
const editorVisible = ref(false);
const stageVisible = ref(false);
const stageVersion = ref(null);
const editing = ref(null);
const editorForm = reactive({ startUrl: "", browserName: "chromium", headless: false, credentialBindingId: "" });
const stepsText = ref("[]");
const bindingsText = ref("{}");
const versionVariablesText = ref("{}");
// 步骤编辑双模式：可视化表格直接操作 editorSteps 数组，JSON 模式编辑文本；
// 切换/保存时以对方为源同步，保证两种模式不丢数据。
const stepsEditorTab = ref("visual");
const editorSteps = ref([]);

// 可视化表格变更后同步回 JSON 文本，保持两视图一致。
function syncStepsToJson() {
    stepsText.value = JSON.stringify(editorSteps.value, null, 2);
}

// 从 JSON 文本刷新可视化表格；解析失败返回 false 并提示。
function syncStepsFromJson() {
    try {
        const parsed = JSON.parse(stepsText.value || "[]");
        if (!Array.isArray(parsed)) {
            ElMessage.warning("步骤必须是合法 JSON 数组");
            return false;
        }
        editorSteps.value = parsed;
        return true;
    } catch {
        ElMessage.warning("步骤必须是合法 JSON 数组");
        return false;
    }
}

watch(
    () => [props.modelValue, props.task?.taskId],
    ([visible]) => {
        if (visible && props.task) {
            loadVersions();
            listWebCredentialOptions()
                .then((rows) => (credentialOptions.value = rows))
                .catch(() => (credentialOptions.value = []));
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
    // 可视化表格用独立数组持有步骤（元素引用与 JSON 文本同步）。
    editorSteps.value = Array.isArray(row.steps) ? [...row.steps] : [];
    stepsEditorTab.value = "visual";
    bindingsText.value = JSON.stringify(row.inputBindings || {}, null, 2);
    versionVariablesText.value = JSON.stringify(row.variables || {}, null, 2);
    editorVisible.value = true;
}

async function saveVersion() {
    if (!editing.value) return;
    // 保存时以当前激活的编辑视图为准：可视化 Tab 先同步到 JSON，JSON Tab 先解析刷新表格。
    if (stepsEditorTab.value === "visual") {
        syncStepsToJson();
    } else if (!syncStepsFromJson()) {
        return;
    }
    let bindings, variables;
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
            // clearable 清空后为空串，后端 normalize 为空即"未绑定凭证"。
            credentialBindingId: editorForm.credentialBindingId || "",
            steps: editorSteps.value,
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
.form-label-with-help {
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.field-help {
    vertical-align: middle;
}


.toolbar {
    display: flex;
    gap: 8px;
}
.steps-editor-tabs {
    width: 100%;

    :deep(.el-tabs__content) {
        max-height: 480px;
        overflow: auto;
    }
}
</style>
