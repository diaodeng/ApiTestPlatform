<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="项目名称" prop="projectName">
        <el-input
            v-model="queryParams.projectName"
            placeholder="请输入项目名称"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="项目状态" clearable style="width: 200px">
          <el-option
              v-for="dict in qtr_data_status"
              :key="dict.value * 1"
              :label="dict.label"
              :value="dict.value * 1"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <slot name="table-tool"></slot>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table
        border
        ref="tableRef"
        v-if="refreshTable"
        v-loading="loading"
        :data="projectList"
        row-key="projectId"
        table-layout="fixed"
        :default-expand-all="isExpandAll"
        @selection-change="handleSelectionChange"
        @select="handleSelect"
        @select-all="handleSelectAll"
        max-height="calc(100vh - 280px)"
    >
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column prop="projectId" label="ID" width="150"></el-table-column>
      <el-table-column prop="projectName" align="left" label="项目名称" min-width="200"></el-table-column>
      <el-table-column prop="responsibleName" align="center" label="负责人" width="100"></el-table-column>
      <el-table-column prop="testUser" label="测试负责人" align="center" width="100"></el-table-column>
      <el-table-column prop="devUser" label="开发负责人" align="center" width="100"></el-table-column>
      <el-table-column prop="orderNum" label="排序" align="center" width="70"></el-table-column>
      <el-table-column prop="status" label="状态" align="center" width="70">
        <template #default="scope">
          <dict-tag :options="qtr_data_status" :value="scope.row.status"/>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" class-name="small-padding fixed-width"
                       width="150">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" prop="updateTime" class-name="small-padding fixed-width"
                       width="150">
        <template #default="scope">
          <span>{{ parseTime(scope.row.updateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" class-name="small-padding fixed-width" fixed="right" width="120"
                       v-if="$slots.tableOperate">
        <template #default="scope">
          <slot name="tableOperate" :scope="scope"></slot>
        </template>
      </el-table-column>
    </el-table>

    <pagination
        v-show="total > 0 && showPagination"
        :total="total"
        v-model:page="queryParams.pageNum"
        v-model:limit="queryParams.pageSize"
        @pagination="getList"
    />
  </div>
</template>

<script setup>
import {listProject} from "@/api/hrm/project.js";

const {proxy} = getCurrentInstance();
const {qtr_data_status} = proxy.useDict("qtr_data_status");
const props = defineProps({
  showPagination: {type: Boolean, default: true},
  checkedIds: {type: Array, default: []}
});
const emits = defineEmits(['selectChange']);
defineExpose({handleQuery, getSelectedIds});

const tableRef = ref(null);
const projectList = ref([]);
const total = ref(0);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const title = ref("");
const isExpandAll = ref(true);
const refreshTable = ref(true);
const allSelectIds = ref([]);

const runIds = ref([]);

const data = reactive({
  form: {},
  queryParams: {
    projectName: undefined,
    status: undefined,
    pageNum: 1,
    pageSize: 10
  },
  rules: {
    projectName: [{required: true, message: "项目名称不能为空", trigger: "blur"}],
    orderNum: [{required: true, message: "显示排序不能为空", trigger: "blur"}]
  },
});

const {queryParams, form, rules} = toRefs(data);

/** 查询项目列表 */
function getList() {
  loading.value = true;
  listProject(queryParams.value).then(response => {
    projectList.value = response.rows;
    total.value = response.total;
    nextTick(() => {
      if (tableRef.value) {
        tableRef.value.clearSelection();
      }
      if (props.checkedIds && props.checkedIds.length > 0) {
        if (tableRef.value && projectList.value) {
          projectList.value.forEach(item => {
            if (props.checkedIds.find(dataId => dataId === item.projectId)) {
              tableRef.value.toggleRowSelection(item, true);
            }
          });
        }
      }
    });
    loading.value = false;
  });
}

function handleSelectionChange(selection) {
  emits('selectChange', selection);
  runIds.value = selection.map(item => item.projectId);
}

function getSelectedIds() {
  return runIds.value;
}

/** 搜索按钮操作 */
function handleQuery() {
  getList();
}

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}

function handleSelect(selection, row) {
  let pageIds = projectList.value.map(item => item.projectId);
  let pageSelectIds = selection.map(item => item.projectId);
  let delIds = pageIds.filter(item => !pageSelectIds.includes(item));
  pageSelectIds.forEach((dataId) => {
    if (!allSelectIds.value.some((projectId) => projectId === dataId)) {
      allSelectIds.value.push(dataId);
    }
  });
  allSelectIds.value = allSelectIds.value.filter(item => !delIds.includes(item));
}


function handleSelectAll(selection) {
  let pageSelectIds = selection.map(item => item.projectId);
  if (pageSelectIds && pageSelectIds.length > 0) {
    pageSelectIds.forEach((item) => {
      if (!allSelectIds.value.some((projectId) => projectId === item)) {
        allSelectIds.value.push(item);
      }
    });
  } else {
    let pageIds = projectList.value.map(item => item.projectId);
    allSelectIds.value = allSelectIds.value.filter(item => !pageIds.includes(item));
  }

}

onMounted(() => {
  allSelectIds.value = toRaw(props.checkedIds);
  getList();
});

</script>
