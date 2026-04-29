<script lang="ts" setup>
import DiffEditor from "@/components/hrm/common/ace-editor-plug/DiffEditor.vue"
import {ref} from "vue";

const diffInstance = ref(null);

function clear() {
  diffInstance.value.clearContent();
}

</script>

<template>
  <div class="app-container">
    <div class="diff-header">
      <el-button @click="clear">清空</el-button>
    </div>
    <DiffEditor ref="diffInstance"></DiffEditor>
  </div>

</template>

<style scoped lang="scss">

</style>