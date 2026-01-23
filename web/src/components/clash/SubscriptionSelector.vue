<template>
  <el-dialog v-model="visible" title="切换订阅" width="400px">
    <el-select
      v-model="selected"
      placeholder="选择订阅"
      style="width:100%"
    >
      <el-option
        v-for="s in subs"
        :key="s.id"
        :label="s.name"
        :value="s.id"
      />
    </el-select>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" @click="apply">应用</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listSubscriptions } from '@/api/clash/subscriptions'
import { bindSubscription } from '@/api/clash/clash'

const props = defineProps<{ serviceId: string }>()
const emit = defineEmits(['success', 'close'])

const visible = ref(true)
const subs = ref<any[]>([])
const selected = ref('')

onMounted(async () => {
  subs.value = (await listSubscriptions()).data
})

function close() {
  visible.value = false
  emit('close')
}

async function apply() {
  await bindSubscription(props.serviceId, selected.value)
  emit('success')
  close()
}
</script>
