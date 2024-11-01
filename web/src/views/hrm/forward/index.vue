<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="转发规则ID" prop="ruleId">
        <el-input
            v-model="queryParams.ruleId"
            placeholder="请输入转发规则Id"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="转发规则名称" prop="ruleName">
        <el-input
            v-model="queryParams.ruleName"
            placeholder="请输入转发规则名称"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="转发规则状态" clearable style="width: 100px">
          <el-option
              v-for="dict in qtr_rule_status"
              :key="dict.value"
              :label="dict.label"
              :value="dict.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="queryParams.onlySelf" @change="handleQuery">仅自己的数据</el-checkbox>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery" :loading="loading.page" :disabled="loading.page">
          搜索
        </el-button>
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
            v-hasPermi="['qtr:forwardRules:add']"
        >新增
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
            type="danger"
            plain
            icon="Delete"
            :disabled="multiple"
            @click="handleDelete"
            v-hasPermi="['qtr:forwardRules:remove']"
        >删除
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading.page" :data="ruleList"
              @selection-change="handleSelectionChange"
              border
              table-layout="fixed"
              max-height="calc(100vh - 280px)"
    >
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column label="转发规则ID" prop="ruleId" width="150px"/>
      <el-table-column label="转发规则名称" prop="ruleName" width="auto" min-width="200px"/>
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
      <el-table-column label="操作" width="170" align="center" class-name="small-padding fixed-width" fixed="right">
        <template #default="scope">

          <el-button link type="warning" icon="Edit" :loading="loading.edite" @click="handleUpdate(scope.row)"
                     v-hasPermi="['qtr:forwardRules:edit']" title="编辑">
          </el-button>
          <el-button link type="warning" icon="CopyDocument" :loading="loading.copy" @click="showCopyDialog(scope.row)"
                     v-hasPermi="['qtr:forwardRules:copy']" title="复制">
          </el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)"
                     v-hasPermi="['qtr:forwardRules:remove']" title="删除">
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


    <!-- 新增或者编辑转发规则 -->
    <el-dialog :title="title + ' >> ' + currentRuleId + form?.ruleName"
               v-model="showDetailDialog" append-to-body destroy-on-close>
      <el-container style="height: 100%">
        <el-main style="max-height: calc(100vh - 95px);">

          <el-form>
            <el-form-item label="规则名称：">
              <el-input v-model="form.ruleName"></el-input>
            </el-form-item>

            <el-button type="primary" @click="addOriginUrl" style="margin-bottom: 10px">增加源地址</el-button>
            <el-form-item label="待转地址：">
              <div style="width: 100%">
                <template v-for="(item,index) in form.originUrl">
                  <div style="display: flex;flex-direction: row;align-items: center;margin-bottom: 5px">
                    <el-input v-model="form.originUrl[index]" style="flex-grow: 1"></el-input>
                    <el-icon color="red" @click="removeOriginUrl(index)">
                      <Remove></Remove>
                    </el-icon>
                  </div>
                </template>
              </div>
            </el-form-item>
            <el-form-item label="目标地址：">
              <el-input v-model="form.targetUrl"></el-input>
            </el-form-item>
          </el-form>
        </el-main>
        <el-footer>
          <div class="dialog-footer">
            <el-button>取消</el-button>
            <el-button type="primary" @click="saveForwardRules">保存</el-button>
          </div>

        </el-footer>
      </el-container>
    </el-dialog>


    <el-dialog :title="copyRulesInfo?.ruleName" v-model="copyDialog" append-to-body destroy-on-close>
      <el-container style="height: 100%">
        <el-main style="max-height: calc(100vh - 95px);">
          <el-input placeholder="请输入转发规则名称" v-model="copyRulesInfo.ruleName">
            <template #suffix>
              <el-button @click="copyRulesHandle">保存</el-button>
            </template>
          </el-input>
        </el-main>
      </el-container>
    </el-dialog>

  </div>
</template>

