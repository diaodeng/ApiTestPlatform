<template>
  <div class="steps-editor">
    <el-alert type="info" :closable="false" show-icon class="section-alert">
      <template #title>
        按顺序执行多个 HTTP 步骤（例如：账密登录 → 提取一次性 ticket → TOTP 验证 → 保存
        Cookie）。整条链共用会话 Cookie；<code>${step.N.变量}</code> 或
        <code>${step.步骤标识.变量}</code> 引用更早步骤的输出；条件不满足的步骤会被跳过。
      </template>
    </el-alert>

    <template v-if="enabled">
      <div class="steps-preview">
        <div class="steps-preview-title">认证流程预览</div>
        <ol class="steps-preview-list">
          <li v-for="(step, index) in steps" :key="index">
            <b>{{ step.name || `步骤${index + 1}` }}</b>
            <span class="steps-preview-request">{{ step.method }} {{ step.url || '(未填写地址)' }}</span>
            <span v-if="step.whenEnabled" class="steps-preview-note"
              >条件：{{ step.whenVariable || '?' }} {{ step.whenOperator }}
              {{ step.whenValue || '' }}</span
            >
            <span v-if="outputSummary(step)" class="steps-preview-note"
              >{{ step.persistOutputs ? '写回' : '输出' }}：{{ outputSummary(step) }}</span
            >
          </li>
          <li v-if="!steps.length" class="steps-preview-empty">尚未添加步骤</li>
        </ol>
      </div>

      <div v-for="(step, index) in steps" :key="index" class="step-card">
        <div class="step-card-header">
          <span class="step-card-title"
            >步骤 {{ index + 1 }}{{ step.name ? `：${step.name}` : '' }}</span
          >
          <el-button text size="small" :disabled="index === 0" @click="moveStep(index, -1)"
            >上移</el-button
          >
          <el-button
            text
            size="small"
            :disabled="index === steps.length - 1"
            @click="moveStep(index, 1)"
            >下移</el-button
          >
          <el-button text size="small" type="danger" @click="removeStep(index)">删除</el-button>
        </div>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="步骤名称">
              <el-input v-model="step.name" placeholder="如：账号密码登录" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="步骤标识">
              <el-input v-model="step.id" placeholder="可选，如 login，供 ${step.login.变量} 引用" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="请求体类型">
              <el-select v-model="step.bodyType" style="width: 100%">
                <el-option value="none" label="无请求体" />
                <el-option value="form" label="表单 (urlencoded)" />
                <el-option value="json" label="JSON" />
                <el-option value="multipart" label="表单 (multipart，自动生成 boundary)" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="7">
            <el-form-item label="请求方法">
              <el-select v-model="step.method" style="width: 100%">
                <el-option v-for="method in requestMethods" :key="method" :value="method" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="17">
            <el-form-item label="接口地址" required>
              <el-input v-model="step.url" placeholder="https://example.com/api/login" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="请求 Header">
          <el-input
            v-model="step.headersText"
            type="textarea"
            :rows="2"
            placeholder='JSON，例如 {"Content-Type":"application/x-www-form-urlencoded; charset=UTF-8"}；multipart 的 Content-Type 由系统生成，无需填写'
          />
        </el-form-item>
        <el-form-item v-if="step.bodyType !== 'none' && step.method !== 'GET'" label="请求体">
          <el-input
            v-model="step.bodyText"
            type="textarea"
            :rows="3"
            :placeholder="bodyPlaceholder(step)"
          />
        </el-form-item>

        <el-divider content-position="left">成功断言（本步独立校验）</el-divider>
        <div v-for="(assertion, assertionIndex) in step.assertions" :key="assertionIndex" class="assertion-row">
          <el-input v-model="assertion.source" placeholder="来源，如 json:code" />
          <el-select v-model="assertion.operator" style="width: 100%">
            <el-option v-for="item in assertionOperators" :key="item.value" :value="item.value" :label="item.label" />
          </el-select>
          <el-input v-model="assertion.expectedText" placeholder="期望值（JSON）" />
          <el-input v-model="assertion.message" placeholder="失败提示（可选）" />
          <el-button text type="danger" @click="step.assertions.splice(assertionIndex, 1)">删除</el-button>
        </div>
        <el-form-item label=" ">
          <el-button plain size="small" @click="step.assertions.push(emptyAssertion())">添加断言</el-button>
        </el-form-item>

        <el-divider content-position="left">输出变量</el-divider>
        <div v-for="(output, outputIndex) in step.outputs" :key="outputIndex" class="mapping-row">
          <el-input v-model="output.key" placeholder="变量名，如 ticket；写回时为 header.cookie.UYBFEWAEE 等" />
          <el-input v-model="output.source" placeholder="来源，如 json:result|url_query:ticket 或 cookie:UYBFEWAEE" />
          <el-button text type="danger" @click="step.outputs.splice(outputIndex, 1)">删除</el-button>
        </div>
        <el-form-item label=" ">
          <el-button plain size="small" @click="step.outputs.push(emptyOutput())">添加输出</el-button>
          <el-switch
            v-model="step.persistOutputs"
            active-text="写回凭证"
            style="margin-left: 12px"
          />
          <span v-if="step.persistOutputs" class="unit-text">输出按响应提取规则写入凭证密文</span>
          <span v-else class="unit-text">输出仅作为临时变量供后续步骤引用，不写入凭证</span>
        </el-form-item>

        <el-divider content-position="left">执行条件（可选）</el-divider>
        <el-row :gutter="16">
          <el-col :span="4">
            <el-form-item label="启用条件">
              <el-switch v-model="step.whenEnabled" />
            </el-form-item>
          </el-col>
          <template v-if="step.whenEnabled">
            <el-col :span="9">
              <el-form-item label="条件变量">
                <el-input v-model="step.whenVariable" placeholder="step.1.result / step.login.result / secret.otpSecret" />
              </el-form-item>
            </el-col>
            <el-col :span="5">
              <el-form-item label="操作符">
                <el-select v-model="step.whenOperator" style="width: 100%">
                  <el-option v-for="item in conditionOperators" :key="item.value" :value="item.value" :label="item.label" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="比较值">
                <el-input v-model="step.whenValue" placeholder="如 otp?" />
              </el-form-item>
            </el-col>
          </template>
        </el-row>
      </div>

      <el-form-item label=" ">
        <el-button plain :icon="Plus" :disabled="steps.length >= maxSteps" @click="addStep()"
          >添加认证步骤</el-button
        >
        <span class="unit-text">最多 {{ maxSteps }} 步；至少一个步骤需要开启"写回凭证"</span>
      </el-form-item>
    </template>
  </div>
