<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="所属项目" prop="projectId">
        <el-select v-model="queryParams.projectId" placeholder="请选择" @change="resetModule" clearable
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
        <el-select v-model="queryParams.moduleId" placeholder="请选择" clearable style="width: 150px">
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
        <el-select v-model="queryParams.status" placeholder="用例状态" clearable style="width: 100px">
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
        <el-button type="default" icon="Refresh" @click="resetQuery">重置</el-button>
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
            v-hasPermi="['hrm:case:edit']"
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
            v-hasPermi="['hrm:case:remove']"
        >删除
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
            type="warning"
            plain
            icon="Download"
            @click="handleExport"
            v-hasPermi="['hrm:case:export']"
        >导出
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="caseList"
              @selection-change="handleSelectionChange"
              border
    >
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column label="用例ID" align="center" prop="caseId"/>
      <el-table-column label="用例名称" align="center" prop="caseName"/>
      <el-table-column label="所属项目" align="center" prop="projectName"/>
      <el-table-column label="所属模块" align="center" prop="moduleName"/>
      <!--         <el-table-column label="用例排序" align="center" prop="sort" />-->
      <el-table-column label="状态" align="center" prop="status">
        <template #default="scope">
          <dict-tag :options="sys_normal_disable" :value="scope.row.status"/>
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
          <el-button link type="primary" icon="Histogram" @click="showHistory(scope.row)" v-hasPermi="['hrm:case:history']"
                     title="执行历史">

          </el-button>
          <el-button link type="primary" icon="View" @click="handleUpdate(scope.row)" v-hasPermi="['hrm:case:detail']"
                     title="查看">

          </el-button>
          <el-button link type="warning" icon="Edit" v-loading="loading" @click="handleUpdate(scope.row)"
                     v-hasPermi="['hrm:case:edit']" title="编辑">
          </el-button>
          <el-button link type="warning" icon="CaretRight" v-loading="loading" @click="runTest(scope.row)"
                     v-hasPermi="['hrm:case:edit']" title="运行">
          </el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)"
                     v-hasPermi="['hrm:case:remove']" title="删除">
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

    <!-- 添加或修改用例对话框 -->
    <el-dialog fullscreen :title="title" v-model="open" append-to-body>
      <el-form ref="postRef" :model="form" :rules="rules" label-width="100px" style="height: 100%">
        <el-container style="height: 100%">
          <el-header height="20px" border="2px" style="border-bottom-color: #97a8be;text-align: right">
            用例修改
            <el-button-group>
              <el-button type="primary" @click="submitForm" v-hasPermi="['hrm:case:edit']">确定</el-button>
              <el-button type="primary" @click="debugForm" v-hasPermi="['hrm:case:debug']">执行
              </el-button>
              <el-select placeholder="Select" v-model="selectedEnv" style="width: 115px">
                <el-option
                    v-for="option in envOptions"
                    :key="option.envId"
                    :label="option.envName"
                    :value="option.envId">
                </el-option>
              </el-select>
            </el-button-group>

          </el-header>
          <el-main style="max-height: calc(100vh - 95px);">
            <!--            <div>{{ form }}</div>-->
            <el-tabs type="border-card" v-model="activeCaseName" style="height: 100%;">
              <el-tab-pane label="config" name="caseConfig">
                <el-tabs type="" v-model="activeMessageName">
                  <el-tab-pane label="messages" name="caseMessages">
                    <el-form-item label="用例名称" prop="caseName">
                      <el-input v-model="form.caseName" placeholder="请输入用例名称" clearable/>
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
                    <el-form-item label="注释" prop="notes">
                      <el-input v-model="form.notes" placeholder="注释"/>
                    </el-form-item>
                    <el-form-item label="用例顺序" prop="sort">
                      <el-input-number v-model="form.sort" controls-position="right" :min="0"/>
                    </el-form-item>
                    <el-form-item label="用例状态" prop="status">
                      <el-radio-group v-model="form.status">
                        <el-radio
                            v-for="dict in sys_normal_disable"
                            :key="dict.value"
                            :label="dict.label"
                            :value="dict.value"
                        ></el-radio>
                      </el-radio-group>
                    </el-form-item>
                    <el-form-item label="备注" prop="remark">
                      <el-input v-model="form.remark" type="textarea" placeholder="请输入内容"/>
                    </el-form-item>
                  </el-tab-pane>
                  <el-tab-pane label="headers" name="caseHeaders">
                    <TableHeaders v-model="form.request.config.headers"></TableHeaders>
                  </el-tab-pane>
                  <el-tab-pane label="variables/parameters/hooks" name="caseVph">
                    variables
                    <TableVariables v-model="form.request.config.variables"></TableVariables>
                    parameters
                    <TableVariables v-model="form.request.config.parameters"></TableVariables>
                    setup_hooks
                    <TableHooks v-model="form.request.config.setup_hooks"></TableHooks>
                    teardown_hooks
                    <TableHooks v-model="form.request.config.teardown_hooks"></TableHooks>
                  </el-tab-pane>
                  <el-tab-pane label="thinktime" name="caseThinktime">
                    <div>
                      <el-input
                          v-model="form.request.config.think_time.limit"
                          style="max-width: 600px"
                          placeholder="Please input"
                      >
                        <template #prepend>thinktime</template>
                      </el-input>
                    </div>
                  </el-tab-pane>
                </el-tabs>
              </el-tab-pane>
              <el-tab-pane label="teststeps" name="caseSteps">
                <el-container>
                  <el-main>
                    <TestStep v-model:test-steps-data="form.request.teststeps"
                              v-model:response-data="responseData"></TestStep>
                  </el-main>
                </el-container>

              </el-tab-pane>
            </el-tabs>
          </el-main>
        </el-container>


      </el-form>
    </el-dialog>


    <el-dialog fullscreen :title="form.case_name" v-model="history" append-to-body>
      <el-container style="height: 100%">
        <!--          <el-header height="20px" border="2px" style="border-bottom-color: #97a8be;text-align: right">-->
        <!--          </el-header>-->
        <el-main style="max-height: calc(100vh - 95px);">
          <RunDetail :run-id="currentRunId"></RunDetail>
        </el-main>
      </el-container>
    </el-dialog>

  </div>
