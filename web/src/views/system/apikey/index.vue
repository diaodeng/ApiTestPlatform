<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="80px">
      <el-form-item label="Key 名称" prop="keyName">
        <el-input
          v-model="queryParams.keyName"
          placeholder="请输入 API Key 名称"
          clearable
          style="width: 260px"
          @keyup.enter="handleQuery"
        />
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
          v-hasPermi="['system:apikey:add']"
        >
          新增
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="apiKeyList">
      <el-table-column label="ID" align="center" prop="apiKeyId" width="90" />
      <el-table-column label="名称" align="center" prop="keyName" min-width="180" :show-overflow-tooltip="true" />
      <el-table-column label="Key 标识" align="center" prop="keyPrefix" min-width="220" :show-overflow-tooltip="true" />
      <el-table-column label="状态" align="center" width="120">
        <template #default="scope">
          <el-tag v-if="!scope.row.isExpired" type="success">生效中</el-tag>
          <el-tag v-else-if="scope.row.expireReason === '手动过期'" type="danger">已手动过期</el-tag>
          <el-tag v-else type="warning">已到期</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="有效期" align="center" min-width="180">
        <template #default="scope">
          <span>{{ scope.row.neverExpire ? "永久有效" : (scope.row.expireTime ? parseTime(scope.row.expireTime) : "-") }}</span>
        </template>
      </el-table-column>
      <el-table-column label="权限范围" align="center" min-width="280" :show-overflow-tooltip="true">
        <template #default="scope">
          <span>{{ formatPermissionNames(scope.row.permissionCodes) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="最后使用" align="center" min-width="180">
        <template #default="scope">
          <span>{{ scope.row.lastUsedTime ? parseTime(scope.row.lastUsedTime) : "-" }}</span>
        </template>
      </el-table-column>
      <el-table-column label="最后使用IP" align="center" prop="lastUsedIp" width="140">
        <template #default="scope">
          <span>{{ scope.row.lastUsedIp || "-" }}</span>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" align="center" prop="createTime" min-width="180">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="备注" align="center" prop="remark" min-width="180" :show-overflow-tooltip="true" />
      <el-table-column label="操作" align="center" width="300" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button
            link
            type="primary"
            icon="View"
            @click="handleViewDetail(scope.row)"
            v-hasPermi="['system:apikey:query']"
          >
            详细
          </el-button>
          <el-button
            link
            type="primary"
            icon="Key"
            @click="handleOpenReveal(scope.row)"
            v-hasPermi="['system:apikey:view']"
          >
            查看密钥
          </el-button>
          <el-button
            v-if="!scope.row.isExpired"
            link
            type="warning"
            icon="SwitchButton"
            @click="handleExpire(scope.row)"
            v-hasPermi="['system:apikey:expire']"
          >
            手动过期
          </el-button>
          <el-button
            link
            type="danger"
            icon="Delete"
            @click="handleDelete(scope.row)"
            v-hasPermi="['system:apikey:remove']"
          >
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

    <el-dialog :title="dialogTitle" v-model="formOpen" width="760px" append-to-body>
      <el-form ref="apiKeyRef" :model="form" :rules="rules" label-width="96px">
        <el-form-item label="Key 名称" prop="keyName">
          <el-input v-model="form.keyName" maxlength="64" placeholder="请输入 API Key 名称" />
        </el-form-item>
        <el-form-item label="权限范围" prop="permissionCodes">
          <el-select
            v-model="form.permissionCodes"
            multiple
            filterable
            clearable
            collapse-tags
            collapse-tags-tooltip
            :loading="permissionLoading"
            placeholder="不选择则默认继承当前账号全部可授权权限"
            style="width: 100%"
          >
            <el-option
              v-for="item in permissionOptions"
              :key="item.perm"
              :label="formatPermissionOption(item)"
              :value="item.perm"
            />
          </el-select>
          <div class="form-tip">不选择单独权限时，默认继承当前账号全部可授权接口权限。</div>
        </el-form-item>
        <el-form-item label="永久有效" prop="neverExpire">
          <el-switch v-model="form.neverExpire" />
        </el-form-item>
        <el-form-item label="失效时间" prop="expireTime">
          <el-date-picker
            v-model="form.expireTime"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="请选择失效时间"
            clearable
            style="width: 100%"
            :disabled="form.neverExpire"
          />
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input v-model="form.remark" type="textarea" :rows="4" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="submitForm">确 定</el-button>
          <el-button @click="cancelForm">取 消</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog title="API Key 详细" v-model="detailOpen" width="860px" append-to-body>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="ID">{{ detailData.apiKeyId || "-" }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ detailData.keyName || "-" }}</el-descriptions-item>
        <el-descriptions-item label="Key 标识">{{ detailData.keyPrefix || "-" }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag v-if="!detailData.isExpired" type="success">生效中</el-tag>
          <el-tag v-else-if="detailData.expireReason === '手动过期'" type="danger">已手动过期</el-tag>
          <el-tag v-else type="warning">已到期</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="有效期">
          {{ detailData.neverExpire ? "永久有效" : (detailData.expireTime ? parseTime(detailData.expireTime) : "-") }}
        </el-descriptions-item>
        <el-descriptions-item label="最后使用时间">
          {{ detailData.lastUsedTime ? parseTime(detailData.lastUsedTime) : "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="最后使用IP">{{ detailData.lastUsedIp || "-" }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detailData.createTime ? parseTime(detailData.createTime) : "-" }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ detailData.updateTime ? parseTime(detailData.updateTime) : "-" }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ detailData.remark || "-" }}</el-descriptions-item>
        <el-descriptions-item label="权限范围" :span="2">
          <div v-if="detailData.permissionCodes?.length" class="permission-tag-list">
            <el-tag
              v-for="item in detailData.permissionCodes"
              :key="item"
              class="permission-tag"
              type="info"
            >
              {{ getPermissionName(item) }}
            </el-tag>
          </div>
          <span v-else>-</span>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="detailOpen = false">关 闭</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog title="查看 API Key" v-model="authOpen" width="520px" append-to-body>
      <el-form ref="authRef" :model="authForm" :rules="authRules" label-width="90px">
        <el-form-item label="账号" prop="userName">
          <el-input v-model="authForm.userName" placeholder="请输入账号" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="authForm.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" :loading="revealLoading" @click="submitReveal">确 定</el-button>
          <el-button @click="cancelReveal">取 消</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog :title="secretDialogTitle" v-model="secretOpen" width="760px" append-to-body>
      <div class="secret-desc">
        API Key 明文请妥善保管，泄露后任何持有者都可在权限范围内调用接口。
      </div>
      <div class="secret-name">名称：{{ secretData.keyName || "-" }}</div>
      <el-input
        :model-value="secretData.apiKey"
        type="textarea"
        :rows="4"
        readonly
        class="secret-input"
      />
      <div class="secret-actions">
        <el-button type="primary" icon="CopyDocument" @click="copySecretKey">复制明文</el-button>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="secretOpen = false">关 闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="ApiKey">
import useUserStore from "@/store/modules/user";
import {
  addApiKey,
  delApiKey,
  expireApiKey,
  getApiKey,
  listApiKey,
  listApiKeyPermissionOptions,
  viewApiKey,
} from "@/api/system/apikey";

const { proxy } = getCurrentInstance();
const userStore = useUserStore();

const apiKeyList = ref([]);
const loading = ref(true);
const showSearch = ref(true);
const total = ref(0);
const formOpen = ref(false);
const detailOpen = ref(false);
const authOpen = ref(false);
const secretOpen = ref(false);
const dialogTitle = ref("");
const secretDialogTitle = ref("API Key 明文");
const permissionLoading = ref(false);
const revealLoading = ref(false);
const permissionOptions = ref([]);
const detailData = ref({});
const secretData = ref({
  keyName: "",
  apiKey: "",
});
const revealTarget = ref(null);

const permissionNameMap = computed(() => {
  const result = {};
  permissionOptions.value.forEach(item => {
    result[item.perm] = formatPermissionOption(item);
  });
  return result;
});

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyName: undefined,
  },
  form: {},
  authForm: {
    userName: userStore.name || "",
    password: "",
  },
  rules: {
    keyName: [{ required: true, message: "API Key 名称不能为空", trigger: "blur" }],
  },
  authRules: {
    userName: [{ required: true, message: "账号不能为空", trigger: "blur" }],
    password: [{ required: true, message: "密码不能为空", trigger: "blur" }],
  },
});

const { queryParams, form, authForm, rules, authRules } = toRefs(data);

watch(
  () => form.value.neverExpire,
  value => {
    if (value) {
      form.value.expireTime = undefined;
    }
  }
);

function getList() {
  loading.value = true;
  listApiKey(queryParams.value)
    .then(response => {
      apiKeyList.value = response.rows || [];
      total.value = response.total || 0;
    })
    .finally(() => {
      loading.value = false;
    });
}

function loadPermissionOptions(force = false) {
  if (!force && permissionOptions.value.length) {
    return Promise.resolve(permissionOptions.value);
  }
  permissionLoading.value = true;
  return listApiKeyPermissionOptions()
    .then(response => {
      permissionOptions.value = response.data || [];
      return permissionOptions.value;
    })
    .finally(() => {
      permissionLoading.value = false;
    });
}

function resetForm() {
  form.value = {
    keyName: undefined,
    permissionCodes: [],
    neverExpire: true,
    expireTime: undefined,
    remark: undefined,
  };
  proxy.resetForm("apiKeyRef");
}

function resetAuthForm() {
  authForm.value = {
    userName: userStore.name || "",
    password: "",
  };
  proxy.resetForm("authRef");
}

function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}

