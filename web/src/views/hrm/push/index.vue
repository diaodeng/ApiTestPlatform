<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="推送配置ID" prop="pushId">
        <el-input
            v-model="queryParams.pushId"
            placeholder="请输入推送配置Id"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="推送配置名称" prop="name">
        <el-input
            v-model="queryParams.name"
            placeholder="请输入推送配置名称"
            clearable
            style="width: 200px"
            @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="推送类型" prop="type">
        <el-select v-model="queryParams.type" placeholder="推送类型" clearable style="width: 100px">
          <el-option
              v-for="dict in qtr_push_type"
              :key="dict.value"
              :label="dict.label"
              :value="dict.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item v-if="false">
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
            v-hasPermi="['hrm:push:add']"
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
            v-hasPermi="['hrm:push:delete']"
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
      <el-table-column label="推送配置ID" prop="pushId" width="150px"/>
      <el-table-column label="推送配置名称" prop="name" width="auto" min-width="200px"/>
      <!--      <el-table-column label="推送类型" prop="type" width="auto" min-width="200px"/>-->
      <el-table-column label="推送类型" align="center" prop="status" width="120">

        <template #default="scope">
          <dict-tag :options="qtr_push_type" :value="scope.row.type"/>
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
                     v-hasPermi="['hrm:push:edite']" title="编辑">
          </el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)"
                     v-hasPermi="['hrm:push:delete']" title="删除">
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


    <!-- 新增或者编辑推送配置 -->
    <el-dialog :title="title + ' >> ' + currentRuleId + form?.name"
               v-model="showDetailDialog"
               append-to-body
               destroy-on-close
    >
      <el-container style="height: 100%">
        <el-main style="max-height: calc(100vh - 95px);">

          <el-form label-width="auto" :rules="rules" ref="pushInfoRef" :model="form">
            <el-form-item label="推送名称：" prop="name">
              <el-input v-model="form.name"></el-input>
            </el-form-item>

            <el-form-item label="状态：" prop="allowPush">
              <el-select v-model="form.allowPush" placeholder="状态" clearable style="width: 150px">
                <el-option
                    key="0"
                    label="停用"
                    :value="0"
                />
                <el-option
                    key="1"
                    label="启用"
                    :value="1"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="推送类型：" prop="configContent.type">
              <el-select v-model="form.type" placeholder="推送类型" clearable style="width: 150px">
                <el-option
                    v-for="dict in qtr_push_type"
                    :key="dict.value"
                    :label="dict.label"
                    :value=dict.value*1
                />
              </el-select>
            </el-form-item>

            <el-form-item label="机器人地址：" prop="configContent.url">
              <el-input v-model="form.configContent.url"></el-input>
            </el-form-item>

            <el-form-item label="KEY：">
              <el-input v-model="form.configContent.secret"></el-input>
            </el-form-item>

            <el-form-item label="消息内容：" prop="configContent.content">

              <template #label>
                <el-text>消息内容：</el-text>
                <el-popover
                    title="可以使用的变量"
                    placement="right-start"
                >
                  <el-text>变量格式：${变量名}
                    可使用变量：user，start_at，total_count，success_count，failed_count，report_id,report_name
                  </el-text>
                  <template #reference>
                    <el-icon>
                      <View/>
                    </el-icon>
                  </template>
                </el-popover>
              </template>
              <el-input type="textarea" v-model="form.configContent.content"></el-input>
            </el-form-item>

            <el-form-item label="简要描述：">
              <el-input type="textarea" v-model="form.desc"></el-input>
            </el-form-item>
          </el-form>
        </el-main>
        <el-footer>
          <div class="dialog-footer">
            <el-button @click="showDetailDialog = false">取消</el-button>
            <el-button type="primary" @click="saveForwardPush">保存</el-button>
          </div>

        </el-footer>
      </el-container>
    </el-dialog>


  </div>
</template>

