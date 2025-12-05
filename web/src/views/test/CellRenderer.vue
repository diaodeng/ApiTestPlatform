<template>
  <div
      class="vt-cell"
      :style="{ width: column.width + 'px' }"
      @dblclick="activateEditor"
  >
    <span v-if="!column.editor">{{ rowData[column.key] }}</span>


    <!-- 简化版渲染逻辑，可替换为你的原始逻辑 -->
    <template v-else>
      <span>{{ rowData[column.key] }}</span>
    </template>
  </div>
</template>


<script setup>
const props = defineProps({
  rowData: Object,
  rowIndex: Number,
  column: Object,
});


const emit = defineEmits(['activate-editor']);


function activateEditor(evt) {
  const rect = evt.target.getBoundingClientRect();
  emit('activate-editor', {
    row: props.rowData,
    column: props.column,
    position: {
      left: rect.left + window.scrollX,
      top: rect.top + window.scrollY,
      width: rect.width,
      height: rect.height,
    },
  });
}
</script>


<style scoped>
.vt-cell {
  border-right: 1px solid #eee;
  padding: 0 8px;
  box-sizing: border-box;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
</style>