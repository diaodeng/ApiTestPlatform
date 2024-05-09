<template>
   <div class="app-container">
      <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
         <el-form-item label="环境名称" prop="envName">
            <el-input
               v-model="queryParams.envName"
               placeholder="请输入环境名称"
               clearable
               style="width: 200px"
               @keyup.enter="handleQuery"
            />
         </el-form-item>
         <el-form-item label="状态" prop="status">
            <el-select v-model="queryParams.status" placeholder="环境状态" clearable style="width: 200px">
               <el-option
                  v-for="dict in sys_normal_disable"
                  :key="dict.value"
                  :label="dict.label"
                  :value="dict.value"
               />
            </el-select>
         </el-form-item>
         <el-form-item>
            <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
            <el-button icon="Refresh" @click="resetQuery">重置</el-button>
         </el-form-item>
      </el-form>

      <el-row :gutter="10" class="mb8">
         <el-col :span="1.5">
            <el-button
               type="primary"
               plain
               icon="Plus"
               @click="handleAdd"
               v-hasPermi="['hrm:env:add']"
            >新增</el-button>
         </el-col>
         <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
      </el-row>

      <el-table
          border
         v-if="refreshTable"
         v-loading="loading"
         :data="envList"
         row-key="envId"
         :default-expand-all="isExpandAll"
      >
         <el-table-column prop="envId" label="ID" width="100"></el-table-column>
         <el-table-column prop="envName" label="环境名称" width="200"></el-table-column>
         <el-table-column prop="envUrl" label="环境URL" width="260"></el-table-column>
         <el-table-column prop="orderNum" label="排序" width="200"></el-table-column>
         <el-table-column prop="status" label="状态" width="100">
            <template #default="scope">
               <dict-tag :options="sys_normal_disable" :value="scope.row.status" />
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
         <el-table-column label="操作" align="center" class-name="small-padding fixed-width">
            <template #default="scope">
               <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['hrm:env:edit']">修改</el-button>
<!--               <el-button link type="primary" icon="Plus" @click="handleAdd(scope.row)" v-hasPermi="['hrm:env:add']">新增</el-button>-->
               <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['hrm:env:remove']">删除</el-button>
            </template>
         </el-table-column>
      </el-table>

      <!-- 添加或修改环境对话框 -->
      <el-dialog :title="title" v-model="open" width="600px" append-to-body>
         <el-form ref="envRef" :model="form" :rules="rules" label-width="80px">
            <el-row>
               <el-col :span="12">
                  <el-form-item label="环境名称" prop="envName">
                     <el-input v-model="form.envName" placeholder="请输入环境名称" />
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="显示排序" prop="orderNum">
                     <el-input-number v-model="form.orderNum" controls-position="right" :min="0" />
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="环境地址" prop="envUrl">
                     <el-input v-model="form.envUrl" placeholder="请输入URL地址" maxlength="20" />
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="环境描述" prop="simpleDesc">
                     <el-input v-model="form.simpleDesc" placeholder="请输入描述" maxlength="11" />
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="环境状态">
                     <el-radio-group v-model="form.status">
                        <el-radio
                           v-for="dict in sys_normal_disable"
                           :key="dict.value"
                           :label="dict.value"
                        >{{ dict.label }}</el-radio>
                     </el-radio-group>
                  </el-form-item>
               </el-col>
            </el-row>
         </el-form>
         <template #footer>
            <div class="dialog-footer">
               <el-button type="primary" @click="submitForm">确 定</el-button>
               <el-button @click="cancel">取 消</el-button>
            </div>
         </template>
      </el-dialog>
   </div>
</template>

<script setup name="Env">
import { listEnv, getEnv, delEnv, addEnv, updateEnv } from "@/api/hrm/env";

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

const envList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const title = ref("");
const isExpandAll = ref(true);
const refreshTable = ref(true);

const data = reactive({
  form: {},
  queryParams: {
    envName: undefined,
    status: undefined
  },
  rules: {
    envName: [{ required: true, message: "环境名称不能为空", trigger: "blur" }],
    orderNum: [{ required: true, message: "显示排序不能为空", trigger: "blur" }],
    envUrl: [{ required: true, message: "环境地址不能为空", trigger: "blur" }]
  },
});

const { queryParams, form, rules } = toRefs(data);

/** 查询环境列表 */
function getList() {
  loading.value = true;
  listEnv(queryParams.value).then(response => {
    envList.value = proxy.handleTree(response.data, "envId");
    loading.value = false;
  });
}
/** 取消按钮 */
function cancel() {
  open.value = false;
  reset();
}
/** 表单重置 */
function reset() {
  form.value = {
    envId: undefined,
    envName: undefined,
    orderNum: 0,
    envUrl: undefined,
    simpleDesc: undefined,
    status: "0"
  };
  proxy.resetForm("envRef");
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
/** 新增按钮操作 */
function handleAdd(row) {
  reset();
  listEnv().then(response => {
    envOptions.value = proxy.handleTree(response.data, "envId");
  });
  open.value = true;
  title.value = "添加环境";
}
/** 展开/折叠操作 */
function toggleExpandAll() {
  refreshTable.value = false;
  isExpandAll.value = !isExpandAll.value;
  nextTick(() => {
    refreshTable.value = true;
  });
}
/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  getEnv(row.envId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改环境";
  });
}
/** 提交按钮 */
function submitForm() {
  proxy.$refs["envRef"].validate(valid => {
    if (valid) {
      if (form.value.envId != undefined) {
        updateEnv(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addEnv(form.value).then(response => {
          proxy.$modal.msgSuccess("新增成功");
          open.value = false;
          getList();
        });
      }
    }
  });
}
/** 删除按钮操作 */
function handleDelete(row) {
  proxy.$modal.confirm('是否确认删除名称为"' + row.envName + '"的数据项?').then(function() {
    return delEnv(row.envId);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}

getList();
</script>
