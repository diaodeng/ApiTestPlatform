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
            :key="item.key"
            :label="item.label"
            :value="item.key"
          />
        </el-select>
      </el-form-item>
    </el-col>
    <!-- 环境-商家匹配结果提示 -->
    <el-col v-if="showEnvironment && model.vendorId && model.environment" :span="24">
      <el-form-item label="" :prop="getProp('resolvedItemKey')">
        <div v-if="envResolveLoading" class="env-resolve-loading">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>正在匹配子环境...</span>
        </div>
        <template v-else-if="envResolveMatchItems.length === 0">
          <el-alert
            title="该商家在当前环境下未匹配到任何子环境配置"
            type="warning"
            :closable="false"
            show-icon
          />
        </template>
        <template v-else-if="envResolveMatchItems.length === 1">
          <el-alert
            :title="`已匹配：${envResolveMatchItems[0].groupLabel} / ${envResolveMatchItems[0].itemLabel}`"
            type="success"
            :closable="false"
            show-icon
          />
        </template>
        <template v-else>
          <div class="env-resolve-multi">
            <span class="env-resolve-label">多个子环境匹配，请选择：</span>
            <el-radio-group v-model="selectedEnvItemKey" @change="handleEnvItemSelect">
              <el-radio
                v-for="item in envResolveMatchItems"
                :key="item.itemKey"
                :value="item.itemKey"
              >
                {{ item.itemLabel }}
              </el-radio>
            </el-radio-group>
          </div>
        </template>
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
          :placeholder="storePlaceholder"
          clearable
          filterable
          allow-create
          :filter-method="handleStoreFilter"
          default-first-option
          :disabled="!model.vendorId"
          style="width: 100%"
        >
          <el-option
            v-for="item in filteredStoreOptions"
            :key="item.storeId"
            :label="item.label"
            :value="item.storeId"
          />
        </el-select>
      </el-form-item>
    </el-col>
    <!-- 门店匹配状态提示 -->
    <el-col v-if="storeHintMessage" :span="24">
      <el-form-item label="" :prop="getProp('storeId')">
        <el-alert
          :title="storeHintMessage"
          type="warning"
          :closable="false"
          show-icon
        />
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
import { getTicketLogPullVendorStoreOptions, resolveLogPullEnvItem } from '@/api/ticket/ticket'

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
const storeFilterKeyword = ref('')
let storeOptionsRequestSeq = 0

// 环境分组匹配相关状态
const envResolveLoading = ref(false)
const envResolveMatchItems = ref([])
const selectedEnvItemKey = ref('')
let envResolveRequestSeq = 0

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

const filteredStoreOptions = computed(() => {
  const keyword = String(storeFilterKeyword.value || '').trim().toLowerCase()
  if (!keyword) return resolvedStoreOptions.value
  return resolvedStoreOptions.value.filter(item =>
    item.label.toLowerCase().includes(keyword) ||
    String(item.storeCode || '').toLowerCase().includes(keyword) ||
    String(item.sapOrgNo || '').toLowerCase().includes(keyword)
  )
})

/**
 * 门店匹配状态提示：当已选商家但门店无法匹配时给出警告。
 * @returns {string|null} 提示文案，无需提示时返回 null
 */
const storeHintMessage = computed(() => {
  const vendorId = String(model.value?.vendorId || '').trim()
  if (!vendorId) return null
  const storeId = String(model.value?.storeId || '').trim()
  // 商家已选但门店列表为空（当前商家下无匹配门店）
  if (!resolvedStoreOptions.value.length) {
    return storeId
      ? `当前商家下未找到匹配门店，输入的 "${storeId}" 可能无效，请确认 org_no 是否正确`
      : '当前商家下未找到匹配门店，请手动输入正确的 org_no'
  }
  // 门店列表不为空，但用户输入的值不在列表中
  if (storeId) {
    const matched = resolvedStoreOptions.value.some(
      item => item.storeId === storeId || item.storeCode === storeId || item.sapOrgNo === storeId
    )
    if (!matched) {
      return `输入的门店 "${storeId}" 未在配置中找到，请确认 org_no 是否正确`
    }
  }
  return null
})