<script setup name="Push">
import * as pushConfigApi from "@/api/hrm/push.js";
import TagSelector from "@/components/hrm/common/tag-selector.vue";
import {initPushConfig} from "@/components/hrm/data-template";
import {ElMessage, ElMessageBox} from "element-plus";
import {Remove, View} from "@element-plus/icons-vue";
import DictTag from "@/components/DictTag/index.vue";

const {proxy} = getCurrentInstance();
const {qtr_push_type} = proxy.useDict("qtr_push_type");

const pushInfoRef = ref(null);
const ruleList = ref([]);
const showSearch = ref(true);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");

const checkedIds = ref([]);

const showDetailDialog = ref(false);

const copyDialog = ref(false);
const copyPushInfo = ref(initPushConfig);

const queryParams = toRef({
  pageNum: 1,
  pageSize: 10,
  pushId: undefined,
  name: undefined,
  type: undefined,
  onlySelf: true
});

const form = ref(initPushConfig);
const loading = ref({
  page: false,
  edite: false,
  copy: false
});


const currentRuleId = computed(() => {
  return form.value.pushId ? '【' + form.value.pushId + '】' : "";
});

const rules = reactive({
  name: [
    {required: true, message: '请输入推送名称', trigger: 'blur'},
    // { min: 3, max: 5, message: 'Length should be 3 to 5', trigger: 'blur' },
  ],
  configContent: {
    url: [
      {required: true, message: '请输入飞书地址或者token', trigger: 'blur'}
    ],
    content: [
      {required: true, message: '请输入推送内容', trigger: 'blur'}
    ]
  }
})


/*
* 换起推送配置复制弹窗
* */
function showCopyDialog(data) {
  copyDialog.value = true;
  copyPushInfo.value = structuredClone(toValue(toRaw(data)));
}


/** 查询列表 */
function getList() {
  loading.value.page = true;
  pushConfigApi.listPushConfig(queryParams.value).then(response => {
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
  checkedIds.value = selection.map(item => item.pushId);
  single.value = selection.length !== 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {

  title.value = "添加推送配置";
  form.value = JSON.parse(JSON.stringify(initPushConfig));
  showDetailDialog.value = true;
}

/** 修改按钮操作 */
function handleUpdate(row) {
  loading.value.edite = true;
  const pushId = row.pushId || checkedIds.value;
  pushConfigApi.getPushConfig(pushId).then(response => {
    if (!response.data || Object.keys(response.data).length === 0) {
      ElMessage.warning("未查到对应数据！");
      return;
    }
    form.value = response.data;

    title.value = "修改推送配置";
    showDetailDialog.value = true;
  }).finally(() => {
    loading.value.edite = false;
  });
}


/** 删除按钮操作 */
function handleDelete(row) {
  const pushIds = row.pushId ? [row.pushId] : checkedIds.value;
  proxy.$modal.confirm('是否确认删除ID为"' + pushIds + '"的数据项？').then(function () {
    return pushConfigApi.delPushConfig({"pushIds": pushIds});
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {
  });
}

function saveForwardPush() {


  loading.value.edite = true;
  if (!pushInfoRef) {
    return;
  }
  pushInfoRef.value.validate((valid, fields) => {
    if (valid) {
      if (form.value.pushId) {
        pushConfigApi.updatePushConfig(form.value).then((response) => {
          ElMessage.success(response.msg);
          showDetailDialog.value = false;
        }).catch((e) => {
          ElMessage.error("操作失败：" + e);
        }).finally(() => {
          loading.value.edite = false;
        });
      } else {
        pushConfigApi.addPushConfig(form.value).then((response) => {
          ElMessage.success(response.msg);
          showDetailDialog.value = false;
        }).catch((e) => {
          ElMessage.error("操作失败：" + e);
        }).finally(() => {
          loading.value.edite = false;
        });
      }
    } else {
      console.log(valid, fields);
      ElMessage.error("请填写必要字段");
    }
  });


}

onMounted(() => {
  getList();
})

</script>
