<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="所属项目" prop="projectId">
        <el-select v-model="queryParams.projectId" placeholder="请选择" @change="resetModule" clearable filterable
                   style="width: 150px">
          <el-option
              v-for="option in projectOptions"
              :key="option.projectId"
              :label="option.projectName"
              :value="option.projectId">
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item label="所属模块" prop="moduleId">
        <el-select v-model="queryParams.moduleId" placeholder="请选择" clearable filterable style="width: 150px">
          <el-option
              v-for="option in moduleOptions"
              :key="option.moduleId"
              :label="option.moduleName"
              :value="option.moduleId">
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item :label="dataName+'ID'" prop="caseId">
        <el-input
            v-model="queryParams.caseId"
            :placeholder="'请输入'+dataName+'名称'"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item :label="dataName+'名称'" prop="caseName">
        <el-input
            v-model="queryParams.caseName"
            :placeholder="'请输入'+dataName+'名称'"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" :placeholder="dataName+'状态'" clearable style="width: 100px">
          <el-option
              v-for="dict in qtr_case_status"
              :key="dict.value * 1"
              :label="dict.label"
              :value="dict.value * 1"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="onlySelf" @change="handleQuery">仅自己的数据</el-checkbox>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery" :loading="loading.page" :disabled="loading.page">
          搜索
        </el-button>
        <el-button type="default" icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <slot name="table-tool"></slot>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading.page"
              ref="tableRef"
              :data="caseList"
              @select="handleSelect"
              @select-all="handleSelectAll"
              @selection-change="handleSelectionChange"
              border
              table-layout="fixed"
              max-height="calc(100vh - 280px)"
    >
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column :label="dataName+'ID'" prop="caseId" width="150px"/>
      <el-table-column :label="dataName+'名称'" prop="caseName" width="auto" min-width="200px"/>
      <el-table-column label="所属项目" prop="projectName">
        <template #default="scope">
          <span>{{ nameOrGlob(scope.row.projectName) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="所属模块" prop="moduleName">
        <template #default="scope">
          <span>{{ nameOrGlob(scope.row.moduleName) }}</span>
        </template>
      </el-table-column>
      <!--         <el-table-column label="用例排序" align="center" prop="sort" />-->
      <el-table-column label="状态" align="center" prop="status" width="120px">
        <template #default="scope">
          <slot name="caseStatus" :scope="scope">
            <DictTag :options="qtr_case_status" :value="scope.row.status"></DictTag>
          </slot>
        </template>
      </el-table-column>
      <el-table-column label="创建人" align="center" prop="createBy" width="80px"></el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" class-name="small-padding fixed-width"
                       width="150px">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" prop="createTime" class-name="small-padding fixed-width"
                       width="150px">
        <template #default="scope">
          <span>{{ parseTime(scope.row.updateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="170" align="center" class-name="small-padding fixed-width" fixed="right"
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
import {listCase} from "@/api/hrm/case";
import {selectModulList} from "@/api/hrm/module";
import {listProject} from "@/api/hrm/project";
import {HrmDataTypeEnum} from "@/components/hrm/enum.js";
import DictTag from "@/components/DictTag/index.vue";
// import JsonEditorVue from "json-editor-vue3";

const {proxy} = getCurrentInstance();
// const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
// const {hrm_data_type} = proxy.useDict("hrm_data_type");
const {qtr_case_status} = proxy.useDict("qtr_case_status");

const props = defineProps({
  dataType: {type: Number, default: HrmDataTypeEnum.case},
  showPagination: {type: Boolean, default: true},
  checkedIds: {type: Array, default: []}
});

const emits = defineEmits(['selectChange']);
defineExpose({handleQuery, getSelectedIds});


/*
* 区分用例还是配置
* */
const dataName = computed(() => {
  return props.dataType === HrmDataTypeEnum.case ? "用例" : "配置";
});

// provide("hrm_data_type", hrm_data_type);
// provide('sys_normal_disable', sys_normal_disable);
provide('qtr_case_status', qtr_case_status);

const tableRef = ref(null);
const caseList = ref([]);
const projectOptions = ref([]);
const moduleOptions = ref([]);
const open = ref(false);
// const loading = ref(true);
const showSearch = ref(true);
const allSelectIds = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const onlySelf = ref(true);
const _selectIds = ref(new Set());

const queryParams = toRef({
  pageNum: 1,
  pageSize: 10,
  type: props.dataType,
  caseId: undefined,
  caseName: undefined,
  projectId: undefined,
  moduleId: undefined,
  status: undefined,
  onlySelf: onlySelf
});

const loading = ref({
  page: false,
  edite: false,
  run: false,
  copy: false
});

/*
* 显示真实名称还是“全局”，没有设置项目和模块的显示未全局
* */
function nameOrGlob(val) {
  return val ? val : "全局";
}

/** 查询用例列表 */
function getList() {
  loading.value.page = true;
  // console.log(tableRef.value.getSelectionRows());
  listCase(queryParams.value).then(response => {
    caseList.value = response.rows;
    total.value = response.total;
    nextTick(() => {
      // if (tableRef.value) {
      //   tableRef.value.clearSelection();
      // }

      if (allSelectIds.value && allSelectIds.value.length > 0) {
        if (tableRef.value && caseList.value) {
          caseList.value.forEach(item => {
            if (allSelectIds.value.some(dataId => dataId === item.caseId)) {
              tableRef.value.toggleRowSelection(item, true);
            } else {
              tableRef.value.toggleRowSelection(item, false);
            }
          });
        }
      }
    });
  }).finally(() => {
    loading.value.page = false;
  });
}

/** 查询项目列表 */
function getProjectSelect() {
  listProject({isPage: false}).then(response => {
    projectOptions.value = response.data;
  });
}

/** 查询模块列表 */
function getModuleSelect() {
  selectModulList(queryParams.value).then(response => {
    moduleOptions.value = response.data;
  });
}

/**重置查询条件所属模块下拉框*/
function resetModule() {
  queryParams.value.moduleId = undefined;
  getModuleSelect();
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

function handleSelect(selection, row) {
  let pageIds = caseList.value.map(item => item.caseId);
  let pageSelectIds = selection.map(item => item.caseId);
  let delIds = pageIds.filter(item=> !pageSelectIds.includes(item));
  pageSelectIds.forEach((dataId) => {
    if (!allSelectIds.value.some((caseId) => caseId === dataId)) {
        allSelectIds.value.push(dataId);
      }
  });
  allSelectIds.value = allSelectIds.value.filter(item => !delIds.includes(item));
}

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  // console.log(selection);
  emits('selectChange', selection);
  // let pageSelectIds = selection.map(item => item.caseId);
  // let pageIds = caseList.value.map(item => item.caseId);
  // 从选中数据中排除当前页的数据
  // allSelectIds.value = allSelectIds.value.filter((dataId) => !caseList.value.some(item=>item.caseId === dataId));

  // 添加当前页选中的数据
  // selection.forEach((item) =>{
  //   if (!allSelectIds.value.some((caseId)=>caseId === item.caseId)){
  //     allSelectIds.value.push(item.caseId);
  //   }
  // });

  single.value = selection.length !== 1;
  multiple.value = !selection.length;
}

function handleSelectAll(selection) {
  let pageSelectIds = selection.map(item => item.caseId);
  if (pageSelectIds && pageSelectIds.length > 0) {
    pageSelectIds.forEach((item) => {
      if (!allSelectIds.value.some((caseId) => caseId === item)) {
        allSelectIds.value.push(item);
      }
    });
  } else {
    let pageIds = caseList.value.map(item => item.caseId);
    allSelectIds.value = allSelectIds.value.filter(item => !pageIds.includes(item));
  }

}

function getSelectedIds() {
  return allSelectIds.value;
}

watch(() => props.checkedIds, (newValue) => {
  console.log("数据变化了");
  // allSelectIds.value = newValue;
}, {deep: true});


onMounted(() => {
  allSelectIds.value = toRaw(props.checkedIds);
  // _selectIds.value.clear();
  // props.checkedIds.forEach(item => _selectIds.value.add(item));
  getProjectSelect();
  getList();

});

</script>
