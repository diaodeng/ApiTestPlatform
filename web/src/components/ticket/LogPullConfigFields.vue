<template>
  <template v-if="model">
    <el-col v-if="showEnvironment && environmentOptions.length" :span="24">
      <el-form-item label="环境" :prop="getProp('environment')">
        <el-select
          :model-value="model.environment"
          placeholder="选择环境"
          style="width: 100%"
          @update:model-value="handleEnvironmentChange"
        >
          <el-option
            v-for="item in environmentOptions"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="24">
      <el-form-item label="商家" :prop="getProp('vendorId')">
        <el-select
          v-model="model.vendorId"
          placeholder="选择商家"
          clearable
          filterable
          allow-create
          default-first-option
          style="width: 100%"
          @change="handleVendorChange"
        >
          <el-option
            v-for="item in vendorOptions"
            :key="item.venderNo"
            :label="item.label"
            :value="item.venderNo"
          />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="24">
      <el-form-item label="门店" :prop="getProp('storeId')">
        <el-select
          v-model="model.storeId"
          placeholder="先选择商家"
          clearable
          filterable
          allow-create
          default-first-option
          :disabled="!model.vendorId"
          style="width: 100%"
        >
          <el-option
            v-for="item in resolvedStoreOptions"
            :key="item.storeId"
            :label="item.label"
            :value="item.storeId"
          />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="24">
      <el-form-item label="POSID" :prop="getProp('posNo')">
        <el-input-number v-model="model.posNo" :min="1" controls-position="right" style="width: 100%" />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="数据类型" :prop="getProp('commandDataType')">
        <el-select v-model="model.commandDataType" placeholder="请选择" style="width: 100%">
          <el-option
            v-for="item in dataTypeOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="拉取方式">
        <el-radio-group v-model="model.pullMethod">
          <el-radio value="time">时间</el-radio>
          <el-radio value="path">路径</el-radio>
        </el-radio-group>
      </el-form-item>
    </el-col>
    <el-col v-if="model.pullMethod === 'time'" :span="12">
      <el-form-item label="modifyTime" :prop="getProp('modifyTime')">
        <el-date-picker
          v-model="model.modifyTime"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="按日期拉取"
          clearable
          style="width: 100%"
        />
      </el-form-item>
    </el-col>
    <el-col v-if="model.pullMethod === 'path'" :span="24">
      <el-form-item label="path" :prop="getProp('path')">
        <el-input v-model="model.path" placeholder="可选，按路径拉取" clearable />
      </el-form-item>
    </el-col>
    <el-col v-if="model.pullMethod === 'path' && parameterExampleOptions.length" :span="24">
      <el-form-item label="参数示例">
        <el-select
          v-model="selectedParameterExample"
          placeholder="选择示例填入当前参数"
          clearable
          filterable
          style="width: 100%"
          @change="handleParameterExampleChange"
        >
          <el-option
            v-for="item in parameterExampleOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="单文件上限" :prop="getProp('fileMaxSize')">
        <el-input-number v-model="model.fileMaxSize" :min="1" controls-position="right" style="width: 100%" />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="压缩包上限" :prop="getProp('zipMaxSize')">
        <el-input-number v-model="model.zipMaxSize" :min="1" controls-position="right" style="width: 100%" />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="保存方式" :prop="getProp('storageMode')">
        <el-select v-model="model.storageMode" placeholder="请选择" style="width: 100%">
          <el-option
            v-for="item in storageModeOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col v-if="showAutoAi" :span="12">
      <el-form-item label="自动AI" :prop="getProp('autoAiEnabled')">
        <el-switch v-model="model.autoAiEnabled" inline-prompt active-text="是" inactive-text="否" />
      </el-form-item>
    </el-col>
    <el-col v-if="model.autoAiEnabled" :span="12">
      <el-form-item label="AI Agent" :prop="getProp('aiAgentCode')">
        <el-select
          v-model="model.aiAgentCode"
          placeholder="请选择Agent"
          filterable
          clearable
          style="width: 100%"
        >
          <el-option
            v-for="item in agentOptions"
            :key="item.agentCode"
            :label="`${item.agentName || item.agentCode} [${item.agentCode}]`"
            :value="item.agentCode"
          />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col v-if="model.autoAiEnabled" :span="12">
      <el-form-item label="AI Provider" :prop="getProp('aiProviderCode')">
        <el-select
          v-model="model.aiProviderCode"
          placeholder="请选择Provider"
          filterable
          clearable
          style="width: 100%"
          @change="handleProviderChange"
        >
          <el-option
            v-for="item in providerOptions"
            :key="item.providerCode"
            :label="formatProviderOption(item)"
            :value="item.providerCode"
          />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="24">
      <el-form-item label="切割日志" :prop="getProp('cutLogEnabled')">
        <el-switch v-model="model.cutLogEnabled" inline-prompt active-text="是" inactive-text="否" />
      </el-form-item>
    </el-col>
    <el-col v-if="model.cutLogEnabled" :span="24">
      <el-form-item label="时间方式" :prop="getProp('timeRangeMode')">
        <el-radio-group v-model="model.timeRangeMode">
          <el-radio value="between">开始 + 结束</el-radio>
          <el-radio value="point">时间点 + 前后范围</el-radio>
        </el-radio-group>
      </el-form-item>
    </el-col>
    <template v-if="model.cutLogEnabled && model.timeRangeMode === 'between'">
      <el-col :span="12">
        <el-form-item label="开始时间" :prop="getProp('logBeginTime')">
          <el-date-picker
            v-model="model.logBeginTime"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="可选，筛选日志开始时间"
            clearable
            style="width: 100%"
          />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="结束时间" :prop="getProp('logEndTime')">
          <el-date-picker
            v-model="model.logEndTime"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="可选，筛选日志结束时间"
            clearable
            style="width: 100%"
          />
        </el-form-item>
      </el-col>
    </template>
    <template v-else-if="model.cutLogEnabled">
      <el-col :span="12">
        <el-form-item label="时间点" :prop="getProp('logPointTime')">
          <el-date-picker
            v-model="model.logPointTime"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="可选，基准时间点"
            clearable
            style="width: 100%"
          />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="前后范围" :prop="getProp('rangeBeforeMinutes')">
          <div class="time-range-inline">
            <span>前</span>
            <el-input-number v-model="model.rangeBeforeMinutes" :min="0" controls-position="right" />
            <span>分钟，后</span>
            <el-input-number v-model="model.rangeAfterMinutes" :min="0" controls-position="right" />
            <span>分钟</span>
          </div>
        </el-form-item>
      </el-col>
    </template>
  </template>
