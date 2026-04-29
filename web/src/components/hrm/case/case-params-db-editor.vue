<script setup>
import {
  addCaseParamsColumn,
  addCaseParamsRow,
  delCaseParams,
  deleteCaseParamsColumn,
  listCaseParams,
  updateCaseParams,
  uploadParamsFileToServer
} from "@/api/hrm/case.js";
import {ElMessage, ElMessageBox} from "element-plus";

const props = defineProps({
  caseId: {
    type: [String, Number],
    required: true
  },
  caseName: {
    type: String,
    default: ""
  }
});

const fileInputRef = ref();
const file = ref(null);
const importProcess = ref("");
const tableColumns = ref([]);
const tableRows = ref([]);
const selectedRows = ref([]);
const deleteColumnName = ref("");

const loading = reactive({
  list: false,
  import: false,
  save: false,
  row: false,
  column: false,
  delete: false
});

const searchForm = reactive({
  column: "",
  value: ""
});

const pagination = reactive({
  pageNum: 1,
  pageSize: 20,
  total: 0
});

const pageSizeOptions = [20, 50, 100];

const canSearch = computed(() => {
  return Boolean(searchForm.column && searchForm.value.trim());
});

const hasColumns = computed(() => tableColumns.value.length > 0);

function normalizeRow(row, columns) {
  const normalized = {
    _row_id: row?._row_id,
    __enable: row?.__enable !== false
  };
  columns.forEach((column) => {
    normalized[column] = row?.[column] ?? "";
  });
  return normalized;
}

function buildQueryPayload() {
  const searchValue = searchForm.value.trim();
  return {
    caseId: props.caseId,
    pageNum: pagination.pageNum,
    pageSize: pagination.pageSize,
    searchColumn: searchForm.column || undefined,
    searchValue: searchForm.column && searchValue ? searchValue : undefined
  };
}

function buildRowsPayload() {
  return tableRows.value.map((row) => {
    const payload = {
      _row_id: row._row_id,
      __enable: !!row.__enable
    };
    tableColumns.value.forEach((column) => {
      payload[column] = row[column] ?? "";
    });
    return payload;
  });
}

async function loadTableData(options = {}) {
  const {resetPage = false, allowAdjustPage = true} = options;
  if (!props.caseId) {
    tableColumns.value = [];
    tableRows.value = [];
    pagination.total = 0;
    return;
  }
  if (resetPage) {
    pagination.pageNum = 1;
  }
  loading.list = true;
  try {
    const response = await listCaseParams(buildQueryPayload());
    const columns = response.columns || [];
    tableColumns.value = columns;
    pagination.total = response.total || 0;
    tableRows.value = (response.rows || []).map((row) => normalizeRow(row, columns));

    if (allowAdjustPage) {
      const maxPage = Math.max(1, Math.ceil((pagination.total || 0) / pagination.pageSize));
      if (pagination.pageNum > maxPage) {
        pagination.pageNum = maxPage;
        await loadTableData({allowAdjustPage: false});
      }
    }
  } finally {
    loading.list = false;
  }
}

function handleFileChange(event) {
  file.value = event.target.files?.[0] || null;
}

function resetFileInput() {
  file.value = null;
  if (fileInputRef.value) {
    fileInputRef.value.value = "";
  }
}

async function uploadFile() {
  if (!file.value) {
    ElMessage.warning("请选择 CSV 文件");
    return;
  }
  loading.import = true;
  importProcess.value = "";
  try {
    const uploadFormData = new FormData();
    uploadFormData.append("file", file.value);
    uploadFormData.append("caseId", props.caseId);
    await uploadParamsFileToServer(uploadFormData, importProcess);
    ElMessage.success("导入成功");
    resetFileInput();
    await loadTableData();
  } finally {
    loading.import = false;
  }
}

async function deleteAllRows() {
  try {
    await ElMessageBox.confirm("确定删除当前用例的全部数据库参数吗？", "删除确认", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消"
    });
  } catch {
    return;
  }
  loading.delete = true;
  try {
    await delCaseParams({caseId: props.caseId});
    pagination.pageNum = 1;
    ElMessage.success("删除成功");
    await loadTableData({allowAdjustPage: false});
  } finally {
    loading.delete = false;
  }
}

