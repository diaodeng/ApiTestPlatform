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
            v-hasPermi="['hrm:project:add']"
        >新增
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="warning" icon="CaretRight" @click="runTest"
                   v-hasPermi="['hrm:case:run']" title="运行">
          执行
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table
        border
        v-if="refreshTable"
        v-loading="loading"
        :data="projectList"
        row-key="projectId"
        table-layout="fixed"
        :default-expand-all="isExpandAll"
        @selection-change="handleSelectionChange"
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
      <el-table-column label="创建时间" align="center" prop="createTime" class-name="small-padding fixed-width" width="150">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" prop="updateTime" class-name="small-padding fixed-width" width="150">
        <template #default="scope">
          <span>{{ parseTime(scope.row.updateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" class-name="small-padding fixed-width" fixed="right" width="120">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['hrm:project:edit']" title="修改">
          </el-button>
          <el-button link type="warning" icon="CaretRight" v-loading="loading" @click="runTest(scope.row)"
                     v-hasPermi="['hrm:case:run']" title="运行">
          </el-button>
          <!--               <el-button link type="primary" icon="Plus" @click="handleAdd(scope.row)" v-hasPermi="['hrm:project:add']">新增</el-button>-->
          <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)"
                     v-hasPermi="['hrm:project:remove']" title="修改">
          </el-button>
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

    <!-- 添加或修改项目对话框 -->
    <el-dialog :title="title" v-model="open" width="800px" append-to-body>
      <el-form ref="projectRef" :model="form" :rules="rules" label-width="90px">
        <el-row>
          <el-col :span="12">
            <el-form-item label="项目名称" prop="projectName">
              <el-input v-model="form.projectName" placeholder="请输入项目名称"/>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="显示排序" prop="orderNum">
              <el-input-number v-model="form.orderNum" controls-position="right" :min="0"/>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目负责人" prop="responsibleName">
              <el-input v-model="form.responsibleName" placeholder="请输入负责人" maxlength="20"/>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="测试负责人" prop="testUser">
              <el-input v-model="form.testUser" placeholder="请输入测试负责人" maxlength="25"/>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="开发负责人" prop="devUser">
              <el-input v-model="form.devUser" placeholder="请输入开发负责人" maxlength="20"/>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发布应用" prop="publishApp">
              <el-input v-model="form.publishApp" placeholder="请输入发布应用" maxlength="20"/>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="简要描述" prop="simpleDesc">
              <el-input type="textarea" :rows="4" v-model="form.simpleDesc" placeholder="简要描述" maxlength="100"/>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="其他信息" prop="otherDesc">
              <el-input type="textarea" :rows="4" v-model="form.otherDesc" placeholder="其他信息" maxlength="100"/>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目状态">
              <el-radio-group v-model="form.status">
                <el-radio
                    v-for="dict in qtr_data_status"
                    :key="dict.value"
                    :label="dict.value"
                >{{ dict.label }}
                </el-radio>
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

    <!-- 运行用例对话框 -->
    <RunDialog v-model:dialog-visible="runDialogShow" :run-type="RunTypeEnum.project" :run-ids="runIds"></RunDialog>
  </div>
</template>

<script setup name="project">
import {ElMessageBox} from "element-plus";
import {listProject, getProject, delProject, addProject, updateProject} from "@/api/hrm/project.js";
import {HrmDataTypeEnum, RunTypeEnum} from "@/components/hrm/enum.js";
import RunDialog from "@/components/hrm/common/run_dialog.vue";

const {proxy} = getCurrentInstance();
const {qtr_data_status} = proxy.useDict("qtr_data_status");

const projectList = ref([]);
const total = ref(0);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const title = ref("");
const isExpandAll = ref(true);
const refreshTable = ref(true);

const runDialogShow = ref(false);
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
    loading.value = false;
  });
}

function handleSelectionChange(selection) {
  runIds.value = selection.map(item => item.projectId);
}



/** 取消按钮 */
function cancel() {
  open.value = false;
  reset();
}

/** 表单重置 */
function reset() {
  form.value = {
    projectId: undefined,
    projectName: undefined,
    orderNum: 0,
    simpleDesc: undefined,
    status: "0"
  };
  proxy.resetForm("projectRef");
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
  listProject().then(response => {
    projectOptions.value = proxy.handleTree(response.data, "projectId");
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
  getProject(row.projectId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改项目";
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["projectRef"].validate(valid => {
    if (valid) {
      if (form.value.projectId != undefined) {
        updateProject(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addProject(form.value).then(response => {
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
  proxy.$modal.confirm('是否确认删除名称为"' + row.projectName + '"的数据项?').then(function () {
    return delProject(row.projectId);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {
  });
}

function runTest(row) {
  if (row && "projectId" in row && row.projectId) {
    runIds.value = [row.projectId];
  }
  if (!runIds.value || runIds.value.length === 0) {
    ElMessageBox.alert('请选择要运行的项目', "提示！", {type: 'warning'});
    return;
  }

  runDialogShow.value = true;

}

getList();
</script>
