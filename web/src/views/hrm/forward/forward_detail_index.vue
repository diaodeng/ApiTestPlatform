<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryDetailRef" :inline="true" v-show="showSearch">
      <el-form-item label="转发规则名称" prop="ruleName">
        <el-input
            v-model="queryParams.ruleDetailName"
            placeholder="请输入转发规则名称"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="源地址" prop="ruleName">
        <el-input
            v-model="queryParams.originUrl"
            placeholder="请输入转发规则源地址"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="转发规则目标地址" prop="ruleName">
        <el-input
            v-model="queryParams.targetUrl"
            placeholder="请输入转发规则目标地址"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="转发规则状态" clearable style="width: 100px">
          <el-option
              v-for="dict in StatusNewEnum"
              :key="dict.value"
              :label="dict.label"
              :value="dict.value"
          />
        </el-select>
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
      <el-table-column label="转发规则详情ID" prop="ruleDetailId" width="150px"/>
      <el-table-column label="转发规则详情名称" prop="ruleDetailName" width="auto" min-width="200px"/>
      <el-table-column label="匹配模式" align="center" prop="matchType" width="155px" min-width="200px">
        <template #default="scope">
          <TagEnum :options="Object.values(ForwardRuleMatchTypeEnum)" :value="[scope.row.matchType]"/>
        </template>

      </el-table-column>
      <el-table-column label="源地址" prop="originUrl" width="auto" min-width="200px"/>
      <el-table-column label="目标地址" prop="targetUrl" width="auto" min-width="200px"/>
      <el-table-column label="状态" align="center" prop="status" width="110px" min-width="100px">
        <template #default="scope">
          <TagSelector v-model:selected-value="scope.row.status"
                       :options="Object.values(StatusNewEnum)"
                       selector-width="85px"
                       :source-data="scope.row"
                       @selectChanged="changeStatus"
          ></TagSelector>
        </template>
      </el-table-column>
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
    <el-dialog :title="title + ' >> ' + currentRuleDetailId + form?.ruleDetailName"
               v-model="showDetailDialog" append-to-body destroy-on-close>
      <el-container style="height: 100%">
        <el-main style="max-height: calc(100vh - 95px);">

          <el-form>
            <el-form-item label="规则名称：">
              <el-input v-model="form.ruleDetailName"></el-input>
            </el-form-item>
            <el-form-item label="匹配模式：">
              <TagSelector v-model:selected-value="form.matchType"
                           :options="Object.values(ForwardRuleMatchTypeEnum)"
                           selector-width="130px"
              ></TagSelector>
            </el-form-item>

            <el-form-item label="待转地址：">
              <el-input v-model="form.originUrl"></el-input>
            </el-form-item>
            <el-form-item label="替换内容：">
              <TagSelector v-model:selected-value="form.replaceContent"
                           :options="Object.values(ForwardReplaceContentEnum)"
                           selector-width="130px"
              ></TagSelector>
            </el-form-item>
            <el-form-item label="目标地址：">
              <el-input v-model="form.targetUrl"></el-input>
            </el-form-item>
            <el-form-item label="简要描述：">
              <el-input v-model="form.simpleDesc"></el-input>
            </el-form-item>
          </el-form>
        </el-main>
        <el-footer>
          <div class="dialog-footer">
            <el-button @click="showDetailDialog = false">取消</el-button>
            <el-button type="primary" @click="saveForwardRules">保存</el-button>
          </div>

        </el-footer>
      </el-container>
    </el-dialog>


    <el-dialog :title="copyRulesInfo?.ruleDetailName" v-model="copyDialog" append-to-body destroy-on-close>
      <el-container style="height: 100%">
        <el-main style="max-height: calc(100vh - 95px);">
          <el-input placeholder="请输入转发规则名称" v-model="copyRulesInfo.ruleDetailName">
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
import * as forwardDetailApi from "@/api/hrm/forward_rule_detail.js";
import TagSelector from "@/components/hrm/common/tag-selector.vue";
import {initForwardRulesDetailFormData} from "@/components/hrm/data-template";
import {ElMessage, ElMessageBox} from "element-plus";
import {Remove} from "@element-plus/icons-vue";
import {ForwardReplaceContentEnum, ForwardRuleMatchTypeEnum, StatusNewEnum} from "@/components/hrm/enum.js";
import DictTag from "@/components/DictTag/index.vue";
import TagEnum from "@/components/hrm/common/tag-enum.vue"

const {proxy} = getCurrentInstance();

const props = defineProps(["rulesId"])

const ruleList = ref([]);
const showSearch = ref(true);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");

const checkedIds = ref([]);

const showDetailDialog = ref(false);

const copyDialog = ref(false);
const copyRulesInfo = ref(initForwardRulesDetailFormData);

const queryParams = toRef({
  pageNum: 1,
  pageSize: 10,
  ruleId: props.rulesId,
  ruleDetailId: undefined,
  ruleDetailName: undefined,
  originUrl: undefined,
  targetUrl: undefined,
  status: undefined,
});

const form = ref(initForwardRulesDetailFormData);
const loading = ref({
  page: false,
  edite: false,
  copy: false
});


const currentRuleDetailId = computed(() => {
  return form.value.ruleDetailId ? '【' + form.value.ruleDetailId + '】' : ""
})


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
    ruleDetailId: copyRulesInfo.value.ruleDetailId,
    ruleDetailName: copyRulesInfo.value.ruleDetailName,
  }
  forwardDetailApi.copyRules(data).then(response => {
    ElMessage.success("复制成功");
  }).finally(() => {
    copyDialog.value = false;
  });
}


/** 查询列表 */
function getList() {
  if (!queryParams.value.ruleId) {
    console.log("没有数据ID");
    return
  }
  loading.value.page = true;
  forwardDetailApi.list(queryParams.value).then(response => {
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
  proxy.resetForm("queryDetailRef");
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
  form.value = JSON.parse(JSON.stringify(initForwardRulesDetailFormData));
  showDetailDialog.value = true;
}

/** 修改按钮操作 */
function handleUpdate(row) {
  loading.value.edite = true;
  const ruleId = row.ruleDetailId || checkedIds.value;
  forwardDetailApi.getDetail(ruleId).then(response => {
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
  return

  forwardDetailApi.changeRulesStatus({ruleDetailId: row.ruleDetailId, status: row.status}).then((response) => {
    ElMessage.success("修改成功");
  }).catch(() => {
    ElMessage.error("修改失败");
  });
}

/** 删除按钮操作 */
function handleDelete(row) {
  const ruleIds = row.ruleDetailId ? [row.ruleDetailId] : checkedIds.value;
  proxy.$modal.confirm('是否确认删除ID为"' + ruleIds + '"的数据项？').then(function () {
    return forwardDetailApi.delRules({"ruleDetailId": ruleIds});
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {
  });
}

// 新增、编辑详情页相关
// >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

function saveForwardRules() {
  loading.value.edite = true;

  if (form.value.ruleDetailId) {
    forwardDetailApi.updateRules(form.value).then((response) => {
      ElMessage.success(response.msg);
      showDetailDialog.value = false;
    }).catch((e) => {
      ElMessage.error("操作失败：" + e);
    }).finally(() => {
      loading.value.edite = false;
    });
  } else {
    forwardDetailApi.addRules(form.value).then((response) => {
      ElMessage.success(response.msg);
      showDetailDialog.value = false;
    }).catch((e) => {
      ElMessage.error("操作失败：" + e);
    }).finally(() => {
      loading.value.edite = false;
    });
  }


}

// <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<


onMounted(() => {
  form.value.ruleId = props.rulesId;
  getList();
})

</script>