/**
 * 门店选择器 placeholder：根据是否有匹配门店动态调整。
 */
const storePlaceholder = computed(() => {
  if (!model.value?.vendorId) return '先选择商家'
  if (!resolvedStoreOptions.value.length) return '当前商家无匹配门店，请手动输入 org_no'
  return '请选择门店'
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
  // 只按 sap_org_no 精确匹配，匹配成功则替换为对应的 storeId (org_no)
  const sapMatch = resolvedStoreOptions.value.find(
    item => String(item.sapOrgNo || '').trim() === storeId
  )
  if (sapMatch) {
    model.value.storeId = sapMatch.storeId
    return
  }
  // 不匹配则保留原值作为自由文本，供手动参考
}

function handleEnvironmentChange(value) {
  // 确保 environment 始终为字符串，避免 element-plus 回传对象导致 [object Object]
  model.value.environment = typeof value === 'object' ? String(value?.key || '') : String(value || '')
  envResolveMatchItems.value = []
  selectedEnvItemKey.value = ''
  model.value.resolvedItemKey = undefined
  if (model.value.vendorId) {
    resolveEnvItemForVendor()
  }
}

function handleStoreFilter(keyword) {
  storeFilterKeyword.value = keyword || ''
}

function handleVendorChange() {
  model.value.storeId = undefined
  storeFilterKeyword.value = ''
  // 清空匹配状态
  envResolveMatchItems.value = []
  selectedEnvItemKey.value = ''
  model.value.resolvedItemKey = undefined
  // 如果有环境分组，重新匹配
  if (model.value.environment && model.value.vendorId) {
    resolveEnvItemForVendor()
  }
}

/**
 * 根据当前环境和商家编号，调用后端接口解析匹配的子环境列表。
 */
function resolveEnvItemForVendor() {
  const groupKey = String(model.value.environment || '').trim()
  const venderNo = String(model.value.vendorId || '').trim()
  if (!groupKey || !venderNo) {
    return
  }
  const requestSeq = ++envResolveRequestSeq
  envResolveLoading.value = true
  envResolveMatchItems.value = []
  selectedEnvItemKey.value = ''
  model.value.resolvedItemKey = undefined
  resolveLogPullEnvItem(groupKey, venderNo).then(response => {
    if (requestSeq !== envResolveRequestSeq) {
      return
    }
    const items = Array.isArray(response?.data) ? response.data : []
    envResolveMatchItems.value = items
    if (items.length === 1) {
      // 单匹配：自动选中
      selectedEnvItemKey.value = items[0].itemKey
      model.value.resolvedItemKey = items[0].itemKey
    } else if (items.length > 1) {
      // 多匹配：需要用户手动选择
      // 保持 selectedEnvItemKey 为空，等待用户选择
    }
  }).catch(() => {
    if (requestSeq !== envResolveRequestSeq) {
      return
    }
    envResolveMatchItems.value = []
  }).finally(() => {
    if (requestSeq === envResolveRequestSeq) {
      envResolveLoading.value = false
    }
  })
}

/**
 * 用户在多匹配时手动选择子环境。
 */
function handleEnvItemSelect(itemKey) {
  model.value.resolvedItemKey = itemKey
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
    // 商家变化后重新匹配子环境
    if (model.value?.environment && vendorId) {
      resolveEnvItemForVendor()
    }
  },
  { immediate: true }
)

watch(
  () => [props.environmentOptions, model.value?.environment],
  ([envOptions, currentEnv]) => {
    if (Array.isArray(envOptions) && envOptions.length && !currentEnv) {
      // environmentOptions 现在是 {key, label} 对象数组
      model.value.environment = envOptions[0].key
      // 环境自动填充后，如果已有商家，立即触发匹配，避免 vendorId watch 先于 environment 设置导致跳过匹配
      if (model.value?.vendorId) {
        resolveEnvItemForVendor()
      }
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

.env-resolve-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;
  font-size: 13px;
}

.env-resolve-multi {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.env-resolve-label {
  font-size: 13px;
  color: #606266;
}
</style>