<script setup name="Rules">
import * as forwardApi from "@/api/hrm/forward";
import TagSelector from "@/components/hrm/common/tag-selector.vue";
import {initForwardRulesFormData} from "@/components/hrm/data-template";
import {ElMessage, ElMessageBox} from "element-plus";
import {Remove} from "@element-plus/icons-vue";

const {proxy} = getCurrentInstance();


const ruleList = ref([]);
const showSearch = ref(true);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");

const checkedIds = ref([]);

const showDetailDialog = ref(false);
const currentRulesInfo = ref(null);

const copyDialog = ref(false);
const copyRulesInfo = ref(initForwardRulesFormData);

const queryParams = toRef({
  pageNum: 1,
  pageSize: 10,
  ruleId: undefined,
  ruleName: undefined,
  status: undefined,
  onlySelf: true
});

const form = ref(initForwardRulesFormData);
const loading = ref({
  page: false,
  edite: false,
  copy: false
});


const currentRuleId = computed(() => {
  return form.value.ruleId ? '【' + form.value.ruleId + '】' : ""
})


function lineStatusChange(selectValue, dataSource) {
  changeRulesStatus({ruleId: dataSource.ruleId, status: selectValue}).then((response) => {
    ElMessage.success("修改成功");
  }).catch(() => {
    ElMessage.error("修改失败");
  });
}

/*
* 换起转发规则复制弹窗
* */
function showCopyDialog(data) {
  copyDialog.value = true;
  copyRulesInfo.value = structuredClone(toValue(toRaw(data)));
}


/*
* 复制转发规则
* */
function copyRulesHandle() {
  copyDialog.value = true;
  let data = {
    ruleId: copyRulesInfo.value.ruleId,
    ruleName: copyRulesInfo.value.ruleName,
  }
  forwardApi.copyRules(data).then(response => {
    ElMessage.success("复制成功");
  }).finally(() => {
    copyDialog.value = false;
  });
}


/** 查询列表 */
function getList() {
  loading.value.page = true;
  forwardApi.list(queryParams.value).then(response => {
    ruleList.value = response.rows;
    total.value = response.total;
  }).finally(() => {
    loading.value.page = false;
  });
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

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  checkedIds.value = selection.map(item => item.ruleId);
  single.value = selection.length !== 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {

  title.value = "添加转发规则";
  form.value = JSON.parse(JSON.stringify(initForwardRulesFormData));
  showDetailDialog.value = true;
}

/** 修改按钮操作 */
function handleUpdate(row) {
  loading.value.edite = true;
  const ruleId = row.ruleId || checkedIds.value;
  forwardApi.getDetail(ruleId).then(response => {
    if (!response.data || Object.keys(response.data).length === 0) {
      ElMessage.warning("未查到对应数据！");
      return;
    }
    form.value = response.data;

    title.value = "修改转发规则";
    showDetailDialog.value = true;
  }).finally(() => {
    loading.value.edite = false;
  });
}

/*
* 更新转发规则状态
* */
function changeStatus(row) {

  forwardApi.changeRulesStatus({ruleId: row.ruleId, status: row.status}).then((response) => {
    ElMessage.success("修改成功");
  }).catch(() => {
    ElMessage.error("修改失败");
  });
}

/** 删除按钮操作 */
function handleDelete(row) {
  const ruleIds = row.ruleId ? [row.ruleId] : checkedIds.value;
  proxy.$modal.confirm('是否确认删除ID为"' + ruleIds + '"的数据项？').then(function () {
    return forwardApi.delRules({"ruleId": ruleIds});
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {
  });
}

// 新增、编辑详情页相关
// >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
function addOriginUrl() {
  form.value.originUrl.push("");
}

function removeOriginUrl(index) {
  if (form.value.originUrl.length <= 1) {
    form.value.originUrl[0] = "";
    return;
  }
  form.value.originUrl.splice(index, 1);
}

function saveForwardRules() {
  loading.value.edite = true;

  forwardApi.addRules(form.value).then((response) => {
    ElMessage.success(response.msg);
  }).catch((e) => {
    ElMessage.error("操作失败：" + e);
  }).finally(() => {
    loading.value.edite = false;
  });
}

// <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<


onMounted(() => {
  getList();
})

</script>
