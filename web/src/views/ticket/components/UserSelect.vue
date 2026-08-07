<template>
  <el-select
    v-model="selectedValue"
    filterable
    remote
    clearable
    reserve-keyword
    :multiple="multiple"
    :collapse-tags="multiple"
    :collapse-tags-tooltip="multiple"
    :remote-method="remoteSearch"
    :loading="loading"
    placeholder="输入用户名/昵称/手机号搜索"
    style="width: 100%"
    @change="handleChange"
  >
    <el-option
      v-for="item in options"
      :key="item.userId"
      :label="item.label"
      :value="item.userId"
    >
      <div class="user-option">
        <span>{{ item.label }}</span>
        <span class="phone">{{ item.phonenumber || '-' }}</span>
      </div>
    </el-option>
  </el-select>
</template>

<script setup name="TicketUserSelect">
import { listTicketUserOptions } from '@/api/ticket/ticket'

const props = defineProps({
  modelValue: {
    type: [Number, String, Array],
    default: undefined
  },
  initialOption: {
    type: [Object, Array],
    default: null
  },
  rawLabel: {
    type: String,
    default: ''
  },
  multiple: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

const loading = ref(false)
const options = ref([])
const selectedValue = ref(props.multiple ? normalizeModelValues(props.modelValue) : props.modelValue)
const rawOptionValue = '__ticket_raw_user_label__'

watch(
  () => props.modelValue,
  value => {
    selectedValue.value = props.multiple ? normalizeModelValues(value) : value
    syncInitialOption()
  }
)

watch(
  () => props.initialOption,
  () => syncInitialOption(),
  { deep: true }
)

watch(
  () => props.rawLabel,
  () => syncInitialOption()
)

function normalizeOption(option) {
  if (!option || option.userId === undefined || option.userId === null) {
    return null
  }
  return {
    ...option,
    label: option.label || option.nickName || option.userName || String(option.userId)
  }
}

function upsertOption(option) {
  const normalized = normalizeOption(option)
  if (!normalized) return
  const index = options.value.findIndex(item => String(item.userId) === String(normalized.userId))
  if (index >= 0) {
    options.value.splice(index, 1, normalized)
  } else {
    options.value.unshift(normalized)
  }
}

// 将单选或多选 v-model 统一转成数组，便于多选场景回显和变更处理。
function normalizeModelValues(value) {
  if (Array.isArray(value)) {
    return value.filter(item => item !== undefined && item !== null && item !== '')
  }
  if (value === undefined || value === null || value === '') {
    return []
  }
  return [value]
}

function syncInitialOption() {
  const rawLabel = String(props.rawLabel || '').trim()
  const modelValues = normalizeModelValues(props.modelValue)
  if (!modelValues.length) {
    if (rawLabel) {
      selectedValue.value = rawOptionValue
      upsertOption({
        userId: rawOptionValue,
        userName: rawLabel,
        nickName: rawLabel,
        label: rawLabel,
        isRawLabel: true
      })
    }
    return
  }
  const initialOptions = Array.isArray(props.initialOption) ? props.initialOption : [props.initialOption]
  initialOptions
    .map(option => normalizeOption(option))
    .filter(option => option && modelValues.some(value => String(value) === String(option.userId)))
    .forEach(option => upsertOption(option))
}

function remoteSearch(keyword) {
  loading.value = true
  listTicketUserOptions({ keyword, limit: 20 }).then(response => {
    options.value = response.data || []
    syncInitialOption()
  }).finally(() => {
    loading.value = false
  })
}

function handleChange(value) {
  if (props.multiple) {
    const values = normalizeModelValues(value).filter(item => item !== rawOptionValue)
    const selectedItems = options.value.filter(item => values.some(userId => String(userId) === String(item.userId)))
    emit('update:modelValue', values)
    emit('change', selectedItems)
    return
  }
  const selected = options.value.find(item => String(item.userId) === String(value))
  emit('update:modelValue', value === rawOptionValue ? undefined : value)
  emit('change', selected || null)
}

syncInitialOption()
remoteSearch('')
</script>

<style scoped>
.user-option {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.phone {
  color: #909399;
  font-size: 12px;
}
</style>
