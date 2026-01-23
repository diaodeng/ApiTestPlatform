<template>
  <iframe
    :src="src"
    style="width:100%;height:800px;border:none"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ serviceId: string }>()

const src = computed(() =>
  `/clash-admin/ui/yacd/${props.serviceId}/`
)
</script>