</template>

<script setup name="Case">
import {randomString} from "@/utils/tools.js"
import {addCase, debugCase, delCase, getCase, listCase, updateCase} from "@/api/hrm/case";
import {testRun} from "@/api/hrm/run_detail.js";
import {selectModulList, showModulList} from "@/api/hrm/module";
import {listEnv} from "@/api/hrm/env";
import {listProject} from "@/api/hrm/project";
import TableHeaders from '../../../components/hrm/table-headers.vue';
import TableVariables from '../../../components/hrm/table-variables.vue';
import TableHooks from '../../../components/hrm/table-hooks.vue';
import TestStep from "@/components/hrm/case/step.vue"
import {initCaseFormData} from "@/components/hrm/data-template.js";
import RunDetail from '@/components/hrm/common/run-detail.vue';
import { runModelEnum } from "@/components/hrm/enum.js";
// import JsonEditorVue from "json-editor-vue3";


const {proxy} = getCurrentInstance();
const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
const {sys_request_method} = proxy.useDict("sys_request_method");
const {hrm_data_type} = proxy.useDict("hrm_data_type");


provide("hrm_data_type", hrm_data_type);

const couldView = ref(["tree", "code", "form", "view"]);
const caseList = ref([]);
const projectOptions = ref([]);
const moduleOptions = ref([]);
const envOptions = ref([]);
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
const selectedEnv = ref("");
const responseData = ref("");

const history = ref(false);
const currentRunId = ref();

const activeCaseName = ref("caseConfig")
const activeMessageName = ref("caseMessages")