function handleAdd() {
  resetForm();
  dialogTitle.value = "新增 API Key";
  formOpen.value = true;
  loadPermissionOptions();
}

function cancelForm() {
  formOpen.value = false;
  resetForm();
}

function submitForm() {
  proxy.$refs["apiKeyRef"].validate(valid => {
    if (!valid) {
      return;
    }
    if (!form.value.neverExpire && !form.value.expireTime) {
      proxy.$modal.msgError("请选择 API Key 失效时间");
      return;
    }
    addApiKey(form.value).then(response => {
      proxy.$modal.msgSuccess("新增成功");
      formOpen.value = false;
      getList();
      openSecretDialog(response.data, "新建 API Key 成功");
    });
  });
}

function handleViewDetail(row) {
  loadPermissionOptions();
  getApiKey(row.apiKeyId).then(response => {
    detailData.value = response.data || {};
    detailOpen.value = true;
  });
}

function handleOpenReveal(row) {
  revealTarget.value = row;
  resetAuthForm();
  authOpen.value = true;
}

function cancelReveal() {
  authOpen.value = false;
  revealTarget.value = null;
  resetAuthForm();
}

function submitReveal() {
  if (!revealTarget.value?.apiKeyId) {
    proxy.$modal.msgError("未找到要查看的 API Key");
    return;
  }
  proxy.$refs["authRef"].validate(valid => {
    if (!valid) {
      return;
    }
    revealLoading.value = true;
    viewApiKey(revealTarget.value.apiKeyId, authForm.value)
      .then(response => {
        authOpen.value = false;
        openSecretDialog(response.data, "API Key 明文");
      })
      .finally(() => {
        revealLoading.value = false;
      });
  });
}

