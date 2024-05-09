<template>
   <div class="app-container">
      <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
         <el-form-item label="所属项目" prop="projectId">
            <el-select v-model="queryParams.projectId" placeholder="请选择" @change="resetModule" clearable>
              <el-option
                v-for="option in projectOptions"
                :key="option.projectId"
                :label="option.projectName"
                :value="option.projectId">
              </el-option>
            </el-select>
         </el-form-item>
        <el-form-item label="所属模块" prop="moduleId">
            <el-select v-model="queryParams.moduleId" placeholder="请选择" clearable>
              <el-option
                v-for="option in moduleOptions"
                :key="option.moduleId"
                :label="option.moduleName"
                :value="option.moduleId">
              </el-option>
            </el-select>
         </el-form-item>
        <el-form-item label="用例ID" prop="caseId">
            <el-input
               v-model="queryParams.caseId"
               placeholder="请输入用例名称"
               clearable
               style="width: 200px"
               @keyup.enter="handleQuery"
            />
         </el-form-item>
         <el-form-item label="用例名称" prop="caseName">
            <el-input
               v-model="queryParams.caseName"
               placeholder="请输入用例名称"
               clearable
               style="width: 200px"
               @keyup.enter="handleQuery"
            />
         </el-form-item>
         <el-form-item label="状态" prop="status">
            <el-select v-model="queryParams.status" placeholder="用例状态" clearable style="width: 200px">
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
               v-hasPermi="['hrm:case:add']"
            >新增</el-button>
         </el-col>
         <el-col :span="1.5">
            <el-button
               type="success"
               plain
               icon="Edit"
               :disabled="single"
               @click="handleUpdate"
               v-hasPermi="['hrm:case:edit']"
            >修改</el-button>
         </el-col>
         <el-col :span="1.5">
            <el-button
               type="danger"
               plain
               icon="Delete"
               :disabled="multiple"
               @click="handleDelete"
               v-hasPermi="['hrm:case:remove']"
            >删除</el-button>
         </el-col>
         <el-col :span="1.5">
            <el-button
               type="warning"
               plain
               icon="Download"
               @click="handleExport"
               v-hasPermi="['hrm:case:export']"
            >导出</el-button>
         </el-col>
         <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
      </el-row>

      <el-table v-loading="loading" :data="caseList"
                @selection-change="handleSelectionChange"
                border
      >
         <el-table-column type="selection" width="55" align="center" />
         <el-table-column label="用例ID" align="center" prop="caseId" />
         <el-table-column label="用例名称" align="center" prop="caseName" />
         <el-table-column label="所属项目" align="center" prop="projectName" />
         <el-table-column label="所属模块" align="center" prop="moduleName" />
<!--         <el-table-column label="用例排序" align="center" prop="sort" />-->
         <el-table-column label="状态" align="center" prop="status">
            <template #default="scope">
               <dict-tag :options="sys_normal_disable" :value="scope.row.status" />
            </template>
         </el-table-column>
         <el-table-column label="创建时间" align="center" prop="createTime" class-name="small-padding fixed-width">
            <template #default="scope">
               <span>{{ parseTime(scope.row.createTime) }}</span>
            </template>
         </el-table-column>
        <el-table-column label="更新时间" align="center" prop="createTime" class-name="small-padding fixed-width">
            <template #default="scope">
               <span>{{ parseTime(scope.row.updateTime) }}</span>
            </template>
         </el-table-column>
         <el-table-column label="操作" width="200" align="center" class-name="small-padding fixed-width">
            <template #default="scope">
               <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['hrm:case:detail']">查看</el-button>
               <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['hrm:case:edit']">修改</el-button>
               <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['hrm:case:remove']">删除</el-button>
            </template>
         </el-table-column>
      </el-table>

      <pagination
         v-show="total > 0"
         :total="total"
         v-model:page="queryParams.pageNum"
         v-model:limit="queryParams.pageSize"
         @pagination="getList"
      />

      <!-- 添加或修改用例对话框 -->
      <el-dialog :title="title" v-model="open" width="800px" append-to-body>
         <el-form ref="postRef" :model="form" :rules="rules" label-width="150px">
            <el-form-item label="用例名称" prop="caseName">
               <el-input v-model="form.caseName" placeholder="请输入用例名称" clearable />
            </el-form-item>
            <el-form-item label="所属项目" prop="projectId">
              <el-select v-model="form.projectId" placeholder="请选择" @change="resetModuleHandl">
                <el-option
                  v-for="option in projectOptions"
                  :key="option.projectId"
                  :label="option.projectName"
                  :value="option.projectId">
                </el-option>
              </el-select>
            </el-form-item>
           <el-form-item label="所属模块" prop="moduleId">
              <el-select v-model="form.moduleId" placeholder="请选择">
                <el-option
                  v-for="option in moduleOptionsHandl"
                  :key="option.moduleId"
                  :label="option.moduleName"
                  :value="option.moduleId">
                </el-option>
              </el-select>
            </el-form-item>
           <el-form-item label="前置config/test" prop="include">
               <el-input v-model="form.include" placeholder="置config/test" />
           </el-form-item>
           <el-form-item label="请求信息" prop="request">
               <el-input v-model="form.request" placeholder="请求信息" />
           </el-form-item>
           <el-form-item>