const data = reactive({
  // form: {},
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
    caseName: [{required: true, message: "用例名称不能为空", trigger: "blur"}],
    projectId: [{required: true, message: "所属项目不能为空", trigger: "blur"}],
    moduleId: [{required: true, message: "所属模块不能为空", trigger: "blur"}]
  }
});

const {queryParams, rules} = toRefs(data);
const form = ref({
  include: {},
  request: JSON.parse(JSON.stringify(initCaseFormData))
});


function runTest(row) {
  let data = {
    ids: [row.caseId],
    runModel: runModelEnum.case,
    env: 1746540889545728
  }
  testRun(data).then(response => {
    alert('执行完成');
  })
}


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
function getProjectSelect() {
  listProject(null).then(response => {
    projectOptions.value = response.data;
  });
}

/** 查询模块列表 */
function getModuleSelect() {
  selectModulList(queryParams.value).then(response => {
    moduleOptions.value = response.data;
  });
}

/** 查询所有模块信息，用于列表展示 */
function getModuleShow() {
  showModulList(null).then(response => {
    moduleShow.value = response.data;
  });
}

/** 查询模块列表-新增、修改窗口 */
function getModuleSelectHandl() {
  selectModulList(form.value).then(response => {
    moduleOptionsHandl.value = response.data;
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

function formatModule(row, column, cellValue) {
  return getModuleName(row.moduleId);

}

function getModuleName(moduleId) {
  for (const module of moduleShow.value) {
    if (moduleId === module.moduleId) {
      return module.moduleName;
    }
  }
}

/**重置查询条件所属模块下拉框*/
function resetModule() {
  queryParams.value.moduleId = undefined;
  getModuleSelect();
}

/**重置新增、修改窗口所属模块下拉框*/
function resetModuleHandl() {
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
  activeCaseName.value = "caseConfig"
  activeMessageName.value = "caseMessages"
  // activeRequestName.value = "stepRequest"
  // activeRequestDetailName.value = "requestHeader"
  // activeTestStepName.value = 0
  form.value = {
    caseId: undefined,
    moduleId: undefined,
    projectId: undefined,
    caseName: undefined,
    notes: undefined,
    sort: 0,
    status: "0",
    remark: undefined,
    include: {},
    request: JSON.parse(JSON.stringify(initCaseFormData))
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
    if (!response.data || Object.keys(response.data).length === 0) {
      alert("未查到对应数据！");
      return;
    }
    // form.value.projectId = response.data.projectId;
    form.value = response.data;
    getModuleSelectHandl();

    open.value = true;
    title.value = "修改用例";
  });
}

function showHistory(row) {
  const caseId = row.caseId || ids.value;
  currentRunId.value = caseId;
  history.value = true;
}

function debugForm() {
  proxy.$refs["postRef"].validate(valid => {
    if (valid) {
      const caseData = form.value;
      caseData.request.config.name = caseData.caseName;
      const req_data = {
        "env": selectedEnv.value,
        "runType": 3,
        "caseData": caseData
      }
      debugCase(req_data).then(response => {
        proxy.$modal.msgSuccess(response.msg);
        responseData.value = response.data.log
        // open.value = false;
        // getList();
      });

    }
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["postRef"].validate(valid => {
    if (valid) {
      const caseData = form.value
      caseData.request.config.name = caseData.caseName;
      if (caseData.caseId != undefined) {
        updateCase(caseData).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addCase(caseData).then(response => {
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
  proxy.$modal.confirm('是否确认删除用例ID为"' + caseIds + '"的数据项？').then(function () {
    return delCase(caseIds);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {
  });
}

/** 导出按钮操作 */
function handleExport() {
  proxy.download("hrm/case/export", {
    ...queryParams.value
  }, `Case_${new Date().getTime()}.xlsx`);
}


function envList() {
  listEnv().then(response => {
    envOptions.value = response.data;
  });
}

getProjectSelect();
getModuleShow();
getList();
envList();
</script>