</template>

<script setup>
import { getTicketLogPullVendorStoreOptions } from '@/api/ticket/ticket'

const props = defineProps({
  agentOptions: {
    type: Array,
    default: () => []
  },
  dataTypeOptions: {
    type: Array,
    default: () => []
  },
  showAutoAi: {
    type: Boolean,
    default: true
  },
  showEnvironment: {
    type: Boolean,
    default: true
  },
  environmentOptions: {
    type: Array,
    default: () => []
  },
  fieldPrefix: {
    type: String,
    default: ''
  },
  storageModeOptions: {
    type: Array,
    default: () => []
  },
  providerOptions: {
    type: Array,
    default: () => []
  },
  vendorOptions: {
    type: Array,
    default: () => []
  },
  storeOptions: {
    type: Array,
    default: () => []
  },
  parameterExamples: {
    type: Array,
    default: () => []
  }
})

const model = defineModel({
  type: Object,
  default: () => ({})
})

const selectedParameterExample = ref('')
const fetchedStoreOptions = ref([])
const activeStoreVenderNo = ref('')
let storeOptionsRequestSeq = 0

const parameterExampleOptions = computed(() => props.parameterExamples
  .map(item => {
    const value = String(item?.value || '').trim()
    const name = String(item?.name || item?.label || '').trim()
    return value
      ? {
          label: name ? `${name}：${value}` : value,
          value
        }
      : null
  })
  .filter(Boolean)
)

const resolvedStoreOptions = computed(() => {
  const venderNo = String(model.value?.vendorId || '').trim()
  if (!venderNo) {
    return []
  }
  if (activeStoreVenderNo.value === venderNo) {
    return fetchedStoreOptions.value
  }
  if (props.storeOptions.length) {
    return props.storeOptions
  }
  return []
})

function getProp(name) {
  return props.fieldPrefix ? `${props.fieldPrefix}.${name}` : name
}

function normalizeStoreOptions(responseData) {
  const stores = Array.isArray(responseData?.stores) ? responseData.stores : []
  return stores.map(store => ({
      storeId: String(store.storeId || '').trim(),
      storeCode: String(store.storeCode || '').trim(),
      sapOrgNo: String(store.sapOrgNo || '').trim(),
      storeName: String(store.storeName || store.storeId || '').trim(),
      label: buildStoreOptionLabel(store)
    }))
}