<!--             <JsonEditorVue v-model="form.request"-->
<!--              :mode-list="couldView"-->
<!--              :current-mode="tree"-->
<!--             >-->
<!--             </JsonEditorVue>-->
           </el-form-item>
           <el-form-item label="注释" prop="notes">
               <el-input v-model="form.notes" placeholder="注释" />
           </el-form-item>
            <el-form-item label="用例顺序" prop="sort">
               <el-input-number v-model="form.sort" controls-position="right" :min="0" />
            </el-form-item>
            <el-form-item label="用例状态" prop="status">
               <el-radio-group v-model="form.status">
                  <el-radio
                     v-for="dict in sys_normal_disable"
                     :key="dict.value"
                     :label="dict.value"
                  >{{ dict.label }}</el-radio>
               </el-radio-group>
            </el-form-item>

            <el-form-item label="备注" prop="remark">
               <el-input v-model="form.remark" type="textarea" placeholder="请输入内容" />
            </el-form-item>
         </el-form>
         <template #footer>
            <div class="dialog-footer">
               <el-button type="primary" @click="submitForm" v-hasPermi="['hrm:case:edit']">确 定</el-button>
               <el-button @click="cancel">取 消</el-button>
            </div>
         </template>
      </el-dialog>
   </div>
</template>

<script setup name="Case">
import { listCase, addCase, delCase, getCase, updateCase } from "@/api/hrm/case";
import {selectModulList, showModulList} from "@/api/hrm/module";
import {listProject} from "@/api/hrm/project";
// import JsonEditorVue from "json-editor-vue3";

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

const couldView = ref(["tree", "code", "form", "view"]);
const caseList = ref([]);
const projectOptions = ref([]);
const moduleOptions = ref([]);
const moduleShow = ref([]);
const moduleOptionsHandl = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    caseId: undefined,
    caseName: undefined,
    projectId: undefined,
    moduleId: undefined,
    status: undefined
  },
  rules: {
    caseName: [{ required: true, message: "用例名称不能为空", trigger: "blur" }],
    projectId: [{ required: true, message: "所属项目不能为空", trigger: "blur" }],
    moduleId: [{ required: true, message: "所属模块不能为空", trigger: "blur" }]
  }
});

const { queryParams, form, rules } = toRefs(data);

/** 查询用例列表 */
function getList() {
  loading.value = true;
  listCase(queryParams.value).then(response => {
    caseList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}

/** 查询项目列表 */
function getProjectSelect(){
  listProject(null).then(response =>{
    projectOptions.value = response.data;
  });
}

/** 查询模块列表 */
function getModuleSelect(){
  selectModulList(queryParams.value).then(response =>{
    moduleOptions.value = response.data;
  });
}

/** 查询所有模块信息，用于列表展示 */
function getModuleShow(){
  showModulList(null).then(response =>{
    moduleShow.value = response.data;
  });
}

/** 查询模块列表-新增、修改窗口 */
function getModuleSelectHandl(){
  selectModulList(form.value).then(response =>{
    moduleOptionsHandl.value = response.data;
  });
}


// 格式化项目名称的函数
function formatProject(row, column, cellValue ){
  // 假设每个debugtalk对象都有一个projectId属性，用于从其他地方获取项目名称
  return getProjectName(row.projectId); // getProjectName是一个根据projectId获取项目名称的函数
}

// 获取项目名称的函数（这里应该是你的实际逻辑）
function getProjectName(projectId){
  // 根据projectId从某个地方（例如另一个数组或API）获取项目名称
  for(const project of projectOptions.value) {
    if(projectId === project.projectId){
      return project.projectName;
    }
  }
}

function formatModule(row, column, cellValue){
  return getModuleName(row.moduleId);

}

function getModuleName(moduleId){
  for(const module of moduleShow.value){
    if(moduleId === module.moduleId){
      return module.moduleName;
    }
  }
}

/**重置查询条件所属模块下拉框*/
function resetModule(){
  queryParams.value.moduleId = undefined;
  getModuleSelect();
}

/**重置新增、修改窗口所属模块下拉框*/
function resetModuleHandl(){
  form.value.moduleId = undefined;
  getModuleSelectHandl();
}


/** 取消按钮 */
function cancel() {
  open.value = false;
  reset();
}
/** 表单重置 */
function reset() {
  form.value = {
    caseId: undefined,
    moduleId: undefined,
    projectId: undefined,
    caseName: undefined,
    request: undefined,
    notes: undefined,
    include: undefined,
    sort: 0,
    status: "0",
    remark: undefined
  };
  proxy.resetForm("postRef");
}
/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1;
  // getProjectSelect();
  // getModuleShow();
  getList();
}
/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}
/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.caseId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}
/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加用例";
}
/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const caseId = row.caseId || ids.value;
  getCase(caseId).then(response => {
    if (!response.data || Object.keys(response.data).length === 0){
      alert("未查到对应数据！");
      return;
    }
    form.value.projectId = response.data.projectId;
    getModuleSelectHandl();
    form.value = response.data;
    open.value = true;
    title.value = "修改用例";
  });
}
/** 提交按钮 */
function submitForm() {
  proxy.$refs["postRef"].validate(valid => {
    if (valid) {
      if (form.value.caseId != undefined) {
        updateCase(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addCase(form.value).then(response => {
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
  const caseIds = row.caseId || ids.value;
  proxy.$modal.confirm('是否确认删除用例ID为"' + caseIds + '"的数据项？').then(function() {
    return delCase(caseIds);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}
/** 导出按钮操作 */
function handleExport() {
  proxy.download("hrm/case/export", {
    ...queryParams.value
  }, `Case_${new Date().getTime()}.xlsx`);
}
getProjectSelect();
getModuleShow();
getList();
</script>
