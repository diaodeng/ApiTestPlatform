<template>
  <div class="upload-file-source">
    <!-- 模式驱动字段显隐：暂不指定=资源键；资源绑定=资源下拉；Agent 目录文件=目录下拉。
         资源键与其他文件来源互斥，不会同时出现。 -->
    <el-select
      v-if="agentCode"
      :model-value="sourceMode"
      placeholder="文件来源"
      @change="onModeChange"
    >
      <el-option label="暂不指定（用输入绑定换文件）" value="none" />
      <el-option label="资源绑定" value="resource" />
      <el-option label="Agent 目录文件" value="agent" />
    </el-select>
    <el-input
      v-if="sourceMode === 'none'"
      :model-value="fileKeyValue"
      placeholder="资源键（可选，配合输入绑定在运行时换文件）"
      @update:model-value="onFileKeyInput"
    />
    <el-select
      v-if="agentCode && sourceMode === 'resource'"
      :model-value="resourceIds"
      multiple
      filterable
      collapse-tags
      collapse-tags-tooltip
      :loading="resourceLoading"
      :placeholder="`选择资源（READY，限 ${agentCode}）`"
      @visible-change="onResourceDropdownVisible"
      @change="onResourceChange"
    >
      <el-option
        v-for="item in resourceOptions"
        :key="item.resourceId"
        :label="item.label"
        :value="item.resourceId"
      />
    </el-select>
    <el-select
      v-if="agentCode && sourceMode === 'agent'"
      :model-value="agentPathValue"
      filterable
      :loading="agentFileLoading"
      :placeholder="`选择 Agent 上传目录文件（${agentCode}）`"
      @visible-change="onAgentFileDropdownVisible"
      @change="onAgentFilePick"
    >
      <el-option
        v-for="item in agentFileOptions"
        :key="item.path"
        :label="item.label"
        :value="item.path"
      />
    </el-select>
    <div v-if="sampleNames.length" class="upload-sample">
      样本：{{ sampleNames.join('、') }}（仅占位展示，运行时使用所选文件来源）
    </div>
  </div>
</template>

<script setup>
// 上传步骤"文件来源"编辑器：资源绑定 / Agent 目录文件双模式。
// 由步骤表格单元格与步骤详情弹窗共用；直接原地改写 params.resourceIds /
// params.agentPath（与步骤编辑器整体风格一致），修改后 emit('change') 通知调用方。
// 未传 agentCode 时降级为只展示样本（Web 用例编辑器场景无执行 Agent 概念）。
import { computed, ref, watch } from 'vue';
import { listResources, listAgentUploadFiles } from '@/api/hrm/configuration_task';

const props = defineProps({
  // 上传步骤的 params 对象（调用方持有，组件原地改写）
  params: { type: Object, required: true },
  // 任务执行 Agent 编码；为空时隐藏来源选择（降级展示样本）
  agentCode: { type: String, default: '' },
});

const emit = defineEmits(['change']);

const resourceOptions = ref([]);
const resourceLoading = ref(false);
const agentFileOptions = ref([]);
const agentFileLoading = ref(false);
const agentFilePrefix = ref('');
// 用户显式选择的模式。不能只从 params 反推：切到"资源绑定"时 resourceIds
// 往往已是空数组，computed 依赖不变不会重算，导致视图永远停留在旧模式。
const localMode = ref(null);

// 调用方切换步骤（params 对象引用变化）时重置本地模式，从数据重新推导
watch(
  () => props.params,
  () => {
    localMode.value = null;
  }
);

const resourceIds = computed(() => {
  const ids = props.params?.resourceIds;
  return Array.isArray(ids) ? ids.filter((item) => `${item ?? ''}`.trim()) : [];
});

const agentPathValue = computed(() => `${props.params?.agentPath ?? ''}`.trim());

const fileKeyValue = computed(() => `${props.params?.fileKey ?? ''}`.trim());

function onFileKeyInput(value) {
  if (!props.params) return;
  props.params.fileKey = `${value ?? ''}`.trim();
  emit('change');
}

const sourceMode = computed(() => {
  // 无执行 Agent 上下文（Web 用例编辑器）时固定"暂不指定"，只展示资源键与样本
  if (!props.agentCode) return 'none';
  // 用户显式选择优先；否则从 params 数据推导
  if (localMode.value) return localMode.value;
  if (resourceIds.value.length) return 'resource';
  if (agentPathValue.value) return 'agent';
  // "none" 是显式选项值（模板中有对应选项）：受控 el-select 的 model-value
  // 必须始终有合法值，undefined/空串会落入非受控分支导致选项点击不触发 change
  return 'none';
});

