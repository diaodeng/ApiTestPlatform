<template>
  <div class="steps-editor">
    <div class="steps-toolbar">
      <div>
        <div class="steps-title">认证流程</div>
        <div class="steps-desc">
          {{ kindLabel }}流程按顺序执行；每一步可以提取临时变量，开启“写回凭证”后才更新最终凭证。
        </div>
      </div>
      <el-tag size="small">{{ steps.length }}/{{ maxSteps }} 步</el-tag>
    </div>

    <div v-if="enabled && steps.length" class="flow-track">
      <template v-for="(step, index) in steps" :key="index">
        <button
          type="button"
          class="flow-node"
          :class="{ active: isExpanded(index) }"
          @click="openStep(index)"
        >
          <span class="flow-node-no">{{ index + 1 }}</span>
          <span class="flow-node-copy">
            <b>{{ step.name || `步骤 ${index + 1}` }}</b>
            <small>{{ step.method }} · {{ step.url || '未配置地址' }}</small>
          </span>
        </button>
        <span v-if="index < steps.length - 1" class="flow-arrow">→</span>
      </template>
    </div>

    <div v-if="enabled && !steps.length" class="steps-empty">
      <div class="steps-empty-icon">+</div>
      <b>还没有认证步骤</b>
      <p>添加第一步，例如“账号密码登录”。后续步骤可以引用前一步输出的 ticket。</p>
      <el-button type="primary" plain :icon="Plus" @click="addStep">添加第一步</el-button>
    </div>

    <div
      v-for="(step, index) in steps"
      :key="`step-${index}`"
      class="step-card"
      :class="{ expanded: isExpanded(index) }"
    >
      <button type="button" class="step-summary" @click="toggleStep(index)">
        <span class="step-summary-no">{{ index + 1 }}</span>
        <span class="step-summary-main">
          <b>{{ step.name || `步骤 ${index + 1}` }}</b>
          <small>{{ stepMethodLabel(step) }}</small>
          <span class="step-badges">
            <el-tag size="small" effect="plain">{{
              step.bodyType === 'none'
                ? '无请求体'
                : step.bodyType === 'multipart'
                  ? 'multipart'
                  : step.bodyType === 'json'
                    ? 'JSON'
                    : 'form'
            }}</el-tag>
            <el-tag v-if="assertionCount(step)" size="small" effect="plain"
              >断言 {{ assertionCount(step) }}</el-tag
            >
            <el-tag v-if="outputCount(step)" size="small" effect="plain" type="success"
              >输出 {{ outputCount(step) }}</el-tag
            >
            <el-tag v-if="step.persistOutputs" size="small" type="success">写回凭证</el-tag>
            <el-tag v-if="step.whenEnabled" size="small" type="warning">有条件</el-tag>
          </span>
        </span>
        <span class="step-summary-actions">
          <el-button text size="small" :disabled="index === 0" @click.stop="moveStep(index, -1)"
            >上移</el-button
          >
          <el-button
            text
            size="small"
            :disabled="index === steps.length - 1"
            @click.stop="moveStep(index, 1)"
            >下移</el-button
          >
          <el-button text size="small" type="danger" @click.stop="removeStep(index)"
            >删除</el-button
          >
          <span class="step-expand">{{ isExpanded(index) ? '⌃' : '⌄' }}</span>
        </span>
      </button>

      <div v-show="isExpanded(index)" class="step-content">
        <div class="step-basic-grid">
          <el-form-item label="步骤名称">
            <el-input v-model="step.name" placeholder="例如：账号密码登录" maxlength="64" />
          </el-form-item>
          <el-form-item label="步骤标识">
            <el-input v-model="step.id" placeholder="例如 login，供后续步骤引用" maxlength="64" />
          </el-form-item>
          <el-form-item label="请求体类型">
            <el-select v-model="step.bodyType" style="width: 100%">
              <el-option value="none" label="无请求体" />
              <el-option value="form" label="表单 (urlencoded)" />
              <el-option value="json" label="JSON" />
              <el-option value="multipart" label="表单 (multipart)" />
            </el-select>
          </el-form-item>
        </div>

        <div class="step-request-line">
          <el-form-item label="请求方法">
            <el-select v-model="step.method" style="width: 100%">
              <el-option v-for="method in requestMethods" :key="method" :value="method" />
            </el-select>
          </el-form-item>
          <el-form-item label="接口地址" required>
            <el-input v-model="step.url" placeholder="https://example.com/api/login" />
          </el-form-item>
        </div>

        <div class="step-tabs">
          <button
            type="button"
            :class="{ active: getStepTab(index) === 'request' }"
            @click="setStepTab(index, 'request')"
          >
            请求
          </button>
          <button
            type="button"
            :class="{ active: getStepTab(index) === 'assertions' }"
            @click="setStepTab(index, 'assertions')"
          >
            成功判断 <em>{{ assertionCount(step) }}</em>
          </button>
          <button
            type="button"
            :class="{ active: getStepTab(index) === 'outputs' }"
            @click="setStepTab(index, 'outputs')"
          >
            输出 <em>{{ outputCount(step) }}</em>
          </button>
          <button
            type="button"
            :class="{ active: getStepTab(index) === 'advanced' }"
            @click="setStepTab(index, 'advanced')"
          >
            高级
          </button>
        </div>

        <div v-show="getStepTab(index) === 'request'" class="step-panel">
          <el-form-item label="请求 Header">
            <el-input
              v-model="step.headersText"
              type="textarea"
              :rows="3"
              placeholder='JSON，例如 {"Accept":"application/json"}；multipart 的 Content-Type 由系统生成'
            />
          </el-form-item>
          <el-form-item v-if="step.bodyType !== 'none' && step.method !== 'GET'" label="请求体">
            <el-input
              v-model="step.bodyText"
              type="textarea"
              :rows="6"
              :placeholder="bodyPlaceholder(step)"
            />
          </el-form-item>
          <div class="variable-box">
            <b>变量</b>
            <span
              >凭证：<code>${secret.username}</code> <code>${secret.password}</code>
              <code>${secret.otp}</code></span
            >
            <span>前一步：<code>${step.login.ticket}</code></span>
            <span>运行时 OTP 会在执行时生成/注入，不保存静态验证码。</span>
          </div>
        </div>

        <div v-show="getStepTab(index) === 'assertions'" class="step-panel">
          <div class="panel-tip">
            本步骤请求成功后，先执行所有断言；断言失败不会继续执行后续步骤。
          </div>
          <div
            v-for="(assertion, assertionIndex) in step.assertions"
            :key="assertionIndex"
            class="assertion-row"
          >
            <el-input v-model="assertion.source" placeholder="来源，如 json:code / status" />
            <el-select v-model="assertion.operator" style="width: 100%">
              <el-option
                v-for="item in assertionOperators"
                :key="item.value"
                :value="item.value"
                :label="item.label"
              />
            </el-select>
            <el-input
              v-model="assertion.expectedText"
              :disabled="['exists', 'not_empty'].includes(assertion.operator)"
              placeholder='期望值，如 "success"'
            />
            <el-input v-model="assertion.message" placeholder="失败提示（可选）" />
            <el-button text type="danger" @click="step.assertions.splice(assertionIndex, 1)"
              >删除</el-button
            >
          </div>
          <el-button plain size="small" @click="step.assertions.push(emptyAssertion())"
            >添加断言</el-button
          >
        </div>

        <div v-show="getStepTab(index) === 'outputs'" class="step-panel">
          <div class="panel-tip">
            输出变量只在当前认证链运行期间存在。开启“写回凭证”后，输出 key
            会按现有规则作为凭证字段写入。
          </div>
          <div v-for="(output, outputIndex) in step.outputs" :key="outputIndex" class="output-row">
            <el-input v-model="output.key" placeholder="变量名，如 ticket / cookie.SESSION" />
            <el-input
              v-model="output.source"
              placeholder="来源，如 json:result|url_query:ticket / cookie:SESSION"
            />
            <el-button text type="danger" @click="step.outputs.splice(outputIndex, 1)"
              >删除</el-button
            >
          </div>
          <div class="output-footer">
            <el-button plain size="small" @click="step.outputs.push(emptyOutput())"
              >添加输出</el-button
            >
            <el-switch v-model="step.persistOutputs" active-text="写回凭证" />
            <span>{{
              step.persistOutputs ? '本步骤输出将更新凭证' : '仅供后续步骤引用，不写回凭证'
            }}</span>
          </div>
        </div>

        <div v-show="getStepTab(index) === 'advanced'" class="step-panel">
          <div class="condition-box">
            <div class="condition-head">
              <div>
                <b>执行条件</b>
                <small>可根据前一步输出决定是否执行当前步骤</small>
              </div>
              <el-switch v-model="step.whenEnabled" />
            </div>
            <div v-if="step.whenEnabled" class="condition-grid">
              <el-form-item label="条件变量">
                <el-input v-model="step.whenVariable" placeholder="step.login.result" />
              </el-form-item>
              <el-form-item label="操作符">
                <el-select v-model="step.whenOperator" style="width: 100%">
                  <el-option
                    v-for="item in conditionOperators"
                    :key="item.value"
                    :value="item.value"
                    :label="item.label"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="比较值">
                <el-input v-model="step.whenValue" placeholder="例如 otp?" />
              </el-form-item>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="enabled && steps.length" class="add-step-bar">
      <el-button plain :icon="Plus" :disabled="steps.length >= maxSteps" @click="addStep"
        >添加认证步骤</el-button
      >
      <span>最多 {{ maxSteps }} 步；建议至少一个步骤开启“写回凭证”</span>
    </div>

    <div v-if="!enabled" class="steps-disabled">
      <el-switch v-model="enabled" />
      <span>开启后使用多步 {{ kindLabel }}认证链，替代单接口配置。</span>
    </div>
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
  const expandedSteps = ref(new Set([0]));
  const stepTabs = reactive({});
  const stepOutputDrafts = reactive({});

  function isExpanded(index) {
    return expandedSteps.value.has(index);
  }

  function toggleStep(index) {
    const next = new Set(expandedSteps.value);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    expandedSteps.value = next;
  }

  function openStep(index) {
    expandedSteps.value = new Set([...expandedSteps.value, index]);
  }

  function getStepTab(index) {
    return stepTabs[index] || 'request';
  }

  function setStepTab(index, tab) {
    stepTabs[index] = tab;
  }

  function stepMethodLabel(step) {
    return `${step.method || 'POST'} ${step.url || '未填写接口地址'}`;
  }

  function outputCount(step) {
    return step.outputs.filter((item) => item.key || item.source).length;
  }

  function assertionCount(step) {
    return step.assertions.filter((item) => item.source || item.expectedText || item.message)
      .length;
  }

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
    if (steps.value.length >= maxSteps) return;
    const index = steps.value.length;
    steps.value.push(emptyStep());
    expandedSteps.value = new Set([...expandedSteps.value, index]);
    stepTabs[index] = 'request';
  }
  function removeStep(index) {
    steps.value.splice(index, 1);
    const next = new Set();
    expandedSteps.value.forEach((item) => {
      if (item === index) return;
      next.add(item > index ? item - 1 : item);
    });
    expandedSteps.value = next;
    const tabs = { ...stepTabs };
    Object.keys(tabs).forEach((key) => delete stepTabs[key]);
    Object.entries(tabs).forEach(([key, value]) => {
      const oldIndex = Number(key);
      if (oldIndex === index) return;
      stepTabs[oldIndex > index ? oldIndex - 1 : oldIndex] = value;
    });
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

  /**
   * 详情接口会把步骤 Header/请求体中的字面量敏感值脱敏为 ******；
   * 回填时还原为 ${secret.字段名} 占位符（与单步请求模板的回填约定一致），
   * 避免保存时把 ****** 当作真实值写回凭证配置。
   */
  function restoreRedacted(value) {
    if (Array.isArray(value)) return value.map(restoreRedacted);
    if (!value || typeof value !== 'object') return value;
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        item === '******' ? `\${secret.${key}}` : restoreRedacted(item),
      ])
    );
  }

  /** 从后端配置回填可编辑状态；payload 为 camelCase 步骤列表。 */
  function loadSteps(payload) {
    expandedSteps.value = new Set([0]);
    Object.keys(stepTabs).forEach((key) => delete stepTabs[key]);
    steps.value = (payload || []).map((item) => ({
      name: item?.name || '',
      id: item?.id || '',
      url: item?.url || '',
      method: item?.method || 'POST',
      bodyType: item?.bodyType || 'form',
      headersText: JSON.stringify(restoreRedacted(item?.headers || {}), null, 2),
      bodyText:
        item?.body === undefined ? '{}' : JSON.stringify(restoreRedacted(item.body), null, 2),
      assertions: (item?.successAssertions || []).map((assertion) => ({
        source: assertion?.source || '',
        operator: assertion?.operator || 'equals',
        expectedText: assertion?.expected === undefined ? '' : JSON.stringify(assertion.expected),
        message: assertion?.message || '',
      })),
      outputs: Object.entries(item?.outputs || {}).map(([key, source]) => ({ key, source })),
      persistOutputs: !!item?.persistOutputs,
      whenEnabled: !!item?.when,
      whenVariable: item?.when?.variable || '',
      whenOperator: item?.when?.operator || 'contains',
      whenValue:
        item?.when?.value === undefined || item?.when?.value === null
          ? ''
          : String(item.when.value),
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
      const body =
        step.bodyType === 'none' || step.method === 'GET'
          ? null
          : JSON.parse(step.bodyText || 'null');
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
            if (!item.expectedText.trim()) throw new Error(`${position}存在未填写期望值的成功断言`);
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
        if (!step.whenVariable.trim()) throw new Error(`${position}启用了执行条件但未填写条件变量`);
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
  .steps-editor {
    border: 1px solid var(--el-border-color-light);
    border-radius: 10px;
    background: var(--el-bg-color);
    overflow: hidden;
  }
  .steps-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    padding: 14px 16px;
    border-bottom: 1px solid var(--el-border-color-light);
    background: var(--el-fill-color-light);
  }
  .steps-title {
    font-size: 14px;
    font-weight: 650;
  }
  .steps-desc {
    margin-top: 3px;
    color: var(--el-text-color-secondary);
    font-size: 11px;
    line-height: 1.5;
  }

  .flow-track {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 14px 16px;
    overflow-x: auto;
    border-bottom: 1px solid var(--el-border-color-light);
  }
  .flow-node {
    flex: 0 0 210px;
    display: flex;
    align-items: center;
    gap: 9px;
    border: 1px solid var(--el-border-color);
    border-radius: 8px;
    background: var(--el-bg-color);
    padding: 8px 10px;
    text-align: left;
    cursor: pointer;
    color: inherit;
  }
  .flow-node.active {
    border-color: var(--el-color-primary);
    background: var(--el-color-primary-light-9);
  }
  .flow-node-no {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--el-fill-color);
    font-size: 11px;
    font-weight: 700;
    flex: 0 0 auto;
  }
  .flow-node-copy {
    min-width: 0;
  }
  .flow-node-copy b,
  .flow-node-copy small {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .flow-node-copy small {
    margin-top: 2px;
    color: var(--el-text-color-secondary);
    font-size: 10px;
  }
  .flow-arrow {
    color: var(--el-text-color-placeholder);
    font-size: 18px;
  }

  .steps-empty {
    text-align: center;
    padding: 40px 20px;
    color: var(--el-text-color-secondary);
  }
  .steps-empty-icon {
    width: 40px;
    height: 40px;
    margin: 0 auto 9px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--el-fill-color-light);
    color: var(--el-color-primary);
    font-size: 20px;
  }
  .steps-empty p {
    font-size: 11px;
    margin: 5px auto 14px;
    max-width: 460px;
  }

  .step-card {
    border-bottom: 1px solid var(--el-border-color-light);
  }
  .step-card:last-of-type {
    border-bottom: 0;
  }
  .step-summary {
    width: 100%;
    border: 0;
    background: var(--el-bg-color);
    color: inherit;
    display: flex;
    align-items: center;
    gap: 11px;
    text-align: left;
    padding: 12px 16px;
    cursor: pointer;
  }
  .step-summary:hover {
    background: var(--el-fill-color-light);
  }
  .step-summary-no {
    width: 28px;
    height: 28px;
    border-radius: 7px;
    display: grid;
    place-items: center;
    background: var(--el-color-primary-light-9);
    color: var(--el-color-primary);
    font-weight: 700;
    font-size: 12px;
    flex: 0 0 auto;
  }
  .step-summary-main {
    min-width: 0;
    flex: 1;
  }
  .step-summary-main > b,
  .step-summary-main > small {
    display: block;
  }
  .step-summary-main > small {
    color: var(--el-text-color-secondary);
    font-size: 11px;
    margin-top: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .step-badges {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
    margin-top: 5px;
  }
  .step-summary-actions {
    display: flex;
    align-items: center;
    gap: 2px;
    flex: 0 0 auto;
  }
  .step-expand {
    color: var(--el-text-color-secondary);
    font-size: 17px;
    padding-left: 4px;
  }

  .step-content {
    padding: 2px 16px 18px;
    border-top: 1px solid var(--el-border-color-lighter);
  }
  .step-basic-grid,
  .step-request-line,
  .condition-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 12px;
  }
  .step-request-line {
    grid-template-columns: 160px 1fr;
    margin-top: 2px;
  }
  .step-content :deep(.el-form-item) {
    margin-bottom: 12px;
  }
  .step-tabs {
    display: flex;
    gap: 2px;
    border-bottom: 1px solid var(--el-border-color-light);
    margin-top: 3px;
  }
  .step-tabs button {
    border: 0;
    border-bottom: 2px solid transparent;
    background: transparent;
    color: var(--el-text-color-secondary);
    padding: 9px 10px;
    cursor: pointer;
    font-size: 12px;
  }
  .step-tabs button.active {
    color: var(--el-color-primary);
    border-bottom-color: var(--el-color-primary);
    font-weight: 600;
  }
  .step-tabs em {
    font-style: normal;
    font-size: 10px;
    background: var(--el-fill-color);
    padding: 1px 4px;
    border-radius: 8px;
    margin-left: 3px;
  }
  .step-panel {
    padding-top: 14px;
  }
  .variable-box,
  .panel-tip {
    padding: 9px 11px;
    background: var(--el-fill-color-light);
    border-radius: 7px;
    color: var(--el-text-color-secondary);
    font-size: 11px;
    line-height: 1.7;
  }
  .variable-box {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    align-items: center;
  }
  .variable-box b {
    color: var(--el-text-color-primary);
  }
  code {
    font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
    background: var(--el-fill-color-darker);
    border-radius: 4px;
    padding: 1px 4px;
  }

  .assertion-row,
  .output-row {
    display: grid;
    gap: 7px;
    align-items: center;
    margin-bottom: 7px;
  }
  .assertion-row {
    grid-template-columns: 1.2fr 110px 1fr 1fr auto;
  }
  .output-row {
    grid-template-columns: 1fr 1.5fr auto;
  }
  .output-footer {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 10px;
  }
  .output-footer > span {
    color: var(--el-text-color-secondary);
    font-size: 11px;
  }

  .condition-box {
    border: 1px solid var(--el-border-color-light);
    border-radius: 8px;
    padding: 12px;
  }
  .condition-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .condition-head b,
  .condition-head small {
    display: block;
  }
  .condition-head small {
    color: var(--el-text-color-secondary);
    font-size: 11px;
    margin-top: 2px;
  }
  .condition-grid {
    margin-top: 12px;
    grid-template-columns: 1.3fr 150px 1fr;
  }

  .add-step-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    background: var(--el-fill-color-light);
    border-top: 1px solid var(--el-border-color-light);
  }
  .add-step-bar span,
  .steps-disabled span {
    color: var(--el-text-color-secondary);
    font-size: 11px;
  }
  .steps-disabled {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px;
    color: var(--el-text-color-secondary);
    background: var(--el-fill-color-light);
  }

  @media (max-width: 900px) {
    .step-basic-grid,
    .step-request-line,
    .condition-grid {
      grid-template-columns: 1fr;
    }
    .assertion-row,
    .output-row {
      grid-template-columns: 1fr;
    }
    .step-summary-actions .el-button {
      display: none;
    }
  }
</style>
