<template>
   <div class="app-container">
      <el-table
          border
         v-if="refreshTable"
         v-loading="loading"
         :data="debugtalkList"
         row-key="debugtalkId"
         :default-expand-all="isExpandAll">
         <el-table-column prop="debugtalkId" label="ID" width="120"></el-table-column>
         <el-table-column label="项目ID" width="140" prop="projectId" align="center"></el-table-column>
         <el-table-column label="所属项目" width="260" :formatter="formatProject" align="center"></el-table-column>
         <el-table-column align="center" label="DebugTalk" width="260">
           <template #default="scope">
             <el-button link type="primary" @click="handleUpdate(scope.row)" v-hasPermi="['hrm:debugtalk:edit']">debugtalk.py</el-button>
           </template>
         </el-table-column>
         <el-table-column prop="status" label="状态" align="center" width="120">
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
      </el-table>

      <!-- 添加或修改项目对话框 -->
      <el-dialog :title="title" v-model="open" width="800px" append-to-body>
         <el-form ref="debugtalkRef" :model="form" :rules="rules" label-width="5px">
           <el-form-item>

                <MonacoEditor v-model="debugtalk" language="javascript" />

            </el-form-item>
         </el-form>
         <template #footer>
            <div class="dialog-footer">
               <el-button type="primary" @click="submitForm">确 定</el-button>
               <el-button @click="cancel">取 消</el-button>
            </div>
         </template>
      </el-dialog>
   </div>
<!--  <div><el-button @click="dialogVisible = true">打开对话框</el-button>-->
<!--      <el-dialog-->
<!--        :visible.sync="dialogVisible"-->
<!--        :fullscreen="isFullscreen"-->
<!--        @fullscreenchange="handleFullscreenChange"-->
<!--        custom-class="my-custom-dialog"-->
<!--      >-->
<!--        <div slot="title" class="dialog-header">-->
<!--          <span>对话框标题</span>-->
<!--          <el-button icon="el-icon-full-screen" @click="toggleFullscreen" class="fullscreen-btn"></el-button>-->
<!--        </div>-->
<!--        <div>-->
<!--          <p>对话框内容...</p>-->
<!--        </div>-->
<!--        <span slot="footer" class="dialog-footer">-->
<!--          <el-button @click="dialogVisible = false">取消</el-button>-->
<!--          <el-button type="primary" @click="dialogVisible = false">确定</el-button>-->
<!--        </span>-->
<!--      </el-dialog></div>-->
</template>

<script setup name="debugtalk">
import { listDebugTalk, getDebugTalk, delDebugTalk, addDebugTalk, updateDebugTalk } from "@/api/hrm/debugtalk.js";
import { listProject } from "@/api/hrm/project.js";
import MonacoEditor from './MonacoEditor.vue';

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

const debugtalkList = ref([]);
const projectList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const title = ref("");
const isExpandAll = ref(true);
const refreshTable = ref(true);
const projectId = ref();
const debugtalk = ref();

const dialogVisible = false;
const isFullscreen = false;

const data = reactive({
  form: {
    debugtalk: ''
  },
  queryParams: {
    debugtalkId: undefined,
    status: undefined
  },
  rules: {
    orderNum: [{ required: true, message: "显示排序不能为空", trigger: "blur" }]
  },
});

const { queryParams, form, rules } = toRefs(data);

function toggleFullscreen() {
  this.isFullscreen = !this.isFullscreen;
}
function handleFullscreenChange(isFullscreen) {
  this.isFullscreen = isFullscreen;
}

getProjectList();

/** 查询DebugTalk列表 */
function getList() {
  loading.value = true;
  listDebugTalk(queryParams.value).then(response => {
    debugtalkList.value = proxy.handleTree(response.data, "debugtalkId");
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
    debugtalkId: undefined,
    orderNum: 0,
    debugtalk: undefined,
    status: "0"
  };
  proxy.resetForm("debugtalkRef");
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
  listDebugTalk().then(response => {
    debugtalkOptions.value = proxy.handleTree(response.data, "debugtalkId");
  });
  open.value = true;
  title.value = "添加项目";
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
  getDebugTalk(row.debugtalkId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "DebugTalk";
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["debugtalkRef"].validate(valid => {
    if (valid) {
      if (form.value.debugtalkId != undefined) {
        updateDebugTalk(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addDebugTalk(form.value).then(response => {
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
  proxy.$modal.confirm('是否确认删除名称为"' + row.projectName + '"的数据项?').then(function() {
    return delProject(row.projectId);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}

// 格式化项目名称的函数
function formatProject(row, column, cellValue ){
  // 假设每个debugtalk对象都有一个projectId属性，用于从其他地方获取项目名称
  return getProjectName(row.projectId); // getProjectName是一个根据projectId获取项目名称的函数
}

// 获取项目名称的函数（这里应该是你的实际逻辑）
function getProjectName(projectId){
  // 根据projectId从某个地方（例如另一个数组或API）获取项目名称
  for (const project of projectList.value) {
    if(projectId === project.projectId){
      return project.projectName;
    }
  }
}
/** 查询项目列表 */
function getProjectList() {
  loading.value = true;
  listProject(queryParams.value).then(response => {
    projectList.value = response.data;
    loading.value = false;
  });
}

getList();
</script>
<style scoped>
.my-custom-dialog .el-dialog__header {
  padding-right: 40px; /* 留出空间给全屏按钮 */
}

.fullscreen-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 1;
}
</style>