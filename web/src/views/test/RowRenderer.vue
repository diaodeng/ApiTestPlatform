<template>
  <div
      class="vt-row"
      :style="{ top: top + 'px' }"
  >
    <CellRenderer
        v-for="col in columns"
        :key="col.key"
        :row-data="row.data"
        :row-index="row.index"
        :column="col"
        @activate-editor="onActivateEditor"
    />
  </div>
</template>


<script setup>
const props = defineProps({
  row: Object,
  columns: Array,
  top: Number,
});


const emit = defineEmits(['activate-editor']);


function onActivateEditor(payload) {
  emit('activate-editor', payload);
}
</script>


<style scoped>
.vt-row {
  display: flex;
  position: absolute;
  height: 38px;
  line-height: 38px;
  border-bottom: 1px solid #f0f0f0;
}
</style>