async function handleSearch() {
  if (searchForm.value.trim() && !searchForm.column) {
    ElMessage.warning("请选择搜索列");
    return;
  }
  await loadTableData({resetPage: true});
}

async function resetSearch() {
  searchForm.column = "";
  searchForm.value = "";
  await loadTableData({resetPage: true});
}

async function addRow() {
  if (!hasColumns.value) {
    ElMessage.warning("当前没有列，请先导入数据");
    return;
  }
  loading.row = true;
  try {
    await addCaseParamsRow({caseId: props.caseId});
    ElMessage.success("新增行成功");
    if (canSearch.value) {
      ElMessage.warning("当前存在搜索条件，新行可能不会显示");
      await loadTableData();
      return;
    }
    pagination.pageNum = Math.max(1, Math.ceil((pagination.total + 1) / pagination.pageSize));
    await loadTableData({allowAdjustPage: false});
  } finally {
    loading.row = false;
  }
}

async function addColumn() {
  if (!tableColumns.value.length) {
    ElMessage.warning("当前没有数据行，请先导入数据");
    return;
  }
  let value;
  try {
    ({value} = await ElMessageBox.prompt("请输入新增列名", "新增列", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      inputPattern: /\S+/,
      inputErrorMessage: "列名不能为空"
    }));
  } catch {
    return;
  }
  const columnName = value?.trim();
  if (!columnName) {
    return;
  }
  loading.column = true;
  try {
    await addCaseParamsColumn({
      caseId: props.caseId,
      columnName
    });
    deleteColumnName.value = "";
    ElMessage.success("新增列成功");
    await loadTableData();
  } finally {
    loading.column = false;
  }
}

function getSelectedRowIds() {
  return selectedRows.value.map((row) => row._row_id).filter(Boolean);
}

