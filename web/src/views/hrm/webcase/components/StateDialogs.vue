<template>
        <el-dialog
            v-model="showRuntimeProfileDialog"
            title="Cookie配置管理"
            width="90%"
            destroy-on-close
            append-to-body
            :close-on-click-modal="false"
            :close-on-press-escape="false"
        >
            <el-row :gutter="16">
                <el-col :span="11">
                    <div class="runtime-profile-toolbar mb12">
                        <el-input
                            v-model="runtimeProfileKeyword"
                            clearable
                            placeholder="按名称筛选配置"
                        />
                        <el-button
                            type="primary"
                            @click="createRuntimeProfileDraft"
                            >新建</el-button
                        >
                        <el-button @click="loadRuntimeProfiles">刷新</el-button>
                    </div>
                    <el-table
                        v-loading="loading.runtimeProfile"
                        :data="filteredRuntimeProfiles"
                        border
                        row-key="profileId"
                        highlight-current-row
                        max-height="520px"
                        @current-change="handleRuntimeProfileRowChange"
                    >
                        <el-table-column
                            label="名称"
                            min-width="220"
                            show-overflow-tooltip
                        >
                            <template #default="scope">{{
                                scope.row.profileName || "-"
                            }}</template>
                        </el-table-column>
                        <el-table-column
                            label="适用范围"
                            min-width="150"
                            show-overflow-tooltip
                        >
                            <template #default="scope">{{
                                formatRuntimeProfileScope(scope.row)
                            }}</template>
                        </el-table-column>
                        <el-table-column
                            label="目标链路"
                            min-width="120"
                            show-overflow-tooltip
                        >
                            <template #default="scope">{{
                                (scope.row.targets || []).join(", ") || "-"
                            }}</template>
                        </el-table-column>
                        <el-table-column label="状态" width="90">
                            <template #default="scope">
                                <el-tag
                                    :type="
                                        scope.row.enabled === false
                                            ? 'info'
                                            : 'success'
                                    "
                                    >{{
                                        scope.row.enabled === false
                                            ? "停用"
                                            : "启用"
                                    }}</el-tag
                                >
                            </template>
                        </el-table-column>
                    </el-table>
                </el-col>
                <el-col :span="13">
                    <el-form :model="runtimeProfileForm" label-width="120px">
                        <el-row :gutter="12">
                            <el-col :span="12">
                                <el-form-item label="配置名称">
                                    <el-input
                                        v-model="runtimeProfileForm.profileName"
                                        placeholder="例如：生产登录态"
                                    />
                                </el-form-item>
                            </el-col>
                            <el-col :span="12">
                                <el-form-item label="是否启用">
                                    <el-switch
                                        v-model="runtimeProfileForm.enabled"
                                    />
                                </el-form-item>
                            </el-col>
                            <el-col :span="12">
                                <el-form-item label="目标链路">
                                    <el-select
                                        v-model="runtimeProfileForm.targets"
                                        multiple
                                        collapse-tags
                                        style="width: 100%"
                                    >
                                        <el-option
                                            v-for="item in runtimeTargetOptions"
                                            :key="item.value"
                                            :label="item.label"
                                            :value="item.value"
                                        />
                                    </el-select>
                                </el-form-item>
                            </el-col>
                            <el-col :span="12">
                                <el-form-item label="排序">
                                    <el-input-number
                                        v-model="runtimeProfileForm.sort"
                                        :min="0"
                                        :step="1"
                                        controls-position="right"
                                        style="width: 100%"
                                    />
                                </el-form-item>
                            </el-col>
                            <el-col :span="12">
                                <el-form-item label="项目(可选)">
                                    <el-select
                                        v-model="runtimeProfileForm.projectId"
                                        clearable
                                        filterable
                                        style="width: 100%"
                                    >
                                        <el-option
                                            v-for="item in projectOptions"
                                            :key="item.projectId"
                                            :label="item.projectName"
                                            :value="item.projectId"
                                        />
                                    </el-select>
                                </el-form-item>
                            </el-col>
                            <el-col :span="12">
                                <el-form-item label="模块(可选)">
                                    <el-select
                                        v-model="runtimeProfileForm.moduleId"
                                        clearable
                                        filterable
                                        style="width: 100%"
                                    >
                                        <el-option
                                            v-for="item in filteredRuntimeProfileModules"
                                            :key="item.moduleId"
                                            :label="item.moduleName"
                                            :value="item.moduleId"
                                        />
                                    </el-select>
                                </el-form-item>
                            </el-col>
                            <el-col :span="24">
                                <el-form-item label="运行覆盖(JSON)">
                                    <el-input
                                        v-model="
                                            runtimeProfileForm.runtimeOverridesText
                                        "
                                        type="textarea"
                                        :rows="3"
                                        placeholder='可选，例如：{"stepTimeoutMs":10000}'
                                    />
                                </el-form-item>
                            </el-col>
                            <el-col :span="24">
                                <el-form-item label="变量(JSON)">
                                    <el-input
                                        v-model="
                                            runtimeProfileForm.variablesText
                                        "
                                        type="textarea"
                                        :rows="3"
                                        placeholder='可选，例如：{"token":"xxx","sid":"yyy"}'
                                    />
                                </el-form-item>
                            </el-col>
                            <el-col :span="24">
                                <el-form-item label="Cookie规则(JSON)">
                                    <el-input
                                        v-model="
                                            runtimeProfileForm.cookieRulesText
                                        "
                                        type="textarea"
                                        :rows="5"
                                        placeholder='可选数组，例如：[{"name":"主站登录","match":{"host":"example.com"},"cookies":[{"name":"token","value":"${token}"}]}]'
                                    />
                                </el-form-item>
                            </el-col>
                            <el-col :span="24">
                                <el-form-item label="快速导入">
                                    <el-row :gutter="8" style="width: 100%">
                                        <el-col :span="14">
                                            <el-input
                                                v-model="
                                                    runtimeProfileImportHost
                                                "
                                                placeholder="可选：匹配域名，例如 example.com"
                                            />
                                        </el-col>
                                        <el-col :span="10">
                                            <el-button
                                                style="width: 100%"
                                                @click="
                                                    applyRuntimeProfileQuickImport
                                                "
                                                >解析并填充Cookie规则</el-button
                                            >
                                        </el-col>
                                        <el-col :span="24" class="mt8">
                                            <el-input
                                                v-model="
                                                    runtimeProfileImportText
                                                "
                                                type="textarea"
                                                :rows="4"
                                                placeholder="支持 Cookie: a=1; b=2、Set-Cookie 响应头，或完整请求头文本"
                                            />
                                        </el-col>
                                    </el-row>
                                </el-form-item>
                            </el-col>
                            <el-col :span="24">
                                <el-form-item label="状态作用域">
                                    <div style="width: 100%">
                                        <div
                                            class="runtime-profile-toolbar mb8"
                                        >
                                            <span class="step-detail-tip"
                                                >用于保留浏览器状态的作用域键，下拉可在执行/录制时直接选择。</span
                                            >
                                            <el-button
                                                type="primary"
                                                plain
                                                @click="
                                                    addPersistContextScopeRow
                                                "
                                                >新增作用域</el-button
                                            >
                                        </div>
                                        <el-table
                                            :data="
                                                runtimeProfileForm.persistContextScopes
                                            "
                                            border
                                            max-height="220px"
                                        >
                                            <el-table-column
                                                label="作用域Key"
                                                min-width="180"
                                            >
                                                <template #default="scope">
                                                    <el-input
                                                        v-model="scope.row.key"
                                                        placeholder="例如 testpartner.sm-os.com"
                                                    />
                                                </template>
                                            </el-table-column>
                                            <el-table-column
                                                label="显示名称"
                                                min-width="160"
                                            >
                                                <template #default="scope">
                                                    <el-input
                                                        v-model="
                                                            scope.row.label
                                                        "
                                                        placeholder="可选：例如 SM测试环境"
                                                    />
                                                </template>
                                            </el-table-column>
                                            <el-table-column
                                                label="匹配域名(逗号分隔)"
                                                min-width="220"
                                            >
                                                <template #default="scope">
                                                    <el-input
                                                        v-model="
                                                            scope.row
                                                                .hostPatternsText
                                                        "
                                                        placeholder="可选：sm-os.com,testpartner.sm-os.com"
                                                    />
                                                </template>
                                            </el-table-column>
                                            <el-table-column
                                                label="启用"
                                                width="90"
                                            >
                                                <template #default="scope">
                                                    <el-switch
                                                        v-model="
                                                            scope.row.enabled
                                                        "
                                                    />
                                                </template>
                                            </el-table-column>
                                            <el-table-column
                                                label="备注"
                                                min-width="160"
                                            >
                                                <template #default="scope">
                                                    <el-input
                                                        v-model="
                                                            scope.row.remark
                                                        "
                                                        placeholder="可选"
                                                    />
                                                </template>
                                            </el-table-column>
                                            <el-table-column
                                                label="操作"
                                                width="80"
                                                fixed="right"
                                            >
                                                <template #default="scope">
                                                    <el-button
                                                        link
                                                        type="danger"
                                                        @click="
                                                            removePersistContextScopeRow(
                                                                scope.$index,
                                                            )
                                                        "
                                                        >删除</el-button
                                                    >
                                                </template>
                                            </el-table-column>
                                        </el-table>
                                    </div>
                                </el-form-item>
                            </el-col>
                            <el-col :span="24">
                                <el-form-item label="备注">
                                    <el-input
                                        v-model="runtimeProfileForm.remark"
                                        type="textarea"
                                        :rows="2"
                                    />
                                </el-form-item>
                            </el-col>
                        </el-row>
                    </el-form>
                </el-col>
            </el-row>
            <template #footer>
                <el-button @click="showRuntimeProfileDialog = false"
                    >关闭</el-button
                >
                <el-button
                    type="danger"
                    :disabled="!runtimeProfileForm.profileId"
                    @click="deleteRuntimeProfile"
                    >删除</el-button
                >
                <el-button
                    type="primary"
                    :loading="loading.runtimeProfileSave"
                    @click="saveRuntimeProfile"
                    >保存</el-button
                >
            </template>
        </el-dialog>

        <el-dialog
            v-model="showBrowserSessionDialog"
            title="浏览器Session管理"
            width="90%"
            destroy-on-close
            append-to-body
            :close-on-click-modal="false"
            :close-on-press-escape="false"
        >
            <el-row :gutter="16">
                <el-col :span="10">
                    <div class="runtime-profile-toolbar mb12">
                        <el-input
                            v-model="browserSessionKeyword"
                            clearable
                            placeholder="按名称/作用域筛选Session"
                        />
                        <el-button
                            type="primary"
                            @click="createBrowserSessionDraft"
                            >新建</el-button
                        >
                        <el-button @click="loadBrowserSessions">刷新</el-button>
                    </div>
                    <el-table
                        v-loading="loading.browserSession"
                        :data="filteredBrowserSessions"
                        border
                        row-key="sessionId"
                        highlight-current-row
                        max-height="520px"
                        @current-change="handleBrowserSessionRowChange"
                    >
                        <el-table-column
                            label="名称"
                            min-width="180"
                            show-overflow-tooltip
                        >
                            <template #default="scope">{{
                                scope.row.sessionName || "-"
                            }}</template>
                        </el-table-column>
                        <el-table-column
                            label="作用域Key"
                            min-width="180"
                            show-overflow-tooltip
                        >
                            <template #default="scope">{{
                                scope.row.scopeKey || "-"
                            }}</template>
                        </el-table-column>
                        <el-table-column
                            label="适用范围"
                            min-width="150"
                            show-overflow-tooltip
                        >
                            <template #default="scope">{{
                                formatRuntimeProfileScope(scope.row)
                            }}</template>
                        </el-table-column>
                        <el-table-column label="状态" width="90">
                            <template #default="scope">
                                <el-tag
                                    :type="
                                        scope.row.enabled === false
                                            ? 'info'
                                            : 'success'
                                    "
                                    >{{
                                        scope.row.enabled === false
                                            ? "停用"
                                            : "启用"
                                    }}</el-tag
                                >
                            </template>
                        </el-table-column>
                    </el-table>
                </el-col>
                <el-col :span="14">
                    <el-form :model="browserSessionForm" label-width="120px">
                        <el-row :gutter="12">
                            <el-col :span="12">
                                <el-form-item label="Session名称">
                                    <el-input
                                        v-model="browserSessionForm.sessionName"
                                        placeholder="例如：SM测试登录态"
                                    />
                                </el-form-item>
                            </el-col>
                            <el-col :span="12">
                                <el-form-item label="作用域Key">
                                    <el-input
                                        v-model="browserSessionForm.scopeKey"
                                        placeholder="例如：testpartner.sm-os.com"
                                    />
                                </el-form-item>
                            </el-col>
                            <el-col :span="12">
                                <el-form-item label="是否启用">
                                    <el-switch
                                        v-model="browserSessionForm.enabled"
                                    />
                                </el-form-item>
                            </el-col>
                            <el-col :span="12">
                                <el-form-item label="绑定浏览器">
                                    <el-select
                                        v-model="browserSessionForm.browserName"
                                        clearable
                                        style="width: 100%"
                                        placeholder="可选：仅匹配指定浏览器"
                                    >
                                        <el-option
                                            v-for="item in browserOptions"
                                            :key="item.value"
                                            :label="item.label"
                                            :value="item.value"
                                        />
                                    </el-select>
                                </el-form-item>
                            </el-col>
                            <el-col :span="12">
                                <el-form-item label="项目(可选)">
                                    <el-select
                                        v-model="browserSessionForm.projectId"
                                        clearable
                                        filterable
                                        style="width: 100%"
                                    >
                                        <el-option
                                            v-for="item in projectOptions"
                                            :key="item.projectId"
                                            :label="item.projectName"
                                            :value="item.projectId"
                                        />
                                    </el-select>
                                </el-form-item>
                            </el-col>
                            <el-col :span="12">
                                <el-form-item label="模块(可选)">
                                    <el-select
                                        v-model="browserSessionForm.moduleId"
                                        clearable
                                        filterable
                                        style="width: 100%"
                                    >
                                        <el-option
                                            v-for="item in filteredBrowserSessionModules"
                                            :key="item.moduleId"
                                            :label="item.moduleName"
                                            :value="item.moduleId"
                                        />
                                    </el-select>
                                </el-form-item>
                            </el-col>
                            <el-col :span="12">
                                <el-form-item label="排序">
                                    <el-input-number
                                        v-model="browserSessionForm.sort"
                                        :min="0"
                                        :step="1"
                                        controls-position="right"
                                        style="width: 100%"
                                    />
                                </el-form-item>
                            </el-col>
                            <el-col :span="12">
                                <el-form-item label="匹配域名">
                                    <el-input
                                        v-model="
                                            browserSessionForm.hostPatternsText
                                        "
                                        placeholder="可选：sm-os.com,*.sm-os.com"
                                    />
                                </el-form-item>
                            </el-col>
                            <el-col :span="24">
                                <el-form-item label="快速导入">
                                    <el-row :gutter="8" style="width: 100%">
                                        <el-col :span="24">
                                            <el-button
                                                style="width: 100%"
                                                @click="
                                                    applyBrowserSessionQuickImport
                                                "
                                                >解析并填充StorageState</el-button
                                            >
                                        </el-col>
                                        <el-col :span="24" class="mt8">
                                            <el-input
                                                v-model="
                                                    browserSessionImportText
                                                "
                                                type="textarea"
                                                :rows="4"
                                                placeholder="支持 storage_state JSON、Cookie: a=1; b=2、Set-Cookie 响应头，或完整请求头文本"
                                            />
                                        </el-col>
                                    </el-row>
                                </el-form-item>
                            </el-col>
                            <el-col :span="24">
                                <el-form-item label="StorageState(JSON)">
                                    <el-input
                                        v-model="
                                            browserSessionForm.storageStateText
                                        "
                                        type="textarea"
                                        :rows="12"
                                        placeholder='例如：{"cookies":[],"origins":[]}'
                                    />
                                </el-form-item>
                            </el-col>
                            <el-col :span="24">
                                <el-form-item label="备注">
                                    <el-input
                                        v-model="browserSessionForm.remark"
                                        type="textarea"
                                        :rows="2"
                                    />
                                </el-form-item>
                            </el-col>
                        </el-row>
                    </el-form>
                </el-col>
            </el-row>
            <template #footer>
                <el-button @click="showBrowserSessionDialog = false"
                    >关闭</el-button
                >
                <el-button
                    type="danger"
                    :disabled="!browserSessionForm.sessionId"
                    @click="deleteBrowserSession"
                    >删除</el-button
                >
                <el-button
                    type="primary"
                    :loading="loading.browserSessionSave"
                    @click="saveBrowserSession"
                    >保存</el-button
                >
            </template>
        </el-dialog>
