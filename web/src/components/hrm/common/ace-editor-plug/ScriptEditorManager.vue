<template>
  <div class="editor-layout">
    <ScriptSelector
      :blocks="blockList"
      :active="activeKey"
      :dirty-map="dirtyMap"
      @switch="switchBlock"
    />

    <div class="editor-container">
      <BaseAceCore ref="coreRef" />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, onMounted } from 'vue'
import * as ace from 'ace-builds'
import BaseAceCore from './BaseAceCore.vue'
import ScriptSelector from './ScriptSelector.vue'

import 'ace-builds/src-noconflict/mode-python'
import 'ace-builds/src-noconflict/mode-json'
import 'ace-builds/src-noconflict/mode-javascript'

/* =========================
   基础配置
========================= */

const AUTO_SAVE_DELAY = 1000 // 1秒防抖

const blockList = reactive([
  { key: 'preScript', label: '前置脚本', mode: 'python', readonly: false },
  { key: 'requestBody', label: '请求参数', mode: 'json', readonly: false },
  { key: 'postScript', label: '后置脚本', mode: 'python', readonly: false },
  { key: 'responseView', label: '响应数据', mode: 'json', readonly: true },
])

/* =========================
   状态管理
========================= */

const coreRef = ref(null)
let editor = null

const activeKey = ref(null)
const sessionMap = reactive({})
const sessionMeta = reactive({}) // { key: { dirty, timer } }
const dirtyMap = reactive({}) // 用于UI显示

/* =========================
   Session 创建
========================= */

function createSession(block, initialValue = '') {
  const session = ace.createEditSession(initialValue, `ace/mode/${block.mode}`)
  session.setUseWrapMode(true)

  sessionMap[block.key] = session

  sessionMeta[block.key] = {
    dirty: false,
    timer: null,
  }

  dirtyMap[block.key] = false

  // 监听变更
  session.on('change', () => {
    markDirty(block.key)
    scheduleAutoSave(block.key)
  })
}

/* =========================
   Dirty 标记
========================= */

function markDirty(key) {
  sessionMeta[key].dirty = true
  dirtyMap[key] = true
}

function clearDirty(key) {
  sessionMeta[key].dirty = false
  dirtyMap[key] = false
}

/* =========================
   自动保存
========================= */

function scheduleAutoSave(key) {
  const meta = sessionMeta[key]
  if (meta.timer) {
    clearTimeout(meta.timer)
  }

  meta.timer = setTimeout(() => {
    saveBlock(key)
  }, AUTO_SAVE_DELAY)
}

/* =========================
   JSON 自动格式化
========================= */

function formatJSONIfNeeded(key) {
  const block = blockList.find(b => b.key === key)
  if (!block || block.mode !== 'json') return

  const session = sessionMap[key]
  const value = session.getValue()

  try {
    const parsed = JSON.parse(value)
    const formatted = JSON.stringify(parsed, null, 2)

    if (formatted !== value) {
      const cursor = editor.getCursorPosition()
      session.setValue(formatted)
      editor.moveCursorToPosition(cursor)
    }
  } catch (e) {
    // JSON 非法，不格式化
    console.warn('JSON 格式错误，未自动格式化')
  }
}

/* =========================
   保存逻辑
========================= */

function saveBlock(key) {
  const meta = sessionMeta[key]
  if (!meta.dirty) return

  formatJSONIfNeeded(key)

  const value = sessionMap[key].getValue()

  // 这里替换为你的API调用
  console.log('自动保存:', key, value)

  clearDirty(key)
}

function saveAll() {
  for (const key in sessionMap) {
    saveBlock(key)
  }
}

/* =========================
   切换脚本块
========================= */

function switchBlock(key) {
  activeKey.value = key

  const block = blockList.find(b => b.key === key)

  if (!sessionMap[key]) {
    createSession(block)
  }

  editor.setSession(sessionMap[key])
  editor.setReadOnly(block.readonly)
}

/* =========================
   对外接口
========================= */

function getAllValues() {
  const result = {}
  for (const key in sessionMap) {
    result[key] = sessionMap[key].getValue()
  }
  return result
}

function setBlockValue(key, value) {
  const block = blockList.find(b => b.key === key)

  if (!sessionMap[key]) {
    createSession(block, value)
  } else {
    sessionMap[key].setValue(value)
  }

  clearDirty(key)
}

defineExpose({
  getAllValues,
  saveAll,
  switchBlock,
  setBlockValue
})

/* =========================
   初始化
========================= */

onMounted(async () => {
  await nextTick()
  editor = coreRef.value.getEditor()
  switchBlock(blockList[0].key)
})
</script>

<style scoped>
.editor-layout {
  display: flex;
  height: 100%;
}

.editor-container {
  flex: 1;
}
</style>