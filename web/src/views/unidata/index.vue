<template>
  <div class="app-container unidata-page">
    <!-- 顶部工具栏：数据源 / 引擎 / 行数 / 超时 -->
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-item">
          <span class="toolbar-label">数据源</span>
          <el-select v-model="activeSource" style="width: 220px" @change="onSourceChange">
            <el-option v-for="item in sources" :key="item.code" :label="item.name" :value="item.code" />
          </el-select>
        </div>
        <div class="toolbar-item">
          <span class="toolbar-label">引擎</span>
          <el-select v-model="engine" style="width: 160px" :disabled="engineLoading || !engineOptions.length" :loading="engineLoading">
            <el-option v-for="option in engineOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </div>
        <div class="toolbar-item">
          <span class="toolbar-label">最大行数</span>
          <el-input-number v-model="maxRows" :min="1" :max="10000" :step="100" style="width: 130px" />
        </div>
        <div class="toolbar-item">
          <span class="toolbar-label">超时(秒)</span>
          <el-input-number v-model="timeoutSeconds" :min="1" :max="600" :step="30" style="width: 120px" />
        </div>
        <div class="toolbar-tip">仅支持单条 SELECT / WITH / EXPLAIN / SHOW CREATE TABLE，只读查询</div>
      </div>
    </el-card>

    <div class="main-layout">
      <!-- 左侧：库 / 表 / 字段 懒加载树 -->
      <el-card shadow="never" class="browser-card">
        <template #header>
          <div class="browser-header">
            <span>库 / 表 / 字段</span>
            <el-button link type="primary" icon="Refresh" title="重新加载库列表" @click="refreshTree" />
          </div>
        </template>
        <el-input v-model="dbFilter" placeholder="过滤库名" clearable size="small" class="db-filter" />
        <div v-loading="dbLoading" class="tree-wrap">
          <el-tree
            ref="treeRef"
            :key="treeKey"
            :props="treeProps"
            lazy
            :load="loadNode"
            node-key="key"
            :filter-node-method="filterNode"
            @node-click="onNodeClick"
            class="db-tree"
          >
            <template #default="{ data }">
              <span v-if="data.type === 'db'" class="node-line">
                <span class="node-main" :title="data.label">{{ data.label }}</span>
                <el-tag size="small" :type="data.layer === 'stable' ? 'success' : 'warning'">{{ data.layer }}</el-tag>
              </span>
              <span v-else-if="data.type === 'table'" class="node-line">
                <span class="node-main" :title="data.fullName">{{ data.label }}</span>
                <span class="node-extra">{{ data.chineseName }}</span>
                <el-button class="node-action" link type="primary" size="small" icon="Plus" title="插入查询模板到 SQL" @click.stop="insertTableToSql(data)" />
              </span>
              <span v-else-if="data.type === 'more'" class="node-line node-more-line">
                <span v-if="data.loading" class="node-extra">加载中…</span>
                <span v-else class="node-more">{{ data.label }}</span>
              </span>
              <span v-else class="node-line">
                <span class="node-main">{{ data.label }}</span>
                <span class="node-extra node-type">{{ data.colType }}</span>
                <span class="node-extra node-comment" :title="data.comment">{{ data.comment }}</span>
              </span>
            </template>
          </el-tree>
        </div>
      </el-card>

      <!-- 右侧：SQL 编辑 + 结果 -->
      <el-card shadow="never" class="sql-card">
        <el-input
          ref="sqlInputRef"
          v-model="sqlText"
          type="textarea"
          :rows="8"
          placeholder="输入只读 SQL，例如：SELECT * FROM dim_dm.dim_supplier LIMIT 10（Ctrl+Enter 执行）"
          class="sql-editor"
          @keydown.ctrl.enter.prevent="runQuery"
        />
        <div class="sql-actions">
          <el-button type="primary" icon="CaretRight" :loading="queryLoading" @click="runQuery">执行查询</el-button>
          <el-button @click="sqlText = ''">清空</el-button>
        </div>
        <div v-if="queryError" class="query-error">{{ queryError }}</div>
        <div class="result-container">
          <QueryResultTable v-if="queryResult" :result="queryResult" />
          <div v-else-if="!queryLoading && !queryError" class="empty-tip">执行查询后在这里查看列与结果</div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup name="Unidata">
import { executeUnidataQuery, listUnidataColumns, listUnidataDatabases, listUnidataEngines, listUnidataSources, listUnidataTables } from '@/api/unidata'
import QueryResultTable from './components/QueryResultTable.vue'

const { proxy } = getCurrentInstance()

const sources = ref([])
const activeSource = ref('')
const engine = ref('')
const engineLoading = ref(false)
const engineStatuses = ref([])
const maxRows = ref(200)
const timeoutSeconds = ref(180)

