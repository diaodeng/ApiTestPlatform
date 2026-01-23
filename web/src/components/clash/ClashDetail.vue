<template>
  <el-card>
    <template #header>
      <span>Clash 实例：{{ serviceId }}</span>
      <el-button
        type="primary"
        size="small"
        style="float:right"
        @click="showSelector = true"
      >
        切换订阅
      </el-button>
    </template>

    <SubscriptionSelector
      v-if="showSelector"
      :service-id="serviceId"
      @close="showSelector = false"
      @success="showSelector = false"
    />

    <YacdFrame :service-id="serviceId" />
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import SubscriptionSelector from '@/components/clash/SubscriptionSelector.vue'
import YacdFrame from '@/components/clash/YacdFrame.vue'

const route = useRoute()
const serviceId = route.params.id as string
const showSelector = ref(false)
</script>
