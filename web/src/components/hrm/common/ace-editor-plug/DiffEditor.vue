<template>
  <div ref="container" class="diff-container"></div>
</template>

<script setup>
// https://github.com/ace-diff/ace-diff
import { onMounted, onBeforeUnmount, ref } from 'vue'
import AceDiff from 'ace-diff'
import 'ace-diff/styles.css'

import 'ace-builds/src-noconflict/ace'
import 'ace-builds/src-noconflict/mode-json'
import 'ace-builds/src-noconflict/theme-github'

const props = defineProps({
  left: String,
  right: String,
  mode: {
    type: String,
    default: 'json'
  }
})

const container = ref()
let diffInstance = null

onMounted(() => {
  diffInstance = new AceDiff({
    element: container.value,
    theme: 'ace/theme/github',
    left: {
      content: props.left || '',
      mode: `ace/mode/${props.mode}`,
    },
    right: {
      content: props.right || '',
      mode: `ace/mode/${props.mode}`,
    }
  });

  const { left, right } = diffInstance.getEditors();

  left.session.setUseWorker(false);
  right.session.setUseWorker(false);

  left.session.setNewLineMode('unix');
  right.session.setNewLineMode('unix');

  left.session.on('change', () => {
    // const value = left.getValue().replace(/\n$/, '')
    // if (value !== left.getValue()) {
    //   left.setValue(value, -1)
    // }
    diffInstance.diff();
  });

  right.session.on('change', () => {
    // const value = left.getValue().replace(/\n$/, '')
    // if (value !== left.getValue()) {
    //   left.setValue(value, -1)
    // }
    diffInstance.diff();
  });

})

onBeforeUnmount(() => {
  if (diffInstance) {
    diffInstance.destroy()
    diffInstance = null
  }
})
</script>

<style>
.diff-container {
  width: 100%;
  flex: 1;
  min-height: 0;
}
</style>