<template>
  <div ref="editorEl" class="editor-core"></div>
  <DictTag></DictTag>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, defineExpose } from 'vue'
import * as ace from 'ace-builds'
import "@/components/hrm/common/aceConfig.js"

const editorEl = ref(null)
let editor = null

onMounted(() => {
  editor = ace.edit(editorEl.value)
  editor.setTheme('ace/theme/monokai')
  editor.setOptions({
    fontSize: 14,
    showPrintMargin: false,
    tabSize: 2,
    useSoftTabs: true,
    wrap: true,
    highlightActiveLine: true,
  })
})

onBeforeUnmount(() => {
  editor?.destroy()
})

defineExpose({
  getEditor() {
    return editor
  }
})
</script>

<style scoped>
.editor-core {
  width: 100%;
  height: 100%;
}
</style>