</template>

<script setup>
const props = defineProps({
    context: {
        type: Object,
        required: true,
    },
});

const {
    showRuntimeProfileDialog,
    runtimeProfileKeyword,
    createRuntimeProfileDraft,
    loadRuntimeProfiles,
    loading,
    filteredRuntimeProfiles,
    handleRuntimeProfileRowChange,
    formatRuntimeProfileScope,
    runtimeProfileForm,
    runtimeTargetOptions,
    projectOptions,
    filteredRuntimeProfileModules,
    runtimeProfileImportHost,
    applyRuntimeProfileQuickImport,
    runtimeProfileImportText,
    addPersistContextScopeRow,
    removePersistContextScopeRow,
    deleteRuntimeProfile,
    saveRuntimeProfile,
    showBrowserSessionDialog,
    browserSessionKeyword,
    createBrowserSessionDraft,
    loadBrowserSessions,
    filteredBrowserSessions,
    handleBrowserSessionRowChange,
    browserSessionForm,
    browserOptions,
    filteredBrowserSessionModules,
    browserSessionImportText,
    applyBrowserSessionQuickImport,
    deleteBrowserSession,
    saveBrowserSession,
} = props.context;
</script>

<style scoped lang="scss">
@import "../styles/dialogs.scss";
</style>