function handleExpire(row) {
  proxy.$modal.confirm(`是否确认手动过期 API Key「${row.keyName}」？`).then(function () {
    return expireApiKey(row.apiKeyId);
  }).then(() => {
    proxy.$modal.msgSuccess("操作成功");
    getList();
    if (detailOpen.value && detailData.value.apiKeyId === row.apiKeyId) {
      handleViewDetail(row);
    }
  }).catch(() => {});
}

function handleDelete(row) {
  proxy.$modal.confirm(`是否确认删除 API Key「${row.keyName}」？`).then(function () {
    return delApiKey(row.apiKeyId);
  }).then(() => {
    proxy.$modal.msgSuccess("删除成功");
    getList();
  }).catch(() => {});
}

function formatPermissionOption(item) {
  if (!item) {
    return "-";
  }
  return item.parentName ? `${item.parentName} / ${item.name} (${item.perm})` : `${item.name} (${item.perm})`;
}

function getPermissionName(permissionCode) {
  return permissionNameMap.value[permissionCode] || permissionCode;
}

function formatPermissionNames(permissionCodes) {
  if (!permissionCodes?.length) {
    return "默认继承全部可授权权限";
  }
  return permissionCodes.map(item => getPermissionName(item)).join("；");
}

function openSecretDialog(secretInfo, title = "API Key 明文") {
  secretDialogTitle.value = title;
  secretData.value = {
    keyName: secretInfo?.keyName || "",
    apiKey: secretInfo?.apiKey || "",
  };
  secretOpen.value = true;
}

async function copySecretKey() {
  if (!secretData.value.apiKey) {
    proxy.$modal.msgError("没有可复制的 API Key");
    return;
  }

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(secretData.value.apiKey);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = secretData.value.apiKey;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "absolute";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
    }
    proxy.$modal.msgSuccess("复制成功");
  } catch (error) {
    proxy.$modal.msgError("复制失败，请手动复制");
  }
}

getList();
loadPermissionOptions();
</script>

<style scoped>
.form-tip {
  margin-top: 8px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.permission-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.permission-tag {
  margin: 0;
}

.secret-desc {
  margin-bottom: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.secret-name {
  margin-bottom: 12px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.secret-input :deep(textarea) {
  font-family: "Consolas", "Monaco", monospace;
}

.secret-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
