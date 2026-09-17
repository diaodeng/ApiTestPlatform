<template>
  <div class="query-result">
    <div class="result-meta">
      <el-tag v-if="result.sqlType" size="small">{{ result.sqlType }}</el-tag>
      <span class="meta-item">行数：{{ result.rowCount }}</span>
      <span class="meta-item">耗时：{{ result.elapsedMs }} ms</span>
      <el-tag v-if="result.truncated" type="warning" size="small">结果已截断（达到 maxRows 上限）</el-tag>
      <span v-if="!result.columns.length" class="meta-item">无返回列</span>
    </div>
    <el-table v-if="result.columns.length" :data="tableRows" border height="100%" size="small" class="result-table">
      <el-table-column type="index" label="#" width="56" fixed="left" />
      <el-table-column
        v-for="column in result.columns"
        :key="column.name"
        :prop="column.name"
        :min-width="columnWidth(column)"
        :label="columnLabel(column)"
        show-overflow-tooltip
      >
        <template #default="{ row }">{{ formatCell(row[column.name]) }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup name="QueryResultTable">
const props = defineProps({
  result: { type: Object, default: () => ({ columns: [], rows: [], rowCount: 0, truncated: false, elapsedMs: 0, sqlType: '' }) },
})

const tableRows = computed(() => props.result?.rows || [])

function columnLabel(column) {
  return column.type ? `${column.name}（${column.type}）` : column.name
}

function columnWidth(column) {
  const nameLength = (column.name || '').length
  return Math.max(120, Math.min(280, nameLength * 12 + 60))
}

/* 单元格格式化：null 显示占位符，对象/数组序列化，避免表格渲染空白或 [object Object]。 */
function formatCell(value) {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
</script>

<style scoped>
.query-result { display: flex; flex-direction: column; gap: 8px; height: 100%; }
.result-meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.meta-item { color: var(--el-text-color-secondary); font-size: 13px; }
.result-table { flex: 1; }
</style>
