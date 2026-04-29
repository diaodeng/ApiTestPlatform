<template>
  <div class="log-wrapper">
    <div class="toolbar">
      <el-switch
          v-model="wrap"
          active-text="自动换行"
          inactive-text="不换行"
      />
    </div>
    <div class="log-container" :class="{'wrap-mode': wrap}" ref="containerRef" @scroll="handleScroll">
      <div
          v-for="(log, index) in logLines"
          :key="index"
          class="log-line"
          :class="`log-${log.level}`"
      >
        <template v-for="(token, i) in log.tokens" :key="i">
    <span :class="token.type ? `log-${token.type}` : ''">
      {{ token.text }}
    </span>
        </template>
      </div>
    </div>
  </div>

</template>

<script setup lang="ts">
import {ref, computed, watch, nextTick} from 'vue'

interface LogToken {
  text: string
  type: string
}

interface ParsedLog {
  level: string
  id: number
  tokens: LogToken[]
}

interface Props {
  logs: string | string[]
  highlightKeywords?: string[]
  autoScroll?: boolean
  maxLineLength?: number
}

const props = withDefaults(defineProps<Props>(), {
  highlightKeywords: () => [],
  autoScroll: true,
  maxLineLength: 1000
});

const containerRef = ref<HTMLElement | null>(null);
const isScrollLocked = ref(false);
const wrap = ref(false);   // 日志是否换行
const logLines = ref<ParsedLog[]>([]);
let id = 1;


function parseLogLine(line: string): ParsedLog | null {
  console.log(line)
  // 根据常见日志格式写一个正则
  // const regex = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) \| (\w+)\s* \| ([^:]+):([^:]+):(\d+) - (.*)$/
  const regex = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})(\s\|\s)([A-Z]+)(\s+)(\|\s)([^:]+:[^:]+:\d+)(\s-\s)(.*)$/

  const match = line.match(regex)

  if (!match) {
    return {
      id: id++,
      level: 'info',
      tokens: [{text: line, type: 'content'}]
    }
  }

  return {
    level: match[3].toLowerCase(),
    id: id++,
    tokens: [
      {text: match[1], type: 'time'},
      {text: match[2]}, // 原样 |
      {text: match[3], type: 'level'},
      {text: match[4]}, // level对齐空格
      {text: match[5]}, // |
      {text: match[6], type: 'logger'},
      {text: match[7]}, // -
      {text: match[8], type: 'content'}
    ]
  }

}

/* -----------------------
   关键字高亮处理
------------------------ */

function escapeHtml(str: string) {
  return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
}

function splitLogText(text: string | Array<string>): string[] {
  if (!text) return [];
  return typeof text === 'string' ? text.split(/\r?\n/) : text;
}

function highlight(text: string) {
  let result = escapeHtml(text)

  props.highlightKeywords.forEach(keyword => {
    if (!keyword) return
    const regex = new RegExp(`(${keyword})`, 'gi')
    result = result.replace(
        regex,
        `<span class="log-highlight">$1</span>`
    )
  })

  return result
}

function appendLog(line: string) {
  logLines.value.push(parseLogLine(line))

  if (logLines.value.length > props.maxLineLength) {
    logLines.value.splice(
        0,
        logLines.value.length - props.maxLineLength
    )
  }
}

/* -----------------------
   自动滚动锁定逻辑
------------------------ */

function handleScroll() {
  const el = containerRef.value
  if (!el) return

  const threshold = 10

  const isAtBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight < threshold

  isScrollLocked.value = !isAtBottom
}

defineExpose({appendLog});

watch(
    () => logLines.value.length,
    async () => {
      if (!props.autoScroll) return
      if (isScrollLocked.value) return

      await nextTick()
      const el = containerRef.value
      if (el) {
        el.scrollTop = el.scrollHeight
      }
    }
)
watch(
    () => props.logs,
    (newLogs) => {
      logLines.value = [];
      if (!newLogs) return
      splitLogText(newLogs).forEach(line => {
        logLines.value.push(parseLogLine(line));
      });
    },
    {immediate: true}
)

</script>

<style scoped>

.log-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.log-container {
  border-radius: 5px;
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: #1e1e1e;
  font-family: monospace;
  font-size: 13px;
  padding: 8px;
  white-space: pre;
}

.log-container.wrap-mode {
  white-space: pre-wrap;
}

.toolbar {
  flex-shrink: 0; /* 不压缩 */
}

.log-line {
  word-break: break-word;
  line-height: 1.6;
}

.log-time {
  color: #888;
}

.log-level {
  font-weight: bold;
}

.log-info .log-level {
  color: #4fc1ff;
}

.log-warn .log-level {
  color: #f0ad4e;
}

.log-error .log-level {
  color: #ff6b6b;
}

.log-logger {
  color: #c586c0;
}

.log-content {
  color: #ddd;
}


.log-highlight {
  background: #264f78;
  color: #fff;
  padding: 0 2px;
  border-radius: 2px;
}
</style>
