<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="套件名称" prop="suiteName">
        <el-input
            v-model="queryParams.suiteName"
            placeholder="请输入套件名称"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="套件状态" clearable style="width: 200px">
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
        :data="suiteList"
        row-key="suiteId"
        :default-expand-all="isExpandAll"
        @selection-change="handleSelectionChange"
        @select="handleSelect"
        @select-all="handleSelectAll"
    >
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column prop="suiteId" label="ID" width="160"></el-table-column>
      <el-table-column prop="suiteName" label="套件名称" width="200"></el-table-column>
      <el-table-column prop="orderNum" label="排序" width="200"></el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="scope">
          <dict-tag :options="qtr_data_status" :value="scope.row.status + ''"/>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" class-name="small-padding fixed-width">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" prop="updateTime" class-name="small-padding fixed-width">
        <template #default="scope">
          <span>{{ parseTime(scope.row.updateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" class-name="small-padding fixed-width" v-if="$slots.tableOperate">
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
import {listSuite} from "@/api/qtr/suite";


const {proxy} = getCurrentInstance();
const {qtr_data_status} = proxy.useDict("qtr_data_status");
const props = defineProps({
  showPagination: {type: Boolean, default: true},
  checkedIds: {type: Array, default: []}
});
const emits = defineEmits(['selectChange']);
defineExpose({handleQuery, getSelectedIds});

const tableRef = ref(null);
const suiteList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const title = ref("");
const isExpandAll = ref(true);
const refreshTable = ref(true);
const total = ref(0);
const runIds = ref([]);
const allSelectIds = ref([]);

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    suiteName: undefined,
    status: undefined
  },
  rules: {
    suiteName: [{required: true, message: "套件名称不能为空", trigger: "blur"}],
    orderNum: [{required: true, message: "显示排序不能为空", trigger: "blur"}]
  },
});

const {queryParams, rules} = toRefs(data);

/** 查询套件列表 */
function getList() {
  loading.value = true;
  listSuite(queryParams.value).then(response => {
    suiteList.value = response.rows;
    total.value = response.total;
    nextTick(() => {
      if (tableRef.value) {
        tableRef.value.clearSelection();
      }
      if (props.checkedIds && props.checkedIds.length > 0) {
        if (tableRef.value && suiteList.value) {
          suiteList.value.forEach(item => {
            if (props.checkedIds.find(dataId => dataId === item.suiteId)) {
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
  runIds.value = selection.map(item => item.suiteId);
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
  let pageIds = suiteList.value.map(item => item.suiteId);
  let pageSelectIds = selection.map(item => item.suiteId);
  let delIds = pageIds.filter(item => !pageSelectIds.includes(item));
  pageSelectIds.forEach((dataId) => {
    if (!allSelectIds.value.some((suiteId) => suiteId === dataId)) {
      allSelectIds.value.push(dataId);
    }
  });
  allSelectIds.value = allSelectIds.value.filter(item => !delIds.includes(item));
}


function handleSelectAll(selection) {
  let pageSelectIds = selection.map(item => item.suiteId);
  if (pageSelectIds && pageSelectIds.length > 0) {
    pageSelectIds.forEach((item) => {
      if (!allSelectIds.value.some((suiteId) => suiteId === item)) {
        allSelectIds.value.push(item);
      }
    });
  } else {
    let pageIds = suiteList.value.map(item => item.suiteId);
    allSelectIds.value = allSelectIds.value.filter(item => !pageIds.includes(item));
  }

}

onMounted(() => {
  allSelectIds.value = toRaw(props.checkedIds);
  getList();
});

</script>
