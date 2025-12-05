<template>
  <teleport to="body">
    <div
        class="vt-editor"
        ref="editorRef"
        :style="{
left: position.left + 'px',
top: position.top + 'px',
width: position.width + 'px',
}"
    >
      <input
          ref="inputRef"
          v-model="value"
          class="vt-editor-input"
          @keydown.enter="confirm"
      />


      <ul class="vt-editor-list">
        <li
            v-for="item in filtered"
            :key="item"
            @click="select(item)"
        >
          {{ item }}
        </li>
      </ul>
    </div>
  </teleport>
</template>


<script setup>
import {ref, watch, onMounted} from 'vue';


const props = defineProps({
  row: Object,
  column: Object,
  position: Object,
});
const emit = defineEmits(['close']);


const inputRef = ref(null);
const value = ref(props.row[props.column.key]);


const filtered = ref([]);


watch(value, (v) => {
  filtered.value = props.column.suggestions
      ? props.column.suggestions.filter((s) => s.includes(v))
      : [];
});


function confirm() {
  props.row[props.column.key] = value.value;
  emit('close');
}


function select(v) {
  value.value = v;
  confirm();
}


onMounted(() => {
  inputRef.value.focus();
});
</script>


<style scoped>
.vt-editor {
  position: absolute;
  background: white;
  border: 1px solid #409eff;
  z-index: 9999;
  padding: 0;
  box-sizing: border-box;
}

.vt-editor-input {
  width: 100%;
  height: 36px;
  padding: 6px;
  border: none;
  outline: none;
  box-sizing: border-box;
}

.vt-editor-list {
  list-style: none;
  max-height: 150px;
  overflow: auto;
  margin: 0;
  padding: 0;
}

.vt-editor-list li {
  padding: 6px;
  cursor: pointer;
}

.vt-editor-list li:hover {
  background: #f0f0f0;
}
</style>