function loadStoreOptions(venderNo) {
  const resolvedVenderNo = String(venderNo || '').trim()
  activeStoreVenderNo.value = resolvedVenderNo
  if (!resolvedVenderNo) {
    fetchedStoreOptions.value = []
    return Promise.resolve()
  }
  const requestSeq = ++storeOptionsRequestSeq
  fetchedStoreOptions.value = []
  return getTicketLogPullVendorStoreOptions(resolvedVenderNo).then(response => {
    if (requestSeq !== storeOptionsRequestSeq) {
      return
    }
    fetchedStoreOptions.value = normalizeStoreOptions(response.data)
  }).catch(() => {
    if (requestSeq !== storeOptionsRequestSeq) {
      return
    }
    fetchedStoreOptions.value = []
  })
}

function syncStoreSelection() {
  const storeId = String(model.value?.storeId || '').trim()
  if (!storeId) {
    return
  }
  if (!resolvedStoreOptions.value.length) {
    return
  }
  if (!resolvedStoreOptions.value.some(item => String(item.storeId || '').trim() === storeId)) {
    // 允许保留非配置内门店值（兼容外部同步原样保存场景）。
    model.value.storeId = storeId
  }
}

function handleEnvironmentChange(value) {
  model.value.environment = value
}

function handleVendorChange() {
  model.value.storeId = undefined
}

function handleParameterExampleChange(value) {
  const resolvedValue = String(value || '').trim()
  if (!resolvedValue) {
    return
  }
  // 参数示例仅在路径模式下可见，直接填充 path
  model.value.path = resolvedValue
}

function clearLogTimeRange() {
  model.value.logBeginTime = undefined
  model.value.logEndTime = undefined
  model.value.logPointTime = undefined
  model.value.rangeBeforeMinutes = 30
  model.value.rangeAfterMinutes = 30
}

function buildStoreOptionLabel(store) {
  const name = String(store.storeName || '').trim()
  const orgNo = String(store.storeCode || store.storeId || '').trim()
  const sapOrgNo = String(store.sapOrgNo || '').trim()
  return [name, orgNo ? `[${orgNo}]` : '', sapOrgNo ? `(${sapOrgNo})` : '']
    .filter(Boolean)
    .join(' ')
}

function formatProviderOption(item) {
  const name = String(item.providerName || item.providerCode || '').trim()
  const code = String(item.providerCode || '').trim()
  const type = String(item.providerType || '').trim()
  const model = String(item.modelName || '').trim()
  const level = item.providerLevel ?? ''
  return [name, code ? `[${code}]` : '', type ? `(${type})` : '', model ? `- ${model}` : '', level !== '' ? `#${level}` : '']
    .filter(Boolean)
    .join(' ')
}

function handleProviderChange(providerCode) {
  if (!providerCode) {
    return
  }
  const provider = props.providerOptions.find(item => item.providerCode === providerCode)
  if (!provider) {
    return
  }
  if (provider.agentCode) {
    model.value.aiAgentCode = provider.agentCode
  }
}

watch(
  () => model.value?.vendorId,
  vendorId => {
    loadStoreOptions(vendorId).then(() => {
      syncStoreSelection()
    })
  },
  { immediate: true }
)

watch(
  () => [props.environmentOptions, model.value?.environment],
  ([envOptions, currentEnv]) => {
    if (Array.isArray(envOptions) && envOptions.length && !currentEnv) {
      model.value.environment = envOptions[0]
    }
  },
  { immediate: true }
)

watch(
  () => model.value?.aiProviderCode,
  providerCode => {
    if (!providerCode) {
      return
    }
    handleProviderChange(providerCode)
  }
)

watch(
  () => model.value?.commandDataType,
  commandDataType => {
    selectedParameterExample.value = ''
    // 切换数据类型时自动联动拉取方式默认值，日志→时间，DB→路径
    model.value.pullMethod = Number(commandDataType) === 2 ? 'path' : 'time'
  }
)

watch(
  () => model.value?.autoAiEnabled,
  enabled => {
    if (!enabled) {
      model.value.aiAgentCode = ''
      model.value.aiProviderCode = ''
    }
  }
)

watch(
  () => model.value?.cutLogEnabled,
  enabled => {
    if (!enabled) {
      clearLogTimeRange()
    } else if (!model.value.timeRangeMode) {
      model.value.timeRangeMode = 'between'
    }
  }
)
</script>

<style scoped>
.time-range-inline {
  display: flex;
  align-items: center;
  gap: 8px;
}

.time-range-inline :deep(.el-input-number) {
  width: 140px;
}
</style>
