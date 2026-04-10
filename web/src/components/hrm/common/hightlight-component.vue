<template>
  <div class="code-wrapper">
    <pre class="preview hljs">
      <code v-html="highlighted"></code>
    </pre>
  </div>
</template>

<script setup>
import {computed, ref, watch} from 'vue'
import hljs from 'highlight.js/lib/core'

// 不预注册语言，动态加载
const languageMap = {
  json: () => import('highlight.js/lib/languages/json'),
  javascript: () => import('highlight.js/lib/languages/javascript'),
  python: () => import('highlight.js/lib/languages/python'),
  bash: () => import('highlight.js/lib/languages/bash'),
}

const props = defineProps({
  code: { type: String, default: '' },
  lang: { type: String, default: 'json' },
  theme: { type: String, default: 'dark' }, // dark | light
})

const loadedLangs = new Set()
const langReadyVersion = ref(0)

async function ensureLang(lang) {
  if (!lang || loadedLangs.has(lang)) return
  if (!languageMap[lang]) return

  const module = await languageMap[lang]()
  hljs.registerLanguage(lang, module.default)
  loadedLangs.add(lang)
  langReadyVersion.value += 1
}

const highlighted = computed(() => {
  langReadyVersion.value
  if (!props.code) return ''

  if (hljs.getLanguage(props.lang)) {
    return hljs.highlight(props.code, {
      language: props.lang,
    }).value
  }

  return hljs.highlightAuto(props.code).value
})

watch(
    () => props.lang,
    async (val) => {
      await ensureLang(val)
    },
    {immediate: true}
)
</script>

<style scoped>
.code-wrapper {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-light);
  background: #272822;
}

.preview {
  margin: 0;
  padding: 12px 14px;
  overflow: auto;
  min-height: 120px;
  line-height: 1.55;
  white-space: pre;
}

.preview code {
  display: block;
  font-family: Consolas, "Courier New", monospace;
  font-size: 13px;
}
</style>
