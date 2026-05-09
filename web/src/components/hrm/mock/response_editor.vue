<template>
  <el-card class="response-editor-card">
    <template #header>
      <slot name="header">响应信息配置</slot>
    </template>

    <MockConditionEditor
      v-if="showCondition"
      v-model="responseData.responseCondition"
      :title="conditionTitle"
      :editable="!disabled"
      :add-button-text="conditionAddButtonText"
      empty-text="无条件（默认匹配）"
    />

    <el-card class="response-config-card">
      <template #header>
        响应配置
        <el-button
          v-if="!disabled"
          class="add-header-btn"
          @click="addHeader"
          type="primary"
          icon="Plus"
        >添加响应头</el-button>
      </template>

      <el-row :gutter="20">
        <el-col :span="6">
          <el-form-item label="状态码">
            <el-input-number v-model="responseData.statusCode" :min="0" :disabled="disabled" />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="延迟(ms)">
            <el-input-number
              v-model="responseData.delay"
              :min="0"
              :max="9999999"
              :disabled="disabled"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="响应头">
        <div
          v-for="(header, idx) in responseData.headersTemplate"
          :key="idx"
          class="header-item"
        >
          <el-input v-model="header.key" placeholder="Header名" style="width: 200px" :disabled="disabled" />
          <span style="margin: 0 10px">:</span>
          <el-input v-model="header.value" placeholder="Header值" style="width: 300px" :disabled="disabled" />
          <el-button v-if="!disabled" @click="removeHeader(idx)" type="danger" icon="Delete" />
        </div>
      </el-form-item>

      <el-form-item label="响应体模板">
        <template #label>
          <el-text>响应体模板</el-text>
          <el-popover v-if="showVariableGuide" title="可以使用的变量" placement="right-start" :width="700">
            <el-text><div v-pre>变量使用格式：{{变量名}}</div></el-text>
            <el-table :data="helpGridData">
              <el-table-column width="300" property="name" label="变量名" />
              <el-table-column width="150" property="desc" label="描述" />
              <el-table-column width="200" property="example" label="示例" />
            </el-table>
            <pre>
{
    'request': {
        'path': self.request.path_params,
        'method': self.request.method,
        'args': dict(self.request.query_params),
        'headers': dict(self.request.headers),
        "body": getattr(self.request, "body_data", None),
    },
    'random': {
        'int': lambda a, b: random.randint(a, b),
        'string': lambda l: ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=l))
    },
    'time': {
        'now': time.time(),
        'iso': datetime.datetime.now().isoformat(),
        'format': lambda format: datetime.datetime.now().strftime(format)
    },
    'uuid': str(uuid.uuid4())
}
            </pre>
            <template #reference>
              <el-text>
                <el-icon>
                  <View />
                </el-icon>
              </el-text>
            </template>
          </el-popover>
        </template>
        <el-alert v-if="showVariableGuide" type="info" show-icon style="margin-bottom: 10px">
          <div v-pre>
            支持模板语法： "{{ request.args.id }}" | "{{ random.int(1,100) }}" | "{{ time.iso }}"
          </div>
        </el-alert>
        <el-input
          v-model="responseData.bodyTemplate"
          type="textarea"
          :rows="10"
          :disabled="disabled"
          placeholder="响应内容（支持JSON/XML/Text）"
        />
      </el-form-item>
    </el-card>
  </el-card>
</template>

<script setup>
  import { computed, watchEffect } from 'vue';
  import { View } from '@element-plus/icons-vue';
  import MockConditionEditor from '@/components/hrm/mock/condition_editor.vue';

  const responseData = defineModel({ type: Object, required: true });

  const props = defineProps({
    disabled: { type: Boolean, default: false },
    showCondition: { type: Boolean, default: true },
    showVariableGuide: { type: Boolean, default: true },
    conditionTitle: { type: String, default: '响应匹配条件' },
    conditionAddButtonText: { type: String, default: '添加条件' },
    gridData: { type: Array, default: () => [] },
  });

  const defaultGridData = [
    {
      example: '/test',
      name: 'request.path',
      desc: '请求路径',
    },
    {
      example: '6',
      name: 'random.int(1,100)',
      desc: '随机数',
    },
    {
      example: 'ak',
      name: 'random.string(2)',
      desc: '随机字符串',
    },
    {
      example: '1767496712',
      name: 'time.now',
      desc: '当前时间',
    },
    {
      example: '20251230 121212',
      name: 'time.format("%y%m%d %H%M%S")',
      desc: '自定义时间格式',
    },
    {
      example: '1960446465473536',
      name: 'uuid',
      desc: 'uuid',
    },
  ];

  const helpGridData = computed(() => {
    if (Array.isArray(props.gridData) && props.gridData.length > 0) {
      return props.gridData;
    }
    return defaultGridData;
  });

  function addHeader() {
    if (!responseData.value || typeof responseData.value !== 'object') {
      return;
    }
    if (!Array.isArray(responseData.value.headersTemplate)) {
      responseData.value.headersTemplate = [];
    }
    responseData.value.headersTemplate.push({ key: '', value: '' });
  }

  function removeHeader(index) {
    if (!responseData.value || typeof responseData.value !== 'object') {
      return;
    }
    if (!Array.isArray(responseData.value.headersTemplate)) {
      responseData.value.headersTemplate = [];
      return;
    }
    responseData.value.headersTemplate.splice(index, 1);
  }

  watchEffect(() => {
    if (!responseData.value || typeof responseData.value !== 'object') {
      return;
    }
    if (!Array.isArray(responseData.value.responseCondition)) {
      responseData.value.responseCondition = [];
    }
    if (!Array.isArray(responseData.value.headersTemplate)) {
      responseData.value.headersTemplate = [];
    }
    if (responseData.value.statusCode === undefined || responseData.value.statusCode === null) {
      responseData.value.statusCode = 200;
    }
    if (responseData.value.delay === undefined || responseData.value.delay === null) {
      responseData.value.delay = 0;
    }
  });
</script>

<style scoped>
  .response-editor-card :deep(.el-card__header) {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .response-config-card {
    margin-top: 8px;
  }

  .add-header-btn {
    margin-left: auto;
  }

  .header-item {
    margin-bottom: 12px;
    padding: 8px;
    border: 1px solid #ebeef5;
    border-radius: 4px;
  }
</style>
