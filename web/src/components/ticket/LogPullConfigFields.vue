<template>
  <template v-if="model">
    <el-col :span="8">
      <el-form-item label="vendorId" :prop="getProp('vendorId')">
        <el-select
          v-model="model.vendorId"
          placeholder="选择或输入商家"
          clearable
          filterable
          allow-create
          default-first-option
          @change="handleVendorChange"
        >
          <el-option
            v-for="item in vendorOptions"
            :key="item.vendorId"
            :label="item.label"
            :value="item.vendorId"
          />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="8">
      <el-form-item label="storeId" :prop="getProp('storeId')">
        <el-select
          v-model="model.storeId"
          placeholder="选择或输入门店"
          clearable
          filterable
          allow-create
          default-first-option
        >
          <el-option
            v-for="item in storeOptions"
            :key="item.storeId"
            :label="item.label"
            :value="item.storeId"
          />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="8">
      <el-form-item label="posNo" :prop="getProp('posNo')">
        <el-input-number v-model="model.posNo" :min="1" controls-position="right" />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="数据类型" :prop="getProp('commandDataType')">
        <el-select v-model="model.commandDataType" placeholder="请选择">
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
      <el-form-item label="modifyTime" :prop="getProp('modifyTime')">
        <el-date-picker
          v-model="model.modifyTime"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="按日期拉取"
          clearable
        />
      </el-form-item>
    </el-col>
    <el-col :span="24">
      <el-form-item label="path" :prop="getProp('path')">
        <el-input v-model="model.path" placeholder="可选，按路径拉取" clearable />
      </el-form-item>
    </el-col>
    <el-col :span="24">
      <el-form-item label="时间方式" :prop="getProp('timeRangeMode')">
        <el-radio-group v-model="model.timeRangeMode">
          <el-radio value="between">开始 + 结束</el-radio>
          <el-radio value="point">时间点 + 前后范围</el-radio>
        </el-radio-group>
      </el-form-item>
    </el-col>
    <template v-if="model.timeRangeMode === 'between'">
      <el-col :span="12">
        <el-form-item label="开始时间" :prop="getProp('logBeginTime')">
          <el-date-picker
            v-model="model.logBeginTime"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="可选，筛选日志开始时间"
            clearable
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
          />
        </el-form-item>
      </el-col>
    </template>
    <template v-else>
      <el-col :span="12">
        <el-form-item label="时间点" :prop="getProp('logPointTime')">
          <el-date-picker
            v-model="model.logPointTime"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="可选，基准时间点"
            clearable
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
    <el-col :span="12">
      <el-form-item label="单文件上限" :prop="getProp('fileMaxSize')">
        <el-input-number v-model="model.fileMaxSize" :min="1" controls-position="right" />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="压缩包上限" :prop="getProp('zipMaxSize')">
        <el-input-number v-model="model.zipMaxSize" :min="1" controls-position="right" />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="保存方式" :prop="getProp('storageMode')">
        <el-select v-model="model.storageMode" placeholder="请选择">
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
    <el-col :span="12">
      <el-form-item label="AI Agent" :prop="getProp('aiAgentCode')">
        <el-select
          v-model="model.aiAgentCode"
          placeholder="请选择Agent"
          filterable
          clearable
          :disabled="!model.autoAiEnabled"
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
    <el-col :span="12">
      <el-form-item label="AI Provider" :prop="getProp('aiProviderCode')">
        <el-select
          v-model="model.aiProviderCode"
          placeholder="请选择Provider"
          filterable
          clearable
          :disabled="!model.autoAiEnabled"
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
  </template>
</template>

<script setup>
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
  }
})

const model = defineModel({
  type: Object,
  default: () => ({})
})

const storeOptions = computed(() => {
  const vendorId = Number(model.value?.vendorId)
  if (!vendorId) {
    return []
  }
  const vendor = props.vendorOptions.find(item => item.vendorId === vendorId)
  return vendor?.stores || []
})

function getProp(name) {
  return props.fieldPrefix ? `${props.fieldPrefix}.${name}` : name
}

function syncStoreSelection() {
  const storeId = Number(model.value?.storeId)
  if (!storeId) {
    return
  }
  if (!storeOptions.value.some(item => item.storeId === storeId)) {
    model.value.storeId = undefined
  }
}

function handleVendorChange() {
  syncStoreSelection()
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
  () => {
    syncStoreSelection()
  }
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
