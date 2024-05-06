<template>
  <el-card class="json-container">
    <pre>{{ jsonData }}</pre>
  </el-card>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({
  json: Object
});

const jsonData = ref(JSON.stringify(props.json, null, 2));
</script>

<style scoped>
.json-container {
  margin: 10px;
  padding: 10px;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
}
</style>