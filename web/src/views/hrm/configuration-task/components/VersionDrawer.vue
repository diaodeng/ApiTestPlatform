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
                <el-table-column label="操作" width="300" fixed="right">
                    <template #default="{ row }">
                        <el-button link type="primary" icon="View" @click="openEditor(row)">编辑</el-button>
                        <el-button
                            v-if="row.status === 'DRAFT'"
                            link
                            type="success"
                            icon="Upload"
                            @click="publish(row)"
                        >发布</el-button>
                        <el-button link type="primary" icon="CopyDocument" @click="copyVersionRow(row)">复制</el-button>
                        <el-button
                            v-if="row.status === 'PUBLISHED'"
                            link
                            type="warning"
                            icon="RefreshLeft"
                            @click="unpublish(row)"
                        >撤销发布</el-button>
                        <el-button
                            v-if="row.status === 'PUBLISHED'"
                            link
                            type="danger"
                            icon="CircleClose"
                            @click="deprecate(row)"
                        >废弃</el-button>
                        <el-button
                            v-if="row.status === 'DRAFT'"
                            link
                            type="danger"
                            icon="Delete"
                            @click="remove(row)"
                        >删除</el-button>
                        <el-button link type="warning" icon="SetUp" @click="openStages(row)">阶段</el-button>
                    </template>
                </el-table-column>
            </el-table>

            <!-- 版本编辑器：append-to-body 挂到 body，弹窗与遮罩覆盖整个窗口而非局限在抽屉内 -->
            <el-dialog
                v-model="editorVisible"
                :title="`编辑版本 v${editing?.versionNo || ''}`"
                width="72%"
                top="5vh"
                destroy-on-close
                append-to-body
                class="version-editor-dialog"
            >
                <el-alert
                    v-if="editing && editing.status !== 'DRAFT'"
                    title="当前版本已发布/已废弃，内容仅可查看且不能保存；如需修改请复制为新草稿后编辑"
                    type="info"
                    :closable="false"
                    class="mb8"
                />
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
                        <!-- 步骤编辑复用公共组件 WebStepEditor（可视化表格 + 高级 JSON + 步骤详情弹窗），
                             与用例管理共用同一交互与样式；版本步骤不落指纹，隐藏指纹字段。 -->
                        <WebStepEditor
                            ref="stepEditorRef"
                            :steps="editorSteps"
                            :show-fingerprint="false"
                            :table-max-height="null"
                            :upload-resource-agent-code="task?.agentCode || ''"
                        />
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
                    <el-button
                        type="primary"
                        :loading="saving"
                        :disabled="!editing || editing.status !== 'DRAFT'"
                        @click="saveVersion"
                    >保存草稿</el-button>
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
import WebStepEditor from "@/components/hrm/case/webcase/components/WebStepEditor.vue";
import PromptButton from "@/components/PromptButton/index.vue";
import { browserOptions } from "@/components/hrm/case/webcase/utils/shared.js";
import { listWebCredentialOptions } from "../composables/recordingOptions.js";
import {
    listVersions,
    createVersion,
    updateVersion,
    publishVersion,
    copyVersion,
    deleteVersion,
    deprecateVersion,
    unpublishVersion
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
const bindingsText = ref("{}");
const versionVariablesText = ref("{}");
// 步骤编辑交给公共组件 WebStepEditor：可视化表格与 JSON 双模式都在组件内部，
// 保存前调用其 flush() 应用 JSON 编辑，步骤数据始终以 editorSteps 数组为准。
const editorSteps = ref([]);
const stepEditorRef = ref(null);

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
    // 可视化表格用独立数组持有步骤（WebStepEditor 打开时自动初始化 JSON 文本与选中行）。
    editorSteps.value = Array.isArray(row.steps) ? [...row.steps] : [];
    bindingsText.value = JSON.stringify(row.inputBindings || {}, null, 2);
    versionVariablesText.value = JSON.stringify(row.variables || {}, null, 2);
    editorVisible.value = true;
}

async function saveVersion() {
    if (!editing.value) return;
    // 版本快照不可变原则：仅草稿可保存；已发布/已废弃版本弹窗只作查看。
    if (editing.value.status !== "DRAFT") {
        ElMessage.warning("仅草稿版本可编辑保存；如需修改请复制为新草稿");
        return;
    }
    // 保存前应用 JSON Tab 的编辑（不在 JSON Tab 时直接通过），失败则中止保存。
    if (!stepEditorRef.value?.flush()) {
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

// 复制任意版本为新草稿：步骤/绑定/变量/阶段切分一并复制，新版本号自动递增。
async function copyVersionRow(row) {
    try {
        const res = await copyVersion(row.versionId);
        ElMessage.success(res?.msg || `已复制为新草稿 v${row.versionNo}`);
        loadVersions();
    } catch (e) {
        ElMessage.error(e.message || "复制失败");
    }
}

// 删除草稿：仅草稿可删，后端校验无运行记录引用。
async function remove(row) {
    try {
        await ElMessageBox.confirm(
            `确定删除草稿 v${row.versionNo}？删除后不可恢复。`,
            "删除草稿",
            { type: "warning" }
        );
    } catch {
        return;
    }
    try {
        await deleteVersion(row.versionId);
        ElMessage.success("草稿已删除");
        loadVersions();
    } catch (e) {
        ElMessage.error(e.message || "删除失败");
    }
}

// 废弃已发布版本：下架不可再运行，历史运行保留追溯；当前版本指针自动回退。
async function deprecate(row) {
    try {
        await ElMessageBox.confirm(
            `废弃后 v${row.versionNo} 不可再发起运行，历史运行记录保留可追溯。确定废弃？`,
            "废弃版本",
            { type: "warning" }
        );
    } catch {
        return;
    }
    try {
        await deprecateVersion(row.versionId);
        ElMessage.success("版本已废弃");
        loadVersions();
    } catch (e) {
        ElMessage.error(e.message || "废弃失败");
    }
}

// 撤销发布：回退为草稿继续编辑；已有运行记录的版本会被后端拒绝（改用废弃+复制）。
async function unpublish(row) {
    try {
        await ElMessageBox.confirm(
            `撤销发布后 v${row.versionNo} 将回到草稿状态并可以继续编辑。确定撤销发布？`,
            "撤销发布",
            { type: "warning" }
        );
    } catch {
        return;
    }
    try {
        await unpublishVersion(row.versionId);
        ElMessage.success("已撤销发布，可继续编辑");
        loadVersions();
    } catch (e) {
        ElMessage.error(e.message || "撤销发布失败");
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
/* 步骤编辑区：公共组件 WebStepEditor 占满表单宽度。 */
:deep(.web-step-editor) {
    width: 100%;
}
</style>

<style lang="scss">
/* 版本编辑弹窗（append-to-body 后 scoped 样式无法命中）：
   dialog body 作为唯一的竖向滚动容器（footer 固定在外），滚动可达全部内容，
   避免与表格内部滚动条叠加出现两个竖向滚动条。 */
.version-editor-dialog .el-dialog__body {
    max-height: calc(100vh - 180px);
    overflow-y: auto;
}
</style>
