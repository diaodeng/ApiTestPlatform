<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="项目" prop="projectId">
        <el-select v-model="queryParams.projectId" placeholder="请选择" clearable style="width: 150px">
          <el-option
              v-for="option in projectOptions"
              :key="option.projectId"
              :label="option.projectName"
              :value="option.projectId">
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item label="模块名称" prop="moduleName">
        <el-input
            v-model="queryParams.moduleName"
            placeholder="请输入模块名称"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="模块状态" clearable style="width: 200px">
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

    <el-table border
              ref="tableRef"
              v-loading="loading"
              :data="moduleList"
              @selection-change="handleSelectionChange"
              @select="handleSelect"
              @select-all="handleSelectAll"
              table-layout="fixed"
              max-height="calc(100vh - 280px)"
    >
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column label="模块ID" align="center" prop="moduleId" width="150"/>
      <el-table-column label="模块名称" align="center" prop="moduleName"/>
      <el-table-column label="所属项目" align="center" :formatter="formatProject"/>
      <el-table-column label="测试人员" align="center" prop="testUser" width="80"/>
      <el-table-column label="模块排序" align="center" prop="sort" width="80"/>
      <el-table-column label="状态" align="center" prop="status" width="70">
        <template #default="scope">
          <dict-tag :options="qtr_data_status" :value="scope.row.status + ''"/>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" class-name="small-padding fixed-width"
                       width="150">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" prop="createTime" class-name="small-padding fixed-width"
                       width="150">
        <template #default="scope">
          <span>{{ parseTime(scope.row.updateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" align="center" class-name="small-padding fixed-width" fixed="right"
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
import {listModule} from "@/api/hrm/module";
import {listProject} from "@/api/hrm/project";

const {proxy} = getCurrentInstance();
const {qtr_data_status} = proxy.useDict("qtr_data_status");
const props = defineProps({
  showPagination: {type: Boolean, default: true},
  checkedIds: {type: Array, default: []}
});

const tableRef = ref(null);
const moduleList = ref([]);
const projectOptions = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const allSelectIds = ref([]);

const runIds = ref([]);

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    projectId: undefined,
    moduleName: undefined,
    status: undefined
  },
  rules: {
    moduleName: [{required: true, message: "模块名称不能为空", trigger: "blur"}],
    projectId: [{required: true, message: "所属项目不能为空", trigger: "blur"}],
    testUser: [{required: true, message: "测试负责人不能为空", trigger: "blur"}],
    sort: [{required: true, message: "模块顺序不能为空", trigger: "blur"}]
  }
});

const emits = defineEmits(['selectChange']);
defineExpose({handleQuery, getSelectedIds});

const {queryParams, rules} = toRefs(data);

/** 查询模块列表 */
function getList() {
  loading.value = true;
  listModule(queryParams.value).then(response => {
    moduleList.value = response.rows;
    total.value = response.total;
    nextTick(() => {
      if (tableRef.value) {
        tableRef.value.clearSelection();
      }
      if (props.checkedIds && props.checkedIds.length > 0) {
        if (tableRef.value && moduleList.value) {
          moduleList.value.forEach(item => {
            if (props.checkedIds.find(dataId => dataId === item.moduleId)) {
              tableRef.value.toggleRowSelection(item, true);
            }
          });
        }
      }
    });
    loading.value = false;
  });
}

/** 查询项目列表 */
function getProjectSelect() {
  listProject({isPage: false}).then(response => {
    projectOptions.value = response.data;
  });
}

// 格式化项目名称的函数
function formatProject(row, column, cellValue) {
  // 假设每个debugtalk对象都有一个projectId属性，用于从其他地方获取项目名称
  return getProjectName(row.projectId); // getProjectName是一个根据projectId获取项目名称的函数
}

// 获取项目名称的函数（这里应该是你的实际逻辑）
function getProjectName(projectId) {
  // 根据projectId从某个地方（例如另一个数组或API）获取项目名称
  for (const project of projectOptions.value) {
    if (projectId === project.projectId) {
      return project.projectName;
    }
  }
}

/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  emits('selectChange', selection);
  ids.value = selection.map(item => item.moduleId);
  runIds.value = ids.value;
  single.value = selection.length !== 1;
  multiple.value = !selection.length;
}

function getSelectedIds() {
  return ids.value;
}

function handleSelect(selection, row) {
  let pageIds = moduleList.value.map(item => item.moduleId);
  let pageSelectIds = selection.map(item => item.moduleId);
  let delIds = pageIds.filter(item => !pageSelectIds.includes(item));
  pageSelectIds.forEach((dataId) => {
    if (!allSelectIds.value.some((moduleId) => moduleId === dataId)) {
      allSelectIds.value.push(dataId);
    }
  });
  allSelectIds.value = allSelectIds.value.filter(item => !delIds.includes(item));
}


function handleSelectAll(selection) {
  let pageSelectIds = selection.map(item => item.moduleId);
  if (pageSelectIds && pageSelectIds.length > 0) {
    pageSelectIds.forEach((item) => {
      if (!allSelectIds.value.some((moduleId) => moduleId === item)) {
        allSelectIds.value.push(item);
      }
    });
  } else {
    let pageIds = moduleList.value.map(item => item.moduleId);
    allSelectIds.value = allSelectIds.value.filter(item => !pageIds.includes(item));
  }

}

onMounted(() => {
  allSelectIds.value = toRaw(props.checkedIds);
  getProjectSelect();
  getList();
});

</script>
