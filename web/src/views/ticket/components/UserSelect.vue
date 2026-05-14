<template>
  <el-select
    v-model="selectedValue"
    filterable
    remote
    clearable
    reserve-keyword
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
    type: [Number, String],
    default: undefined
  },
  initialOption: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

const loading = ref(false)
const options = ref([])
const selectedValue = ref(props.modelValue)

watch(
  () => props.modelValue,
  value => {
    selectedValue.value = value
    syncInitialOption()
  }
)

watch(
  () => props.initialOption,
  () => syncInitialOption(),
  { deep: true }
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

function syncInitialOption() {
  if (props.modelValue === undefined || props.modelValue === null || props.modelValue === '') {
    return
  }
  const option = normalizeOption(props.initialOption)
  if (option && String(option.userId) === String(props.modelValue)) {
    upsertOption(option)
  }
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
  const selected = options.value.find(item => String(item.userId) === String(value))
  emit('update:modelValue', value)
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
