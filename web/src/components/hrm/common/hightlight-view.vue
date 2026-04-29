<template>
  <pre class="preview">
    <code v-html="highlighted"></code>
  </pre>
</template>

<script setup>
import hljs from 'highlight.js'
import {computed} from 'vue'

const props = defineProps({
  code: String,
  lang: String,
})

const highlighted = computed(() => {
  return hljs.highlight(props.code, {
    language: props.lang
  }).value
})
</script>

<style>
.preview {
  padding: 12px;
  border-radius: 6px;
}
</style>