<template>
  <div ref="editor" class="editor-container" style="height: 600px;"></div>
</template>

<script>
import * as monaco from 'monaco-editor';
monaco.languages.register({ id: 'python' });
export default {
  name: 'MonacoEditor',
  props: {
    value: {
      type: String,
      default: ''
    },
    language: {
      type: String,
      default: 'python'
    }
  },
  watch: {
    value(newValue) {
      this.editor.setValue(newValue);
    }
  },
  mounted() {
    this.initEditor();
  },
  beforeUnmount() {
    if (this.editor) {
      this.editor.dispose();
    }
  },
  methods: {
    initEditor() {
      this.editor = monaco.editor.create(this.$refs.editor, {
        value: this.value,
        language: this.language,
        theme: 'vs-dark', // 可以选择其他主题
        automaticLayout: true,
        scrollBeyondLastLine: false,
        roundedSelection: false,
        readOnly: false,
        // 其他配置选项...
      });

      // 监听编辑器值的变化并更新 props
      this.editor.onDidChangeModelContent(() => {
        this.$emit('input', this.editor.getValue());
      });

      // 自动识别语言
      this.editor.onDidChangeModelLanguage(() => {
        console.log('Language changed to', this.editor.getModel().getLanguageId());
      });
    }
  }
};
</script>

<style scoped>
.editor-container {
  width: 100%;
  height: 100%;
  position: relative;
}
</style>