</template>

<script setup>
  import { Plus } from '@element-plus/icons-vue';

  const props = defineProps({
    /* 认证链用途标签：登录 / 刷新，用于提示文案。 */
    kindLabel: { type: String, default: '登录' },
  });

  const enabled = defineModel('enabled', { type: Boolean, default: false });

  const requestMethods = ['GET', 'POST', 'PUT', 'PATCH'];
  const maxSteps = 5;
  const assertionOperators = [
    { value: 'equals', label: '等于' },
    { value: 'not_equals', label: '不等于' },
    { value: 'exists', label: '存在' },
    { value: 'not_empty', label: '非空' },
    { value: 'contains', label: '包含' },
    { value: 'in', label: '属于' },
  ];
  const conditionOperators = [
    { value: 'equals', label: '等于' },
    { value: 'not_equals', label: '不等于' },
    { value: 'contains', label: '包含' },
    { value: 'not_contains', label: '不包含' },
    { value: 'exists', label: '存在' },
    { value: 'not_empty', label: '非空' },
  ];

  const steps = ref([]);

  function bodyPlaceholder(step) {
    if (step.bodyType === 'json') return `{"account":"\${secret.username}"}`;
    return `{"account":"\${secret.username}","google_code":"\${secret.otp}"}`;
  }

  function emptyAssertion() {
    return { source: '', operator: 'equals', expectedText: '', message: '' };
  }
  function emptyOutput() {
    return { key: '', source: '' };
  }
  function emptyStep() {
    return {
      name: '',
      id: '',
      url: '',
      method: 'POST',
      bodyType: 'form',
      headersText: '{}',
      bodyText: '{}',
      assertions: [],
      outputs: [],
      persistOutputs: false,
      whenEnabled: false,
      whenVariable: '',
      whenOperator: 'contains',
      whenValue: '',
    };
  }
  function addStep() {
    steps.value.push(emptyStep());
  }
  function removeStep(index) {
    steps.value.splice(index, 1);
  }
  function moveStep(index, offset) {
    const target = index + offset;
    if (target < 0 || target >= steps.value.length) return;
    const [item] = steps.value.splice(index, 1);
    steps.value.splice(target, 0, item);
  }
  function outputSummary(step) {
    return step.outputs
      .map((item) => item.key)
      .filter(Boolean)
      .join('、');
  }

  function parseJsonObject(text, label) {
    const value = JSON.parse(text || '{}');
    if (!value || Array.isArray(value) || typeof value !== 'object')
      throw new Error(`${label}必须是 JSON 对象`);
    return value;
  }

  /** 从后端配置回填可编辑状态；payload 为 camelCase 步骤列表。 */
  function loadSteps(payload) {
    steps.value = (payload || []).map((item) => ({
      name: item?.name || '',
      id: item?.id || '',
      url: item?.url || '',
      method: item?.method || 'POST',
      bodyType: item?.bodyType || 'form',
      headersText: JSON.stringify(item?.headers || {}, null, 2),
      bodyText: item?.body === undefined ? '{}' : JSON.stringify(item.body, null, 2),
      assertions: (item?.successAssertions || []).map((assertion) => ({
        source: assertion?.source || '',
        operator: assertion?.operator || 'equals',
        expectedText:
          assertion?.expected === undefined ? '' : JSON.stringify(assertion.expected),
        message: assertion?.message || '',
      })),
      outputs: Object.entries(item?.outputs || {}).map(([key, source]) => ({ key, source })),
      persistOutputs: !!item?.persistOutputs,
      whenEnabled: !!item?.when,
      whenVariable: item?.when?.variable || '',
      whenOperator: item?.when?.operator || 'contains',
      whenValue: item?.when?.value === undefined || item?.when?.value === null ? '' : String(item.when.value),
    }));
    if (!steps.value.length) steps.value = [emptyStep()];
  }

  /** 构建提交给后端的 camelCase 步骤列表；格式不合法时抛出带定位信息的异常。 */
  function buildSteps() {
    if (!enabled.value) return [];
    return steps.value.map((step, index) => {
      const position = `${props.kindLabel}链步骤 ${index + 1}`;
      if (!step.url.trim()) throw new Error(`${position}未填写接口地址`);
      if (!step.url.trim().startsWith('http://') && !step.url.trim().startsWith('https://'))
        throw new Error(`${position}的接口地址必须以 http:// 或 https:// 开头`);
      const body = step.bodyType === 'none' || step.method === 'GET' ? null : JSON.parse(step.bodyText || 'null');
      if (['form', 'multipart'].includes(step.bodyType) && body !== null) {
        if (!body || Array.isArray(body) || typeof body !== 'object')
          throw new Error(`${position}的请求体必须是 JSON 对象（键值对）`);
      }
      const outputs = {};
      for (const item of step.outputs) {
        const key = item.key.trim();
        const source = item.source.trim();
        if (!key && !source) continue;
        if (!key || !source) throw new Error(`${position}存在未填写完整的输出变量`);
        outputs[key] = source;
      }
      const successAssertions = step.assertions
        .filter((item) => item.source.trim() || item.expectedText.trim() || item.message.trim())
        .map((item) => {
          const source = item.source.trim();
          if (!source) throw new Error(`${position}存在未填写来源的成功断言`);
          const requiresExpected = !['exists', 'not_empty'].includes(item.operator);
          let expected = null;
          if (requiresExpected) {
            if (!item.expectedText.trim())
              throw new Error(`${position}存在未填写期望值的成功断言`);
            try {
              expected = JSON.parse(item.expectedText);
            } catch (_) {
              throw new Error(`${position}成功断言的期望值必须是合法 JSON`);
            }
          }
          return { source, operator: item.operator, expected, message: item.message.trim() };
        });
      let when = null;
      if (step.whenEnabled) {
        if (!step.whenVariable.trim())
          throw new Error(`${position}启用了执行条件但未填写条件变量`);
        let value = step.whenValue.trim();
        try {
          value = JSON.parse(value);
        } catch (_) {
          /* 保留原始字符串，比较值通常是普通文本如 otp? */
        }
        when = {
          variable: step.whenVariable.trim(),
          operator: step.whenOperator,
          value,
        };
      }
      return {
        name: step.name.trim(),
        id: step.id.trim(),
        url: step.url.trim(),
        method: step.method,
        bodyType: step.bodyType,
        headers: parseJsonObject(step.headersText, `${position}请求 Header`),
        body,
        successAssertions,
        outputs,
        persistOutputs: step.persistOutputs,
        when,
      };
    });
  }

  defineExpose({ loadSteps, buildSteps });