const databases = ref([])
const dbLoading = ref(false)
const dbFilter = ref('')
const treeRef = ref()
const treeKey = ref(0)
const treeProps = { label: 'label', children: 'children', isLeaf: 'isLeaf' }
/* 表清单分块大小：展开库先加载 200 张，滑到底部点「加载更多表」继续，避免一次渲染上千节点 */
const TABLE_CHUNK = 200

const sqlText = ref('')
const sqlInputRef = ref()
const queryLoading = ref(false)
const queryResult = ref(null)
const queryError = ref('')

/* 引擎标签映射：kyuubi 是 SQL 网关，实际执行引擎为 Spark SQL。 */
const engineLabels = { kyuubi: 'kyuubi（Spark SQL）', starrocks: 'starrocks' }

/* 引擎下拉只展示探测可用的引擎，不可用（如 UAT 的 starrocks）不出现。 */
const engineOptions = computed(() => engineStatuses.value
  .filter(item => item.available)
  .map(item => ({ value: item.engine, label: engineLabels[item.engine] || item.engine })))

/* 库名过滤：el-tree filter 只作用于已加载的库根节点，未展开的子树跟随父节点隐藏。 */
watch(dbFilter, value => { treeRef.value?.filter(value) })

function filterNode(value, data) {
  if (!value) return true
  if (data.type !== 'db') return true
  return data.label.toLowerCase().includes(String(value).trim().toLowerCase())
}

/* 加载启用的大数据数据源，默认选中第一个并联动加载引擎与库树。 */
function loadSources() {
  return listUnidataSources().then(response => {
    sources.value = response.data || []
    if (sources.value.length && !activeSource.value) {
      activeSource.value = sources.value[0].code
      loadEngines()
      refreshTree()
    }
  })
}

function onSourceChange(code) {
  engineStatuses.value = []
  engine.value = ''
  loadEngines()
  refreshTree()
}

/* 动态探测当前数据源可用的引擎：只展示可用项，默认选中数据源配置的 defaultEngine。 */
function loadEngines() {
  if (!activeSource.value) return
  engineLoading.value = true
  listUnidataEngines(activeSource.value)
    .then(response => {
      engineStatuses.value = response.data || []
      const available = engineStatuses.value.filter(item => item.available).map(item => item.engine)
      if (!available.includes(engine.value)) {
        const source = sources.value.find(item => item.code === activeSource.value)
        const preferred = source?.defaultEngine
        engine.value = available.includes(preferred) ? preferred : (available[0] || '')
      }
      if (!available.length) proxy.$modal.msgWarning(`数据源 ${activeSource.value} 暂无可用查询引擎`)
    })
    .finally(() => { engineLoading.value = false })
}

/* 重建懒加载树：首次加载与切换数据源时触发，根节点为权限库清单。 */
function refreshTree() {
  if (!activeSource.value) return
  treeKey.value++
}

/* el-tree 懒加载：第 0 层库 -> 第 1 层表（分块）-> 第 2 层字段（名称/类型/备注）。 */
function loadNode(node, resolve) {
  if (node.level === 0) {
    dbLoading.value = true
    listUnidataDatabases(activeSource.value)
      .then(response => {
        databases.value = response.data || []
        resolve(databases.value.map(d => ({ key: `db:${d.name}`, type: 'db', label: d.name, layer: d.layer, isLeaf: false })))
      })
      .catch(() => resolve([]))
      .finally(() => { dbLoading.value = false })
    return
  }
  if (node.data.type === 'db') {
    listUnidataTables(activeSource.value, { dbName: node.data.label, pageNo: 1, pageSize: TABLE_CHUNK })
      .then(response => {
        const data = response.data || {}
        const rows = data.rows || []
        const children = rows.map(toTableNode)
        if ((data.total || 0) > rows.length) children.push(moreTablesNode(node.data.label, rows.length, data.total))
        resolve(children)
      })
      .catch(() => resolve([]))
    return
  }
  if (node.data.type === 'table') {
    listUnidataColumns(activeSource.value, node.data.fullName)
      .then(response => {
        const columns = response.data || []
        resolve(columns.map(c => ({ key: `col:${node.data.fullName}.${c.name}`, type: 'column', label: c.name, colType: c.type, comment: c.comment, isLeaf: true })))
      })
      .catch(() => resolve([]))
    return
  }
  resolve([])
}

function toTableNode(table) {
  return { key: `tb:${table.name}`, type: 'table', label: table.tableName, fullName: table.name, chineseName: table.chineseName, isLeaf: false }
}

