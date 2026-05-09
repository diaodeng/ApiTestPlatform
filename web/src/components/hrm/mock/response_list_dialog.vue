<template>
  <el-dialog
    v-model="openDialog"
    width="1200px"
    append-to-body
    destroy-on-close
    align-center
  >
    <template #header>
      <div class="dialog-title">
        <span>Mock响应列表</span>
        <el-tag type="info" effect="plain">规则ID: {{ props.ruleId || '-' }}</el-tag>
        <el-text v-if="props.ruleName">{{ props.ruleName }}</el-text>
      </div>
    </template>

    <el-form :model="queryForm" :inline="true" class="query-form">
      <el-form-item label="响应名称">
        <el-input
          v-model="queryForm.name"
          placeholder="支持模糊查询"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="条件关键字">
        <el-input
          v-model="queryForm.responseConditionKeyword"
          placeholder="从response_condition中过滤"
          clearable
          style="width: 260px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="queryForm.status" clearable placeholder="全部" style="width: 120px">
          <el-option
            v-for="dict in qtr_data_status"
            :key="dict.value * 1"
            :label="dict.label"
            :value="dict.value * 1"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery" :loading="loading.list">查询</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <MockConditionEditor
      v-model="queryForm.responseCondition"
      title="高级搜索条件"
      add-button-text="添加筛选条件"
      class="advanced-condition"
      empty-text="未设置高级筛选条件"
    ></MockConditionEditor>

    <el-row :gutter="10" class="toolbar">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="openCreateDialog">新增响应</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="selectedResponseIds.length === 0"
          @click="handleBatchDelete"
        >批量删除</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="success" plain icon="Refresh" @click="fetchResponseList" :loading="loading.list"
        >刷新列表</el-button>
      </el-col>
    </el-row>

    <el-table
      :data="responseList"
      v-loading="loading.list"
      border
      max-height="calc(100vh - 340px)"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="响应ID" prop="ruleResponseId" width="180" />
      <el-table-column label="名称" prop="name" min-width="180" />
      <el-table-column label="标签" prop="responseTag" min-width="120" />
      <el-table-column label="优先级" width="100">
        <template #default="{ row }">
          <el-input
            v-model="row.priority"
            type="number"
            min="1"
            max="999"
            step="1"
            @blur="handlePriorityBlur(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <DictTag :options="qtr_data_status" :value="row.status" />
        </template>
      </el-table-column>
      <el-table-column label="默认响应" width="100">
        <template #default="{ row }">
          <el-tag :type="row.isDefault ? 'success' : 'info'">{{ row.isDefault ? '是' : '否' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="响应条件" min-width="360" show-overflow-tooltip>
        <template #default="{ row }">
          <div class="condition-text">{{ formatConditionText(row.responseCondition) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="170">
        <template #default="{ row }">
          <span>{{ parseTime(row.updateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" fixed="right" width="300">
        <template #default="{ row }">
          <el-button link type="primary" icon="Edit" @click="openEditDialog(row)">编辑</el-button>
          <el-button link type="warning" icon="CopyDocument" @click="handleCopy(row)">复制</el-button>
          <el-button link type="success" icon="Select" @click="setAsDefault(row)"
          >设默认</el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-dialog>

  <el-dialog
    v-model="editor.visible"
    :title="editor.isEdit ? '编辑响应' : '新增响应'"
    width="900px"
    append-to-body
    destroy-on-close
  >
    <el-form :model="editorForm" label-width="100px" v-loading="loading.detail">
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="响应名称" required>
            <el-input v-model="editorForm.name" placeholder="请输入响应名称" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="优先级">
            <el-input-number v-model="editorForm.priority" :min="1" :max="999" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="状态">
            <el-select v-model="editorForm.status" style="width: 100%">
              <el-option
                v-for="dict in qtr_data_status"
                :key="dict.value * 1"
                :label="dict.label"
                :value="dict.value * 1"
              />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="响应标签">
        <el-input v-model="editorForm.responseTag" placeholder="例如 v1 / abtest-A" />
      </el-form-item>
      <MockResponseEditor
        v-model="editorForm"
        :show-variable-guide="false"
        condition-title="响应匹配条件"
        condition-add-button-text="添加条件"
      ></MockResponseEditor>
    </el-form>

    <template #footer>
      <el-button @click="editor.visible = false">取消</el-button>
      <el-button type="primary" @click="saveResponse" :loading="loading.save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
  import { getCurrentInstance, reactive, ref, watch } from 'vue';
  import { ElMessage, ElMessageBox } from 'element-plus';
  import DictTag from '@/components/DictTag/index.vue';
  import MockConditionEditor from '@/components/hrm/mock/condition_editor.vue';
  import MockResponseEditor from '@/components/hrm/mock/response_editor.vue';
  import {
    addResponseDetail,
    copyResponseDetail,
    delResponseDetail,
    editResponseDetail,
    editResponsePriority,
    getRuleResponseDetail,
    listMockRuleResponse,
    listMockRuleResponseByCondition,
    setDefaultResponse,
  } from '@/api/hrm/mock.js';

  const { proxy } = getCurrentInstance();
  const { qtr_data_status } = proxy.useDict('qtr_data_status');

  const props = defineProps({
    ruleId: { type: [Number, String], default: null },
    ruleName: { type: String, default: '' },
  });
  const openDialog = defineModel('openDialog', { type: Boolean, default: false });

  const queryForm = reactive({
    name: '',
    responseConditionKeyword: '',
    status: undefined,
    responseCondition: [],
  });
  const loading = reactive({
    list: false,
    save: false,
    detail: false,
  });
  const responseList = ref([]);
  const selectedResponseIds = ref([]);

  const editor = reactive({
    visible: false,
    isEdit: false,
  });
  const editorForm = reactive(createEditorForm());

  function createEditorForm() {
    return {
      ruleResponseId: null,
      ruleId: props.ruleId,
      name: '',
      responseTag: '',
      isDefault: 0,
      status: 2,
      priority: 1,
      responseCondition: [],
      statusCode: 200,
      headersTemplate: [{ key: 'Content-Type', value: 'application/json' }],
      bodyTemplate: '',
      delay: 0,
      desc: '',
    };
  }

  function normalizeResponseData(data) {
    return {
      ...createEditorForm(),
      ...(data || {}),
      ruleId: props.ruleId,
      responseCondition: normalizeArray(data?.responseCondition, []),
      headersTemplate: normalizeArray(data?.headersTemplate, []),
    };
  }

  function normalizeArray(value, fallback = []) {
    if (Array.isArray(value)) {
      return value;
    }
    if (typeof value === 'string' && value.trim()) {
      try {
        const parsed = JSON.parse(value);
        if (Array.isArray(parsed)) {
          return parsed;
        }
      } catch (e) {
        return fallback;
      }
    }
    return fallback;
  }

  function formatConditionText(conditions) {
    const conditionList = normalizeArray(conditions, []);
    if (!conditionList.length) {
      return '无条件（默认匹配）';
    }
    return conditionList
      .map((item) => {
        const source = item?.source || 'query';
        const key = item?.key || '';
        const operator = item?.operator || '=';
        const value = item?.operator === 'exists' ? '' : item?.value ?? '';
        const dataType = item?.data_type || item?.dataType || 'str';
        return `${source}.${key} ${operator} ${value} (${dataType})`.trim();
      })
      .join(' && ');
  }

  async function fetchResponseList() {
    if (!props.ruleId) {
      responseList.value = [];
      return;
    }
    loading.list = true;
    try {
      const hasAdvancedCondition =
        Array.isArray(queryForm.responseCondition) && queryForm.responseCondition.length > 0;
      let rows = [];

      if (hasAdvancedCondition) {
        const response = await listMockRuleResponseByCondition({
          ruleId: props.ruleId,
          responseCondition: queryForm.responseCondition,
        });
        rows = Array.isArray(response.data) ? response.data : [];
        rows = rows.filter((item) => {
          const matchedName = queryForm.name
            ? String(item?.name || '').includes(queryForm.name)
            : true;
          const matchedStatus =
            queryForm.status !== undefined && queryForm.status !== null && queryForm.status !== ''
              ? item?.status === queryForm.status
              : true;
          const matchedKeyword = queryForm.responseConditionKeyword
            ? JSON.stringify(normalizeArray(item?.responseCondition, [])).includes(
                queryForm.responseConditionKeyword
              )
            : true;
          return matchedName && matchedStatus && matchedKeyword;
        });
      } else {
        const response = await listMockRuleResponse({
          ruleId: props.ruleId,
          name: queryForm.name || undefined,
          status: queryForm.status,
          responseConditionKeyword: queryForm.responseConditionKeyword || undefined,
        });
        rows = Array.isArray(response.data) ? response.data : [];
      }
      responseList.value = rows;
    } catch (error) {
      ElMessage.error(error?.message || '加载响应列表失败');
    } finally {
      loading.list = false;
    }
  }

  function handleSelectionChange(selection) {
    selectedResponseIds.value = selection.map((item) => item.ruleResponseId);
  }

  function handleQuery() {
    fetchResponseList();
  }

  function resetQuery() {
    queryForm.name = '';
    queryForm.status = undefined;
    queryForm.responseConditionKeyword = '';
    queryForm.responseCondition = [];
    fetchResponseList();
  }

  async function handlePriorityBlur(row) {
    if (!row?.ruleResponseId) {
      return;
    }
    const priorityValue = Number(row.priority);
    if (Number.isNaN(priorityValue) || priorityValue < 1) {
      row.priority = 1;
    }
    try {
      await editResponsePriority({
        ruleResponseId: row.ruleResponseId,
        priority: Number(row.priority),
      });
      ElMessage.success('优先级更新成功');
    } catch (error) {
      ElMessage.error(error?.message || '优先级更新失败');
    }
  }

  function openCreateDialog() {
    editor.isEdit = false;
    Object.assign(editorForm, createEditorForm());
    editor.visible = true;
  }

  async function openEditDialog(row) {
    if (!row?.ruleResponseId) {
      return;
    }
    editor.isEdit = true;
    Object.assign(editorForm, normalizeResponseData(row));
    editor.visible = true;
    loading.detail = true;
    try {
      const response = await getRuleResponseDetail({ ruleResponseId: row.ruleResponseId });
      const rowData = response?.data || row;
      Object.assign(editorForm, normalizeResponseData(rowData));
    } catch (error) {
      ElMessage.warning('加载响应详情失败，已使用列表数据填充编辑内容');
    } finally {
      loading.detail = false;
    }
  }

  async function saveResponse() {
    if (!props.ruleId) {
      ElMessage.warning('当前规则ID为空，无法保存响应');
      return;
    }
    if (!editorForm.name || !editorForm.name.trim()) {
      ElMessage.warning('响应名称不能为空');
      return;
    }
    const payload = JSON.parse(JSON.stringify(editorForm));
    payload.ruleId = props.ruleId;
    payload.name = payload.name.trim();
    payload.responseCondition = normalizeArray(payload.responseCondition, []);
    payload.headersTemplate = normalizeArray(payload.headersTemplate, []);

    loading.save = true;
    try {
      if (editor.isEdit && payload.ruleResponseId) {
        await editResponseDetail(payload);
        ElMessage.success('响应更新成功');
      } else {
        payload.ruleResponseId = null;
        payload.id = null;
        await addResponseDetail(payload);
        ElMessage.success('响应新增成功');
      }
      editor.visible = false;
      await fetchResponseList();
    } catch (error) {
      ElMessage.error(error?.message || '响应保存失败');
    } finally {
      loading.save = false;
    }
  }

  async function handleDelete(row) {
    if (!row?.ruleResponseId) {
      return;
    }
    try {
      await ElMessageBox.confirm(`确认删除响应【${row.name}】吗？`, '删除确认', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      });
      await delResponseDetail({ ruleResponseIds: [row.ruleResponseId] });
      ElMessage.success('删除成功');
      await fetchResponseList();
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(error?.message || '删除失败');
      }
    }
  }

  async function handleBatchDelete() {
    if (!selectedResponseIds.value.length) {
      ElMessage.warning('请先选择要删除的响应');
      return;
    }
    try {
      await ElMessageBox.confirm(`确认删除选中的${selectedResponseIds.value.length}个响应吗？`, '批量删除确认', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      });
      await delResponseDetail({ ruleResponseIds: selectedResponseIds.value });
      ElMessage.success('批量删除成功');
      selectedResponseIds.value = [];
      await fetchResponseList();
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(error?.message || '批量删除失败');
      }
    }
  }

  async function handleCopy(row) {
    if (!row?.ruleResponseId) {
      return;
    }
    try {
      const { value } = await ElMessageBox.prompt('请输入复制后的响应名称', '复制响应', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputValue: `${row.name}_copy`,
        inputValidator: (inputValue) => !!inputValue && !!inputValue.trim(),
        inputErrorMessage: '响应名称不能为空',
      });
      await copyResponseDetail({
        ruleId: props.ruleId,
        ruleResponseId: row.ruleResponseId,
        name: value.trim(),
      });
      ElMessage.success('复制成功');
      await fetchResponseList();
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(error?.message || '复制失败');
      }
    }
  }

  async function setAsDefault(row) {
    if (!row?.ruleResponseId) {
      return;
    }
    try {
      await ElMessageBox.confirm('确认将当前响应设置为默认响应吗？', '设置默认响应', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      });
      await setDefaultResponse({
        ruleId: props.ruleId,
        ruleResponseId: row.ruleResponseId,
        responseCondition: normalizeArray(row.responseCondition, []),
      });
      ElMessage.success('设置默认响应成功');
      await fetchResponseList();
    } catch (error) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(error?.message || '设置默认响应失败');
      }
    }
  }

  watch(
    () => openDialog.value,
    (visible) => {
      if (visible) {
        fetchResponseList();
      }
    }
  );

  watch(
    () => props.ruleId,
    () => {
      if (openDialog.value) {
        fetchResponseList();
      }
    }
  );
</script>

<style scoped>
  .dialog-title {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .query-form {
    margin-bottom: 10px;
  }

  .toolbar {
    margin-bottom: 10px;
  }

  .advanced-condition {
    margin-bottom: 10px;
  }

  .condition-text {
    white-space: pre-wrap;
    line-height: 1.4;
    color: #606266;
  }
</style>
