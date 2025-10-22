<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="AgentCode" prop="agentId">
        <el-input
            v-model="queryParams.agentCode"
            placeholder="请输入AgentCode"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="Agent名称" prop="agentName">
        <el-input
            v-model="queryParams.agentName"
            placeholder="请输入Agent名称"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
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
            type="danger"
            plain
            icon="Delete"
            :disabled="multiple"
            @click="handleDelete"
            v-hasPermi="['qtr:agent:remove']"
        >删除
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading.page" :data="pageDataList"
              @selection-change="handleSelectionChange"
              border
              table-layout="fixed"
              max-height="calc(100vh - 280px)"
    >
      <el-table-column type="selection" width="55" align="center"/>
      <el-table-column label="AgentID" prop="agentId" width="150px"/>
      <el-table-column label="Agent名称" prop="agentName" width="auto" min-width="200px"/>
      <el-table-column label="AgentCode" prop="agentCode" width="auto" min-width="200px"/>
      <el-table-column label="状态" prop="status" width="100px" min-width="100px">
        <template #default="scope">
          <TagEnum :options="Object.values(AgentStatusEnum)" :value="[scope.row.status]"/>
        </template>
      </el-table-column>
      <el-table-column label="在线时间" align="center" prop="onlineTime" class-name="small-padding fixed-width"
                       width="150px">
        <template #default="scope">
          <span>{{ parseTime(scope.row.onlineTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="离线时间" align="center" prop="offlineTime" class-name="small-padding fixed-width"
                       width="150px">
        <template #default="scope">
          <span>{{ parseTime(scope.row.offlineTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="170" align="center" class-name="small-padding fixed-width" fixed="right">
        <template #default="scope">
          <el-button link type="warning" icon="Edit" :loading="loading.edite" @click="handleUpdate(scope.row)"
                     v-hasPermi="['qtr:agent:edit']" title="编辑">
          </el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)"
                     v-hasPermi="['qtr:agent:remove']" title="删除">
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


    <!-- 新增或者编辑Agent -->
    <el-dialog :title="title + ' >> ' + currentAgentDialogTile"
               v-model="showDetailDialog" append-to-body destroy-on-close>
      <el-container style="height: 100%">
        <el-main style="max-height: calc(100vh - 95px);">

          <el-form>
            <el-form-item label="Agent名称：">
              <el-input v-model="form.agentName"></el-input>
            </el-form-item>
            <el-form-item label="AgentCode：">
              <el-text>{{ form.agentCode }}</el-text>
            </el-form-item>

            <el-form-item label="简要描述：">
              <el-input v-model="form.simpleDesc"></el-input>
            </el-form-item>
          </el-form>
        </el-main>
        <el-footer>
          <div class="dialog-footer">
            <el-button @click="showDetailDialog = false">取消</el-button>
            <el-button type="primary" @click="saveAgent">保存</el-button>
          </div>

        </el-footer>
      </el-container>
    </el-dialog>


    <el-dialog :title="copyAgentInfo?.agentName" v-model="copyDialog" append-to-body destroy-on-close>
      <el-container style="height: 100%">
        <el-main style="max-height: calc(100vh - 95px);">
          <el-input placeholder="请输入Agent名称" v-model="copyAgentInfo.agentName">
            <template #suffix>
              <el-button @click="copyAgentHandle">保存</el-button>
            </template>
          </el-input>
        </el-main>
      </el-container>
    </el-dialog>


  </div>
</template>

<script setup name="Agent">
import * as agentApi from "@/api/hrm/agent.js";
import {initAgentFormData} from "@/components/hrm/data-template";
import {ElMessage} from "element-plus";
import {AgentStatusEnum} from "@/components/hrm/enum.js";
import TagEnum from "@/components/hrm/common/tag-enum.vue";

const {proxy} = getCurrentInstance();


const pageDataList = ref([]);
const showSearch = ref(true);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");

const checkedIds = ref([]);

const showDetailDialog = ref(false);

const copyDialog = ref(false);
const copyAgentInfo = ref(initAgentFormData);

const queryParams = toRef({
  pageNum: 1,
  pageSize: 10,
  agentCode: undefined,
  agentName: undefined,
  status: undefined,
});

const form = ref(initAgentFormData);
const loading = ref({
  page: false,
  edite: false,
  copy: false
});


const currentAgentDialogTile = computed(() => {
  const dataId = form.value.agentId ? '【' + form.value.agentId + '】' : "";
  return dataId + form.value.agentName
});


/** 查询列表 */
function getList() {
  loading.value.page = true;
  agentApi.list(queryParams.value).then(response => {
    pageDataList.value = response.rows;
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
  checkedIds.value = selection.map(item => item.agentId);
  single.value = selection.length !== 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {

  title.value = "添加Agent";
  form.value = JSON.parse(JSON.stringify(initAgentFormData));
  showDetailDialog.value = true;
}

/** 修改按钮操作 */
function handleUpdate(row) {
  loading.value.edite = true;
  const agentId = row.agentId || checkedIds.value;
  agentApi.getDetail(agentId).then(response => {
    if (!response.data || Object.keys(response.data).length === 0) {
      ElMessage.warning("未查到对应数据！");
      return;
    }
    form.value = response.data;

    title.value = "修改Agent";
    showDetailDialog.value = true;
  }).finally(() => {
    loading.value.edite = false;
  });
}


/** 删除按钮操作 */
function handleDelete(row) {
  const agentIds = row.agentId ? [row.agentId] : checkedIds.value;
  proxy.$modal.confirm('是否确认删除ID为"' + agentIds + '"的数据项？').then(function () {
    return agentApi.delAgent({"agentIds": agentIds});
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {
  });
}

// 编辑详情页相关
// >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

function saveAgent() {
  loading.value.edite = true;

  agentApi.updateAgent(form.value).then((response) => {
    ElMessage.success(response.msg);
    showDetailDialog.value = false;
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
