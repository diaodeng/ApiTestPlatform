<template>
    <el-dialog
        v-model="visible"
        :title="`系统凭证映射 - ${task?.taskName || ''}`"
        width="720px"
        append-to-body
        destroy-on-close
    >
        <el-alert
            title="阶段/阶段模板通过「系统标识」声明目标系统；凭证绑定是环境配置，发布版本后仍可修改。"
            type="info"
            :closable="false"
            class="mb8"
        />
        <el-table :data="rows" border size="small" empty-text="暂无映射，点击下方按钮添加">
            <el-table-column label="系统标识" min-width="140">
                <template #default="{ row }">
                    <el-input v-model="row.systemKey" maxlength="64" placeholder="如 erp / oms" />
                </template>
            </el-table-column>
            <el-table-column label="凭证绑定" min-width="220">
                <template #default="{ row }">
                    <el-select
                        v-model="row.credentialBindingId"
                        clearable
                        filterable
                        :loading="bindingsLoading"
                        placeholder="选择统一凭证绑定"
                        style="width: 100%"
                    >
                        <el-option
                            v-for="item in bindingOptions"
                            :key="item.bindingId"
                            :label="`${item.bindingName}（${item.credentialName || '-'}）`"
                            :value="String(item.bindingId)"
                        />
                    </el-select>
                </template>
            </el-table-column>
            <el-table-column label="说明" min-width="160">
                <template #default="{ row }">
                    <el-input v-model="row.remark" maxlength="255" placeholder="目标系统名称/地址" />
                </template>
            </el-table-column>
            <el-table-column label="操作" width="70" fixed="right">
                <template #default="{ $index }">
                    <el-button link type="danger" icon="Delete" @click="rows.splice($index, 1)" />
                </template>
            </el-table-column>
        </el-table>
        <el-button class="mt8" icon="Plus" @click="addRow">添加映射</el-button>
        <template #footer>
            <el-button @click="visible = false">取消</el-button>
            <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        </template>
    </el-dialog>
</template>

<script setup name="ConfigCredentialMappingDialog">
import { ref, computed, watch } from "vue";
import { ElMessage } from "element-plus";
import { getCredentialMappings, saveCredentialMappings } from "@/api/hrm/configuration_task";
import { listWebCredentialOptions } from "../composables/recordingOptions.js";

const props = defineProps({ modelValue: Boolean, task: Object });
const emit = defineEmits(["update:modelValue", "saved"]);

const visible = computed({
    get: () => props.modelValue,
    set: (value) => emit("update:modelValue", value)
});
const rows = ref([]);
const saving = ref(false);
const bindingOptions = ref([]);
const bindingsLoading = ref(false);

watch(
    () => props.modelValue,
    async (opened) => {
        if (!opened || !props.task) return;
        rows.value = [];
        bindingsLoading.value = true;
        try {
            bindingOptions.value = await listWebCredentialOptions();
        } catch {
            bindingOptions.value = [];
        } finally {
            bindingsLoading.value = false;
        }
        try {
            const res = await getCredentialMappings(props.task.taskId);
            rows.value = (res.data || []).map((item) => ({
                systemKey: item.systemKey,
                credentialBindingId: item.credentialBindingId || "",
                remark: item.remark || ""
            }));
        } catch (e) {
            ElMessage.error(e.message || "凭证映射查询失败");
        }
    },
    { immediate: true }
);

function addRow() {
    rows.value.push({ systemKey: "", credentialBindingId: "", remark: "" });
}

async function save() {
    if (!props.task) return;
    const seen = new Set();
    for (const row of rows.value) {
        const key = (row.systemKey || "").trim();
        if (!key) {
            ElMessage.warning("系统标识不能为空");
            return;
        }
        if (seen.has(key)) {
            ElMessage.warning(`系统标识重复：${key}`);
            return;
        }
        seen.add(key);
    }
    saving.value = true;
    try {
        await saveCredentialMappings(
            props.task.taskId,
            rows.value.map((row) => ({
                systemKey: (row.systemKey || "").trim(),
                credentialBindingId: (row.credentialBindingId || "").trim(),
                remark: (row.remark || "").trim()
            }))
        );
        ElMessage.success("凭证映射已保存");
        emit("saved");
        visible.value = false;
    } catch (e) {
        ElMessage.error(e.message || "保存失败");
    } finally {
        saving.value = false;
    }
}
</script>

<style lang="scss" scoped>
.mt8 {
    margin-top: 8px;
}
.mb8 {
    margin-bottom: 8px;
}
</style>