</script>

<style scoped>
  .steps-preview {
    background: #f5f7fa;
    border: 1px solid #ebeef5;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 12px;
  }
  .steps-preview-title {
    font-weight: 600;
    font-size: 13px;
    color: #303133;
    margin-bottom: 6px;
  }
  .steps-preview-list {
    margin: 0;
    padding-left: 18px;
    color: #606266;
    font-size: 13px;
  }
  .steps-preview-list li {
    line-height: 1.8;
  }
  .steps-preview-request {
    margin-left: 8px;
    font-family: monospace;
  }
  .steps-preview-note {
    margin-left: 8px;
    color: #909399;
  }
  .steps-preview-empty {
    color: #909399;
    list-style: none;
    margin-left: -18px;
  }
  .step-card {
    border: 1px solid #ebeef5;
    border-radius: 6px;
    padding: 12px 14px 4px;
    margin-bottom: 12px;
  }
  .step-card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
  }
  .step-card-title {
    font-weight: 600;
    color: #303133;
    margin-right: auto;
  }
  .assertion-row {
    display: grid;
    grid-template-columns: minmax(120px, 1.2fr) 110px minmax(120px, 1fr) minmax(120px, 1fr) 48px;
    gap: 8px;
    align-items: center;
    margin-bottom: 8px;
  }
  .mapping-row {
    display: grid;
    grid-template-columns: 1fr 1.4fr 48px;
    gap: 8px;
    align-items: center;
    margin-bottom: 8px;
  }
  @media (max-width: 768px) {
    .assertion-row,
    .mapping-row {
      grid-template-columns: 1fr;
    }
  }
</style>
