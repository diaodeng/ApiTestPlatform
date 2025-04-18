<template>
  <div class="app-container">
    <ModuleTableQuery @select-change="handleSelectionChange" ref="moduleQueryViewRef">
      <template #table-tool>
        <el-col :span="1.5">
          <el-button
              type="primary"
              plain
              icon="Plus"
              @click="handleAdd"
              v-hasPermi="['hrm:module:add']"
          >新增
          </el-button>
        </el-col>
        <el-col :span="1.5">
          <el-button
              type="success"
              plain
              icon="Edit"
              :disabled="single"
              @click="handleUpdate"
              v-hasPermi="['hrm:module:edit']"
          >修改
          </el-button>
        </el-col>
        <el-col :span="1.5">
          <el-button
              type="danger"
              plain
              icon="Delete"
              :disabled="multiple"
              @click="handleDelete"
              v-hasPermi="['hrm:module:remove']"
          >删除
          </el-button>
        </el-col>
        <el-col :span="1.5">
          <el-button
              type="warning"
              plain
              icon="Download"
              @click="handleExport"
              v-hasPermi="['hrm:module:export']"
          >导出
          </el-button>
        </el-col>
        <el-col :span="1.5">
          <el-button type="warning" icon="CaretRight" @click="runTest"
                     v-hasPermi="['hrm:case:run']" title="运行">
            执行
          </el-button>
        </el-col>
      </template>
      <template #tableOperate="{scope}">
        <el-button link type="primary"
                   icon="Edit"
                   @click="handleUpdate(scope.row)"
                   :loading="loading"
                   v-hasPermi="['hrm:module:edit']">
        </el-button>
        <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)"
                   v-hasPermi="['hrm:module:remove']">
        </el-button>
      </template>
    </ModuleTableQuery>

    <!-- 添加或修改模块对话框 -->
    <el-dialog :title="title" v-model="open" width="600px" append-to-body>
      <el-form ref="postRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="模块名称" prop="moduleName">
          <el-input v-model="form.moduleName" placeholder="请输入模块名称"/>
        </el-form-item>
        <el-form-item label="所属项目" prop="projectId">
          <el-select v-model="form.projectId" placeholder="请选择">
            <el-option
                v-for="option in projectOptions"
                :key="option.projectId"
                :label="option.projectName"
                :value="option.projectId">
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="测试负责人" prop="testUser">
          <el-input v-model="form.testUser" placeholder="请输入测试负责人"/>
        </el-form-item>
        <el-form-item label="模块顺序" prop="sort">
          <el-input-number v-model="form.sort" controls-position="right" :min="0"/>
        </el-form-item>
        <el-form-item label="模块状态" prop="status">
          <el-radio-group v-model="form.status">
            <el-radio
                v-for="dict in qtr_data_status"
                :key="dict.value * 1"
                :value="dict.value * 1"
            >{{ dict.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="简要描述" prop="simpleDesc">
          <el-input type="textarea" :rows="4" v-model="form.simpleDesc" placeholder="简要描述" maxlength="100"/>
        </el-form-item>


        <el-form-item label="其他信息" prop="otherDesc">
          <el-input type="textarea" :rows="4" v-model="form.otherDesc" placeholder="其他信息" maxlength="100"/>
        </el-form-item>

        <el-form-item label="备注" prop="remark">
          <el-input v-model="form.remark" type="textarea" placeholder="请输入内容"/>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="submitForm">确 定</el-button>
          <el-button @click="cancel">取 消</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 运行用例对话框 -->
    <RunDialog v-model:dialog-visible="runDialogShow" :run-type="RunTypeEnum.module" :run-ids="runIds"></RunDialog>
  </div>
</template>

<script setup>
import {addModule, delModule, getModule, listModule, updateModule} from "@/api/hrm/module";
import {listProject} from "@/api/hrm/project";
import {RunTypeEnum, StatusNewEnum} from "@/components/hrm/enum.js";
import RunDialog from "@/components/hrm/common/run/run_dialog.vue";
import ModuleTableQuery from "@/components/hrm/util-data-table/module-table-query.vue";
import {ElMessageBox} from "element-plus";

const {proxy} = getCurrentInstance();
const {qtr_data_status} = proxy.useDict("qtr_data_status");

const moduleList = ref([]);
const projectOptions = ref([]);
const open = ref(false);
const loading = ref(false);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");

const runDialogShow = ref(false);
const runIds = ref([]);
const moduleQueryViewRef = ref(null);

const data = reactive({
  form: {
    testUser: undefined
  },
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

const {queryParams, form, rules} = toRefs(data);

/** 查询项目列表 */
function getProjectSelect() {
  listProject({isPage: false}).then(response => {
    projectOptions.value = response.data;
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
    moduleId: undefined,
    projectId: undefined,
    moduleName: undefined,
    sort: 0,
    status: StatusNewEnum.normal.value,
    remark: undefined
  };
  proxy.resetForm("postRef");
}


/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.moduleId);
  runIds.value = ids.value;
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加模块";
}

/** 修改按钮操作 */
function handleUpdate(row) {
  loading.value = true;
  reset();
  const moduleId = row.moduleId || ids.value;
  getModule(moduleId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改模块";
  }).finally(()=>{
    loading.value = false;
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["postRef"].validate(valid => {
    if (valid) {
      if (form.value.moduleId != undefined) {
        updateModule(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          moduleQueryViewRef.value.handleQuery();
        });
      } else {
        addModule(form.value).then(response => {
          proxy.$modal.msgSuccess("新增成功");
          open.value = false;
          moduleQueryViewRef.value.handleQuery();
        });
      }
    }
  });
}

/** 删除按钮操作 */
function handleDelete(row) {
  const moduleIds = row.moduleId || ids.value;
  proxy.$modal.confirm('是否确认删除模块编号为"' + moduleIds + '"的数据项？').then(function () {
    return delModule(moduleIds);
  }).then(() => {
    moduleQueryViewRef.value.handleQuery();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {
  });
}

/** 导出按钮操作 */
function handleExport() {
  proxy.download("hrm/module/export", {
    ...queryParams.value
  }, `Module_${new Date().getTime()}.xlsx`);
}

/** 运行用例 */
function runTest(row) {
  if (row && "moduleId" in row && row.moduleId) {
    runIds.value = [row.moduleId];
  }
  if (!runIds.value || runIds.value.length === 0) {
    ElMessageBox.alert('请选择要运行的模块', "提示！", {type: 'warning'});
    return;
  }
  runDialogShow.value = true;
}

onMounted(() => {
  getProjectSelect();
});

</script>
