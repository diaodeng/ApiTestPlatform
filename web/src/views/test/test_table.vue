<template>
  <div
      class="vt-root"
      ref="rootRef"
      @scroll="onScroll"
  >
    <TableHeader :columns="columns"/>


    <div
        class="vt-body"
        :style="{ height: totalHeight + 'px', position: 'relative' }"
    >
      <RowRenderer
          v-for="row in visibleRows"
          :key="row.index"
          :row="row"
          :columns="columns"
          :top="row.offsetTop"
          @activate-editor="openEditor"
      />
    </div>
  </div>


  <!-- 全局唯一编辑器 -->
  <GlobalAutocompleteEditor
      v-if="editor.active"
      :row="editor.row"
      :column="editor.column"
      :position="editor.position"
      @close="editor.active = false"
  />
</template>


<script setup>
import {ref, computed} from 'vue';
import TableHeader from './TableHeader.vue';
import RowRenderer from './RowRenderer.vue';
import GlobalAutocompleteEditor from './GlobalAutocompleteEditor.vue';
import useVirtualScroll from './useVirtualScroll.js';


const props = defineProps({
  rows: Array,
  columns: Array,
  rowHeight: {type: Number, default: 38},
});


const rootRef = ref();
const {visibleRows, totalHeight, onScroll} = useVirtualScroll(rootRef, props);


const editor = ref({
  active: false,
  row: null,
  column: null,
  position: null,
});


function openEditor(payload) {
  editor.value = {
    active: true,
    ...payload,
  };
}
</script>


<style scoped>
.vt-root {
  overflow: auto;
  position: relative;
  border: 1px solid #ddd;
  height: 100%;
}
</style>