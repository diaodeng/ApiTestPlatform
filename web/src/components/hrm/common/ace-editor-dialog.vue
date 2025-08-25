<script setup>
import AceEditor from "@/components/hrm/common/ace-editor.vue";

const showDialog = defineModel('showDialog');
const editContent = defineModel("editContent");

</script>

<template>
<el-dialog v-model="showDialog">
  <AceEditor :can-set="true" v-model:content="editContent"></AceEditor>
</el-dialog>
</template>

<style scoped lang="scss">

</style>