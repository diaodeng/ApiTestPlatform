<template>
  <div class="code-wrapper">
    <div class="toolbar" v-if="false">
      <span class="lang">{{ lang }}</span>
      <button class="copy-btn" @click="copy">Copy</button>
    </div>
    <pre ref="preRef" class="preview hljs">
      <code v-html="highlighted"></code>
    </pre>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
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

const preRef = ref(null)
const loadedLangs = new Set()

async function ensureLang(lang) {
  if (!lang || loadedLangs.has(lang)) return
  if (!languageMap[lang]) return

  const module = await languageMap[lang]()
  hljs.registerLanguage(lang, module.default)
  loadedLangs.add(lang)
}

const highlighted = computed(() => {
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
  { immediate: true }
)

async function copy() {
  await navigator.clipboard.writeText(props.code)
}
</script>

<style scoped>
.code-wrapper {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  font-size: 13px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  padding: 6px 10px;
  font-size: 12px;
  background: var(--toolbar-bg);
  border-bottom: 1px solid var(--border-color);
}

.copy-btn {
  cursor: pointer;
  border: none;
  background: transparent;
  color: var(--primary);
}

.preview {
  margin: 0;
  padding: 12px 16px;
  overflow-x: auto;
  counter-reset: line;
}

.preview code {
  display: block;
}

/* 行号实现 */
.preview code span {
  display: inline-block;
  width: 100%;
}

.preview code span::before {
  counter-increment: line;
  content: counter(line);
  display: inline-block;
  width: 36px;
  margin-right: 12px;
  color: #666;
  text-align: right;
}

/* 主题变量 */
:host,
.code-wrapper {
  --primary: #409eff;
  --border-color: #2a2a2a;
  --toolbar-bg: #1b1b1b;
}
</style>