const sampleNames = computed(() => {
  const names = props.params?.fileNames;
  return Array.isArray(names) ? names.filter((item) => `${item ?? ''}`.trim()) : [];
});

function onModeChange(value) {
  if (!props.params) return;
  // 显式记录用户选择，保证 computed 立即反映切换（避免依赖未变导致视图停留旧模式）
  localMode.value = value;
  if (value === 'resource') {
    // 切到资源绑定：清掉 Agent 目录路径，保留已有资源选择
    delete props.params.agentPath;
    if (!Array.isArray(props.params.resourceIds)) props.params.resourceIds = [];
    agentFilePrefix.value = '';
  } else if (value === 'agent') {
    // 切到 Agent 目录文件：清掉资源绑定，等待选择受控相对路径
    props.params.resourceIds = [];
    if (!agentPathValue.value) props.params.agentPath = '';
  } else if (value === 'none') {
    // 暂不指定：清空两种来源，仅保留样本占位展示
    props.params.resourceIds = [];
    delete props.params.agentPath;
  }
  emit('change');
}

async function loadResourceOptions() {
  if (!props.agentCode || resourceLoading.value) return;
  resourceLoading.value = true;
  try {
    const response = await listResources({
      agentCode: props.agentCode,
      status: 'READY',
      limit: 200
    });
    const rows = Array.isArray(response.data) ? response.data : [];
    resourceOptions.value = rows.map((item) => ({
      resourceId: item.resourceId,
      label: `${item.originalFileName} · ${formatSize(item.fileSize)} · ${shortId(item.resourceId)}`
    }));
  } catch (error) {
    resourceOptions.value = [];
  } finally {
    resourceLoading.value = false;
  }
}

function onResourceDropdownVisible(visible) {
  if (visible) loadResourceOptions();
}

function onResourceChange(value) {
  if (!props.params) return;
  props.params.resourceIds = Array.isArray(value) ? value.filter(Boolean) : [];
  emit('change');
}

async function loadAgentFileOptions() {
  if (!props.agentCode || agentFileLoading.value) return;
  agentFileLoading.value = true;
  try {
    const response = await listAgentUploadFiles({
      agentCode: props.agentCode,
      prefix: agentFilePrefix.value
    });
    const entries = (response.data && response.data.entries) || [];
    const items = [];
    if (agentFilePrefix.value) {
      items.push({ path: '__qtr_parent__', type: 'parent', label: '← 上级目录' });
    }
    for (const item of entries) {
      const name = String(item.path || '').split('/').pop();
      items.push({
        path: item.path,
        type: item.type,
        label: item.type === 'directory' ? `📁 ${name}/` : `${name}（${formatSize(item.size)}）`
      });
    }
    agentFileOptions.value = items;
  } catch (error) {
    agentFileOptions.value = [];
  } finally {
    agentFileLoading.value = false;
  }
}

function onAgentFileDropdownVisible(visible) {
  if (visible) loadAgentFileOptions();
}

function onAgentFilePick(value) {
  if (value === '__qtr_parent__') {
    // 目录导航：回到上级目录，不改动步骤
    agentFilePrefix.value = agentFilePrefix.value.split('/').slice(0, -1).join('/');
    loadAgentFileOptions();
    return;
  }
  const option = agentFileOptions.value.find((item) => item.path === value);
  if (option && option.type === 'directory') {
    // 目录条目：下钻一层，不改动步骤
    agentFilePrefix.value = option.path;
    loadAgentFileOptions();
    return;
  }
  if (!props.params) return;
  props.params.agentPath = value;
  props.params.resourceIds = [];
  emit('change');
}

function shortId(value) {
  const text = String(value || '');
  return text.length > 10 ? `${text.slice(0, 6)}…${text.slice(-4)}` : text;
}

function formatSize(size) {
  const value = Number(size) || 0;
  if (value < 1024) return `${value}B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)}KB`;
  return `${(value / 1024 / 1024).toFixed(2)}MB`;
}
</script>

<style scoped>
.upload-file-source {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  min-width: 220px;
}

.upload-file-source .el-select {
  width: 100%;
}

.upload-sample {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
  word-break: break-all;
}
</style>
