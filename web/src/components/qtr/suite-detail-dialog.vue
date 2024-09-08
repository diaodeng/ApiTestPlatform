<template>
  <el-dialog fullscreen :title='title' v-model="openSuiteDetailDialog" append-to-body destroy-on-close>
    <div class="app-container">
      <el-form :model="queryParams" ref="queryRef_detail" :inline="true" v-show="showSearch">
        <el-form-item label="套件名称" prop="suiteName">
          <el-input
              v-model="queryParams.suiteName"
              placeholder="请输入套件名称"
              clearable
              style="width: 200px"
              @keyup.enter="handleQuery"
          />
        </el-form-item>
        <el-form-item label="用例ID" prop="caseId">
          <el-input
              v-model="queryParams.caseId"
              placeholder="请输入用例ID"
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
        <el-form-item label="用例状态" prop="status">
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

      <!--    <el-row :gutter="10" class="mb8">-->
      <!--      <el-col :span="1.5">-->
      <!--        <el-button-->
      <!--            type="primary"-->
      <!--            plain-->
      <!--            icon="Plus"-->
      <!--            @click="handleAdd"-->
      <!--            v-hasPermi="['qtr:suite:add']"-->
      <!--        >新增-->
      <!--        </el-button>-->
      <!--        <el-button type="warning" icon="CaretRight" @click="runTest"-->
      <!--                   v-hasPermi="['hrm:case:run']" title="运行">执行-->
      <!--        </el-button>-->
      <!--      </el-col>-->
      <!--      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>-->
      <!--    </el-row>-->

      <!--    <el-table-->
      <!--        border-->
      <!--        v-if="refreshTable"-->
      <!--        v-loading="loading"-->
      <!--        :data="suiteList"-->
      <!--        row-key="suiteId"-->
      <!--        :default-expand-all="isExpandAll"-->
      <!--        @selection-change="handleSelectionChange"-->
      <!--    >-->
      <!--      <el-table-column type="selection" width="55" align="center"/>-->
      <!--      <el-table-column prop="suiteId" label="ID" width="160"></el-table-column>-->
      <!--      <el-table-column prop="suiteName" label="套件名称" width="200"></el-table-column>\-->
      <!--      <el-table-column prop="orderNum" label="排序" width="200"></el-table-column>-->
      <!--      <el-table-column prop="status" label="状态" width="100">-->
      <!--        <template #default="scope">-->
      <!--          <dict-tag :options="sys_normal_disable" :value="scope.row.status"/>-->
      <!--        </template>-->
      <!--      </el-table-column>-->
      <!--      <el-table-column label="创建时间" align="center" prop="createTime" class-name="small-padding fixed-width">-->
      <!--        <template #default="scope">-->
      <!--          <span>{{ parseTime(scope.row.createTime) }}</span>-->
      <!--        </template>-->
      <!--      </el-table-column>-->
      <!--      <el-table-column label="更新时间" align="center" prop="updateTime" class-name="small-padding fixed-width">-->
      <!--        <template #default="scope">-->
      <!--          <span>{{ parseTime(scope.row.updateTime) }}</span>-->
      <!--        </template>-->
      <!--      </el-table-column>-->
      <!--      <el-table-column label="操作" align="center" class-name="small-padding fixed-width">-->
      <!--        <template #default="scope">-->
      <!--          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['qtr:suite:edit']">-->
      <!--            修改-->
      <!--          </el-button>-->
      <!--          <el-button link type="primary" icon="Tools" @click="handleConfigSuite(scope.row)" v-hasPermi="['qtr:suite:edit']">-->
      <!--            配置-->
      <!--          </el-button>-->
      <!--          <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['qtr:suite:remove']">-->
      <!--            删除-->
      <!--          </el-button>-->
      <!--        </template>-->
      <!--      </el-table-column>-->
      <!--    </el-table>-->
    </div>
  </el-dialog>
</template>

<script setup>

const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const showSearch = ref(true);

const data = reactive({
  form: {},
  queryParams: {
    suiteName: undefined,
    projectId: undefined,
    projectName: undefined,
    caseId: undefined,
    caseName: undefined,
    status: undefined
  },
  rules: {
    suiteName: [{required: true, message: "套件名称不能为空", trigger: "blur"}],
    orderNum: [{required: true, message: "显示排序不能为空", trigger: "blur"}]
  },
});

const openSuiteDetailDialog = defineModel("openSuiteDetailDialog");
const {queryParams, form, rules} = toRefs(data);

/** 表单重置 */
function reset() {
  form.value = {
    suiteId: undefined,
    suiteName: undefined,
    orderNum: 0,
    simpleDesc: undefined,
    status: "0"
  };
  proxy.resetForm("suiteRef");
}

/** 搜索按钮操作 */
function handleQuery() {
  getList();
}

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef_detail");
  handleQuery();
}

/** 新增按钮操作 */
function handleAdd(row) {
  reset();
  open.value = true;
  title.value = "添加套件";
}

/** 提交按钮 */
// function submitForm() {
//   proxy.$refs["postRef"].validate(valid => {
//     if (valid) {
//       const caseData = formData.value
//       caseData.request.config.name = caseData.caseName;
//       caseData.request.config.result = {}
//       for (let step of caseData.request.teststeps) {
//         step.result = {}
//       }
//
//       if (caseData.caseId !== undefined) {
//         updateCase(caseData).then(response => {
//           proxy.$modal.msgSuccess("修改成功");
//           openCaseEditDialog.value = false;
//           // getList();
//         });
//       } else {
//         addCase(caseData).then(response => {
//           proxy.$modal.msgSuccess("新增成功");
//           openCaseEditDialog.value = false;
//           // getList();
//         });
//       }
//     }
//   });
// }


</script>

<style scoped lang="scss">

</style>