async function deleteRows(rowIds = []) {
  const ids = rowIds.length > 0 ? rowIds : getSelectedRowIds();
  if (ids.length <= 0) {
    ElMessage.warning("请先选择要删除的行");
    return;
  }
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${ids.length} 行数据吗？`, "删除确认", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消"
    });
  } catch {
    return;
  }
  loading.delete = true;
  try {
    await delCaseParams({
      caseId: props.caseId,
      rowIds: ids
    });
    selectedRows.value = [];
    ElMessage.success("删除成功");
    await loadTableData();
  } finally {
    loading.delete = false;
  }
}

async function removeSelectedColumn() {
  if (!deleteColumnName.value) {
    ElMessage.warning("请选择要删除的列");
    return;
  }
  const columnName = deleteColumnName.value;
  try {
    await ElMessageBox.confirm(`确定删除列“${columnName}”吗？`, "删除确认", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消"
    });
  } catch {
    return;
  }
  loading.delete = true;
  try {
    await deleteCaseParamsColumn({
      caseId: props.caseId,
      columnName
    });
    if (searchForm.column === columnName) {
      searchForm.column = "";
      searchForm.value = "";
    }
    deleteColumnName.value = "";
    ElMessage.success("删除成功");
    await loadTableData({resetPage: true});
  } finally {
    loading.delete = false;
  }
}

async function saveRows() {
  loading.save = true;
  try {
    await updateCaseParams({
      caseId: props.caseId,
      rowsData: buildRowsPayload()
    });
    ElMessage.success("保存成功");
    await loadTableData({allowAdjustPage: false});
  } finally {
    loading.save = false;
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows;
}

async function handlePageChange(pageNum) {
  pagination.pageNum = pageNum;
  await loadTableData({allowAdjustPage: false});
}

async function handleSizeChange(pageSize) {
  pagination.pageSize = pageSize;
  pagination.pageNum = 1;
  await loadTableData({allowAdjustPage: false});
}

watch(
  () => props.caseId,
  async (value) => {
    resetFileInput();
    searchForm.column = "";
    searchForm.value = "";
    deleteColumnName.value = "";
    selectedRows.value = [];
    pagination.pageNum = 1;
    if (value) {
      await loadTableData({allowAdjustPage: false});
    }
  },
  {immediate: true}
);
</script>

<template>
  <div class="case-params-db-editor">
    <template v-if="caseId">
      <el-card shadow="never" class="toolbar-card">
        <el-space wrap>
          <input ref="fileInputRef" type="file" accept=".csv,text/csv" @change="handleFileChange"/>
          <el-button :disabled="!file" :loading="loading.import" type="primary" @click="uploadFile">上传 CSV</el-button>
          <el-button :disabled="loading.delete" type="danger" @click="deleteAllRows">清空数据</el-button>
          <el-text type="primary" v-if="importProcess">{{ importProcess }}</el-text>
          <el-text>当前行数：{{ pagination.total }}</el-text>
          <el-text>当前列数：{{ tableColumns.length }}</el-text>
        </el-space>
      </el-card>

      <el-card shadow="never" class="toolbar-card">
        <el-space wrap>
          <el-select
            v-model="searchForm.column"
            clearable
            filterable
            placeholder="选择搜索列"
            style="width: 220px"
          >
            <el-option
              v-for="column in tableColumns"
              :key="column"
              :label="column"
              :value="column"
            />
          </el-select>
          <el-input
            v-model="searchForm.value"
            clearable
            placeholder="输入列值关键字"
            style="width: 260px"
            @keyup.enter="handleSearch"
          />
          <el-button :loading="loading.list" type="primary" @click="handleSearch">搜索</el-button>
          <el-button :disabled="!searchForm.column && !searchForm.value" @click="resetSearch">重置</el-button>
        </el-space>
      </el-card>

      <el-card shadow="never" class="toolbar-card">
        <el-space wrap>
          <el-button :disabled="loading.row" :loading="loading.row" type="success" @click="addRow">新增行</el-button>
          <el-button :disabled="loading.column" :loading="loading.column" type="success" @click="addColumn">新增列</el-button>
          <el-button :disabled="getSelectedRowIds().length <= 0 || loading.delete" type="danger" @click="deleteRows()">
            删除选中行
          </el-button>
          <el-select
            v-model="deleteColumnName"
            clearable
            filterable
            placeholder="选择要删除的列"
            style="width: 220px"
          >
            <el-option
              v-for="column in tableColumns"
              :key="column"
              :label="column"
              :value="column"
            />
          </el-select>
          <el-button :disabled="!deleteColumnName || loading.delete" type="danger" @click="removeSelectedColumn">
            删除列
          </el-button>
          <el-button :loading="loading.save" type="primary" @click="saveRows">保存当前页修改</el-button>
          <el-button :disabled="loading.list" @click="loadTableData({allowAdjustPage: false})">刷新</el-button>
        </el-space>
      </el-card>

      <el-table
        v-loading="loading.list || loading.save || loading.delete || loading.row || loading.column"
        :data="tableRows"
        border
        class="params-table"
        max-height="calc(100vh - 310px)"
        row-key="_row_id"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" reserve-selection />
        <el-table-column type="index" label="#" width="60" align="center" />
        <el-table-column label="启用" width="90" align="center" fixed="left">
          <template #default="{row}">
            <el-switch v-model="row.__enable" />
          </template>
        </el-table-column>
        <el-table-column
          v-for="column in tableColumns"
          :key="column"
          :label="column"
          :min-width="180"
          show-overflow-tooltip
        >
          <template #default="{row}">
            <el-input v-model="row[column]" clearable size="small" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right" align="center">
          <template #default="{row}">
            <el-button link type="danger" @click="deleteRows([row._row_id])">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.pageNum"
          v-model:page-size="pagination.pageSize"
          :background="true"
          :page-sizes="pageSizeOptions"
          :layout="'total, sizes, prev, pager, next, jumper'"
          :total="pagination.total"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </template>
    <el-empty v-else description="请先保存用例后再管理数据库参数" />
  </div>
</template>

<style scoped lang="scss">
.case-params-db-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}

.toolbar-card {
  flex-shrink: 0;
}

.params-table {
  flex: 1;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  padding: 4px 0;
}
</style>