function moreTablesNode(dbName, loaded, total) {
  return { key: `more:tb:${dbName}`, type: 'more', dbName, loaded, total, label: `加载更多表（剩 ${total - loaded}）`, isLeaf: true }
}

/* 点击「加载更多表」：拉取下一块并追加到该库节点下，保持已展开子树与滚动位置。 */
function onNodeClick(data) {
  if (data.type !== 'more' || data.loading) return
  const dbKey = `db:${data.dbName}`
  const dbNode = treeRef.value?.getNode(dbKey)
  if (!dbNode) return
  data.loading = true
  const pageNo = Math.floor(data.loaded / TABLE_CHUNK) + 1
  listUnidataTables(activeSource.value, { dbName: data.dbName, pageNo, pageSize: TABLE_CHUNK })
    .then(response => {
      const result = response.data || {}
      const rows = result.rows || []
      treeRef.value.remove(data.key)
      rows.forEach(row => treeRef.value.append(toTableNode(row), dbKey))
      const loaded = data.loaded + rows.length
      const total = result.total || data.total
      if (loaded < total) treeRef.value.append(moreTablesNode(data.dbName, loaded, total), dbKey)
    })
    .catch(error => {
      data.loading = false
      proxy.$modal.msgError(error?.message || '加载更多表失败')
    })
}

/* 点击表节点上的按钮把查询模板写入 SQL 编辑器：编辑器为空时填模板，否则追加。 */
function insertTableToSql(data) {
  const template = `SELECT *\nFROM ${data.fullName}\nLIMIT 10`
  if (!sqlText.value.trim()) {
    sqlText.value = template
    return
  }
  sqlText.value = `${sqlText.value.replace(/\s+$/, '')}\n\n${template}\n`
}

/* 执行只读 SQL；Ctrl+Enter 亦可触发。 */
function runQuery() {
  if (!activeSource.value) return proxy.$modal.msgWarning('请先选择数据源')
  if (!sqlText.value.trim()) return proxy.$modal.msgWarning('请输入 SQL')
  queryLoading.value = true
  queryError.value = ''
  queryResult.value = null
  executeUnidataQuery(activeSource.value, {
    sql: sqlText.value,
    maxRows: maxRows.value,
    timeoutSeconds: timeoutSeconds.value,
    engine: engine.value || null,
  })
    .then(response => { queryResult.value = response.data })
    .catch(error => { queryError.value = error?.message || '查询失败' })
    .finally(() => { queryLoading.value = false })
}

loadSources()
</script>

<style scoped>
.unidata-page { display: flex; flex-direction: column; gap: 12px; height: calc(100vh - 120px); }
.toolbar-card :deep(.el-card__body) { padding: 12px 16px; }
.toolbar { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
.toolbar-item { display: flex; align-items: center; gap: 8px; }
.toolbar-label { color: var(--el-text-color-secondary); font-size: 13px; }
.toolbar-tip { color: var(--el-text-color-placeholder); font-size: 12px; margin-left: auto; }
.main-layout { display: flex; gap: 12px; flex: 1; min-height: 0; }
.browser-card { width: 320px; flex-shrink: 0; display: flex; flex-direction: column; }
.browser-card :deep(.el-card__body) { flex: 1; overflow: auto; display: flex; flex-direction: column; }
.browser-header { display: flex; justify-content: space-between; align-items: center; }
.db-filter { margin-bottom: 8px; }
.tree-wrap { flex: 1; overflow: auto; }
.db-tree { background: transparent; }
.db-tree :deep(.el-tree-node__content) { height: 28px; border-radius: 4px; }
.node-line { display: flex; align-items: center; gap: 6px; overflow: hidden; flex: 1; padding-right: 4px; }
.node-main { flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-extra { color: var(--el-text-color-secondary); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-type { color: var(--el-color-primary); flex-shrink: 0; }
.node-comment { color: var(--el-text-color-placeholder); }
.node-action { display: none; flex-shrink: 0; }
.el-tree-node__content:hover .node-action { display: inline-flex; }
.node-more-line { color: var(--el-color-primary); cursor: pointer; }
.node-more { font-size: 13px; }
.sql-card { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.sql-card :deep(.el-card__body) { flex: 1; display: flex; flex-direction: column; gap: 10px; overflow: hidden; }
.sql-editor :deep(textarea) { font-family: Consolas, Monaco, monospace; }
.sql-actions { display: flex; gap: 8px; }
.query-error { color: var(--el-color-danger); font-size: 13px; white-space: pre-wrap; }
.result-container { flex: 1; min-height: 0; }
.empty-tip { color: var(--el-text-color-placeholder); font-size: 13px; text-align: center; padding: 16px 0; }
</style>
