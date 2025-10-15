<template>
   <div class="app-container">
      <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="68px">
         <el-form-item label="Logger名称" prop="loggerName">
            <el-input
               v-model="queryParams.loggerName"
               placeholder="请输入Logger名称"
               clearable
               style="width: 240px;"
               @keyup.enter="handleQuery"
            />
         </el-form-item>

         <el-form-item label="日志级别" prop="level">
            <el-select
               v-model="queryParams.level"
               placeholder="日志级别"
               clearable
               style="width: 240px"
            >
               <el-option key="DEBUG" label="DEBUG" value="DEBUG" />
               <el-option key="INFO" label="INFO" value="INFO" />
               <el-option key="WARNING" label="WARNING" value="WARNING" />
               <el-option key="ERROR" label="ERROR" value="ERROR" />
               <el-option key="CRITICAL" label="CRITICAL" value="CRITICAL" />
            </el-select>
         </el-form-item>

      </el-form>

      <el-row :gutter="10" class="mb8">
         <el-col :span="1.5">
            <el-button
               type="danger"
               plain
               icon="Delete"
               @click="resetQuery"
            >清空</el-button>
         </el-col>
         <el-col :span="1.5" v-if="false">
            <el-button
               type="warning"
               plain
               icon="Download"
               @click="handleExport"
               v-hasPermi="['monitor:operlog:export']"
            >导出</el-button>
         </el-col>
         <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
      </el-row>

      <el-table ref="operlogRef" v-loading="loading" :data="loggerList" @selection-change="handleSelectionChange" >
         <el-table-column type="selection" width="50" align="center" />
         <el-table-column label="Logger名称" prop="loggerName" />
        
         <el-table-column label="日志级别" prop="level">
            <template #default="scope">
               <el-select v-model="scope.row.level" placeholder="日志级别" clearable style="width: 150px" @change="handleSave(scope.row)">
                  <el-option key="DEBUG" label="DEBUG" value="DEBUG" />
                  <el-option key="INFO" label="INFO" value="INFO" />
                  <el-option key="WARNING" label="WARNING" value="WARNING" />
                  <el-option key="ERROR" label="ERROR" value="ERROR" />
                  <el-option key="CRITICAL" label="CRITICAL" value="CRITICAL" />
               </el-select>
            </template>
         </el-table-column>
         <el-table-column label="日志处理器" prop="handlers"></el-table-column>
      </el-table>

      <pagination
         v-show="total > 0"
         :total="total"
         v-model:page="queryParams.pageNum"
         v-model:limit="queryParams.pageSize"
         @pagination="getList"
      />
   </div>
</template>

<script setup name="Operlog">
import { getLoggerList, setLoggerLevel } from "@/api/monitor/operlog";

const { proxy } = getCurrentInstance();

const loggerList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const dateRange = ref([]);
const defaultSort = ref({ prop: "operTime", order: "descending" });

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 1000,
    loggerName: undefined,
    level: undefined,
  }
});

const { queryParams, form } = toRefs(data);

/** 查询登录日志 */
function getList() {
  loading.value = true;
  getLoggerList(queryParams.value).then(response => {
    loggerList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}

/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}
/** 重置按钮操作 */
function resetQuery() {
  dateRange.value = [];
  proxy.resetForm("queryRef");
  queryParams.value.pageNum = 1;
  proxy.$refs["operlogRef"].sort(defaultSort.value.prop, defaultSort.value.order);
}
/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.operId);
  multiple.value = !selection.length;
}

/** 保存日志级别 */
function handleSave(row) {
  if (!row.loggerName) {
    proxy.$modal.msgError("请选择Logger名称");
    return;
  }
  let data = {
    loggerName: [row.loggerName],
    level: row.level,
  }
  setLoggerLevel(data).then(() => {
    proxy.$modal.msgSuccess("保存成功");
    getList();
  }).catch(() => {});
}

getList();
</script>
