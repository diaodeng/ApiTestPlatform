<template>
   <i-frame v-model:src="url"></i-frame>
</template>

<script setup>
import iFrame from '@/components/iFrame'

const url = ref(window.BASE_API + "/docs")
</script>
