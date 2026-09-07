<template>
  <el-dialog
    v-model="open"
    :title="form.profileId ? '编辑采集服务' : '新增采集服务'"
    width="80%"
    append-to-body
  >
    <el-form :model="form" label-width="130px">
      <el-form-item label="服务名称" required>
        <el-input v-model="form.profileName" placeholder="例如：生产 vmagent" maxlength="64" />
      </el-form-item>
      <el-form-item label="启用推送">
        <el-switch v-model="form.enabled" />
        <span class="unit-text">关闭后指标停止推送，Grafana 面板会暂时无数据</span>
      </el-form-item>
      <el-form-item label="推送地址" :required="form.enabled">
        <el-input
          v-model="form.pushUrl"
          placeholder="例如：https://vmagent.example.com/api/v1/import/prometheus"
        />
      </el-form-item>
      <el-form-item label="认证用户">
        <el-input v-model="form.authUser" placeholder="接收端 Basic 认证用户，可留空" />
      </el-form-item>
      <el-form-item label="认证密码">
        <el-input
          v-model="form.authPassword"
          type="password"
          show-password
          :placeholder="passwordPlaceholder"
          autocomplete="new-password"
        />
        <span class="unit-text">加密存储，编辑时留空表示不修改旧密码</span>
      </el-form-item>
      <el-row :gutter="16">
        <el-col :span="8">
          <el-form-item label="job 标签">
            <el-input v-model="form.jobLabel" placeholder="QTR" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="instance 标签">
            <el-input v-model="form.instanceLabel" placeholder="TEST_ENV" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="machine 标签">
            <el-input v-model="form.machineLabel" placeholder="留空使用默认分组" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="16">
        <el-col :span="8">
          <el-form-item label="推送间隔(秒)">
            <el-input-number
              v-model="form.intervalSeconds"
              :min="1"
              :max="3600"
              controls-position="right"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="批次条数">
            <el-input-number
              v-model="form.batchSize"
              :min="1"
              :max="10000"
              controls-position="right"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="超时(秒)">
            <el-input-number
              v-model="form.timeoutSeconds"
              :min="1"
              :max="60"
              controls-position="right"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="扩展指标">
        <el-switch v-model="form.extendedEnabled" />
        <span class="unit-text">发送进程内存、cgroup 与任务级指标（更多细节，样本量更大）</span>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" :rows="2" maxlength="500" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="open = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup name="MetricsCollectorDialog">
  import { addMetricsCollector, updateMetricsCollector } from '@/api/system/metricsCollector';

  const { proxy } = getCurrentInstance();
  const emit = defineEmits(['saved']);
  const open = ref(false);
  const saving = ref(false);
  const passwordPlaceholder = ref('未设置');

  const emptyForm = () => ({
    profileId: '',
    profileName: '',
    enabled: false,
    pushUrl: '',
    authUser: '',
    authPassword: '',
    jobLabel: 'QTR',
    instanceLabel: 'TEST_ENV',
    machineLabel: '',
    intervalSeconds: 5,
    batchSize: 100,
    timeoutSeconds: 10,
    extendedEnabled: false,
    remark: '',
  });
  const form = reactive(emptyForm());

  function openDialog(row) {
    Object.assign(form, emptyForm(), row || {});
    // 密码不回显，只在用户主动输入时修改
    form.authPassword = '';
    passwordPlaceholder.value = row?.authPasswordSet ? '已设置，留空表示不修改' : '未设置';
    open.value = true;
  }

  function save() {
    if (!form.profileName?.trim()) {
      proxy.$modal.msgError('请填写采集服务名称');
      return;
    }
    if (form.enabled && !form.pushUrl?.trim()) {
      proxy.$modal.msgError('启用推送时必须填写推送地址');
      return;
    }
    saving.value = true;
    const request = form.profileId
      ? updateMetricsCollector(form.profileId, form)
      : addMetricsCollector(form);
    request
      .then(() => {
        proxy.$modal.msgSuccess('保存成功，配置将在 5 秒内热生效');
        open.value = false;
        emit('saved');
      })
      .finally(() => {
        saving.value = false;
      });
  }

  defineExpose({ open: openDialog });
</script>

<style scoped>
  .unit-text {
    color: var(--el-text-color-secondary);
    font-size: 12px;
    margin-left: 8px;
  }
</style>
