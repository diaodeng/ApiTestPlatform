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
      <el-col :span="1.5">
        <el-button
            type="primary"
            plain
            icon="Plus"
            @click="handleAdd"
            v-hasPermi="['qtr:suite:add']"
        >新增
        </el-button>
        <el-button type="warning" icon="CaretRight" @click="runTest"
                   v-hasPermi="['hrm:case:run']" title="运行">执行
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table
        border
        v-if="refreshTable"
        v-loading="loading"
        :data="suiteList"
        row-key="suiteId"
        :default-expand-all="isExpandAll"
        @selection-change="handleSelectionChange"
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
      <el-table-column label="操作" align="center" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['qtr:suite:edit']">
            修改
          </el-button>
          <el-button link type="primary" icon="Tools" @click="handleConfigSuite(scope.row)"
                     v-hasPermi="['qtr:suite:edit']">
            配置
          </el-button>
          <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)"
                     v-hasPermi="['qtr:suite:remove']">
            删除
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
    <!-- 添加或修改套件对话框 -->
    <el-dialog :title="title" v-model="open" append-to-body>
      <el-form ref="suiteRef" :model="form" :rules="rules" label-width="80px">
        <el-row>
          <el-col :span="12">
            <el-form-item label="套件名称" prop="suiteName">
              <el-input v-model="form.suiteName" placeholder="请输入套件名称"/>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="显示排序" prop="orderNum">
              <el-input-number v-model="form.orderNum" controls-position="right" :min="0"/>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="套件描述" prop="simpleDesc">
              <el-input v-model="form.simpleDesc" placeholder="请输入描述" maxlength="400"/>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="套件状态">
              <el-radio-group v-model="form.status">
                <el-radio
                    v-for="dict in qtr_data_status"
                    :key="dict.value * 1"
                    :value="dict.value * 1"
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
    <RunDialog v-model:dialog-visible="runDialogShow" :run-type="RunTypeEnum.suite" :run-ids="runIds"></RunDialog>

    <!-- 配置套件详情对话框 -->
    <SuiteDetailDialog :form-datas="form"
                       v-model:open-suite-detail-dialog="openSuiteDetail"
                       :title="SuiteTitle"
                       :suiteId="configSuiteId"
                       show-close
                       :destroy-on-close="true">
    </SuiteDetailDialog>
  </div>
</template>

<script setup name="Suite">
import {addSuite, delSuite, getSuite, listSuite, updateSuite} from "@/api/qtr/suite";
import {ElMessageBox} from "element-plus";
import {RunTypeEnum} from "@/components/hrm/enum.js";
import RunDialog from "@/components/hrm/common/run_dialog.vue";
import SuiteDetailDialog from "@/components/qtr/suite-detail-dialog.vue";


const {proxy} = getCurrentInstance();
const {qtr_data_status} = proxy.useDict("qtr_data_status");

const suiteList = ref([]);
const open = ref(false);
const openSuiteDetail = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const title = ref("");
const configSuiteId = ref(0);
const isExpandAll = ref(true);
const refreshTable = ref(true);
const total = ref(0);
const runDialogShow = ref(false);
const runIds = ref([]);

const data = reactive({
  form: {},
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

const {queryParams, form, rules} = toRefs(data);

const SuiteTitle = computed(() => {
  return title.value
});

/** 查询套件列表 */
function getList() {
  loading.value = true;
  listSuite(queryParams.value).then(response => {
    suiteList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}

function handleSelectionChange(selection) {
  runIds.value = selection.map(item => item.suiteId);
}


/** 取消按钮 */
function cancel() {
  open.value = false;
  reset();
}

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
  proxy.resetForm("queryRef");
  handleQuery();
}

/** 新增按钮操作 */
function handleAdd(row) {
  reset();
  open.value = true;
  title.value = "添加套件";
}

/** 配置按钮操作 */
function handleConfigSuite(row) {
  const suiteId = row.suiteId;
  getSuite(suiteId).then(response => {
    if (!response.data || Object.keys(response.data).length === 0) {
      alert("未查到对应数据！");
      return;
    }
    form.value = response.data;
    openSuiteDetail.value = true;
    configSuiteId.value = row.suiteId;
    title.value = "配置套件" + "【" + response.data['suiteName'] + "】";
  });
}

/** 运行套件 */
function handleRun(row) {
  // TODO

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
  getSuite(row.suiteId).then(response => {
    if (!response.data || Object.keys(response.data).length === 0) {
      alert("未查到对应数据！");
      return;
    }
    form.value = response.data;
    open.value = true;
    title.value = "修改套件";
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["suiteRef"].validate(valid => {
    if (valid) {
      if (form.value.suiteId != undefined) {
        updateSuite(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addSuite(form.value).then(response => {
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
  proxy.$modal.confirm('是否确认删除名称为"' + row.suiteName + '"的数据项?').then(function () {
    return delSuite(row.suiteId);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {
  });
}

function runTest(row) {
  if (row && "suiteId" in row && row.suiteId) {
    runIds.value = [row.suiteId];
  }
  if (!runIds.value || runIds.value.length === 0) {
    ElMessageBox.alert('请选择要运行的套件', "提示！", {type: 'warning'});
    return;
  }

  runDialogShow.value = true;

}

getList();
</script>
