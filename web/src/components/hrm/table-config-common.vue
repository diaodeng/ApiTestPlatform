<script setup>
/*
* 各种配置小表哥的通用模板
* */
import {ElMessage, ElMessageBox} from 'element-plus';
import {inject, nextTick, onBeforeUnmount, onMounted, ref, toRaw, unref, useTemplateRef, watch} from "vue";
import {useClipboard} from "@vueuse/core";
import {Json, parseHeader} from "@/utils/tools.js";
import Sortable from "sortablejs";
import {ScopeEnum} from "@/components/hrm/enum.js";
import CellAssertComparator from "@/components/hrm/common/cells/cell-assert-comparator.vue";
import CellDictSelectChange from "@/components/hrm/common/cells/cell-dict-select-change.vue";

const props = defineProps({
  cols: {type: Object},
  tableTitle: {type: String, default: ""},
  toolFixTarget: {type: String, default: ""},
  toolFixOffset: {type: Number, default: 0}
});

const selfData = defineModel();
const multipleTable = useTemplateRef("tableRef");

const hrm_data_type = inject("hrm_data_type");
const hrm_comparator_dict = inject("hrm_comparator_dict");

const {copy, isSupported} = useClipboard({legacy: true});
const editingCellKey = ref("");
let sortableInstance = null;
let rowDataIdSeed = 0;

function ensureTableData() {
  if (!Array.isArray(selfData.value)) {
    selfData.value = [];
  }
  return selfData.value;
}

function buildColumnProps(col) {
  const columnProps = {};
  if (col?.prop) {
    columnProps.prop = col.prop;
  }
  if (col?.width) {
    columnProps.width = col.width;
  } else if (col?.minWidth) {
    columnProps.minWidth = col.minWidth;
  } else {
    columnProps.minWidth = 120;
  }
  if (col?.fixed !== undefined) {
    columnProps.fixed = col.fixed;
  }
  if (col?.align) {
    columnProps.align = col.align;
  }
  return columnProps;
}

function syncDataIds() {
  const tableData = ensureTableData();

  const usedIds = new Set();
  let nextSeed = rowDataIdSeed;

  tableData.forEach((item) => {
    const currentId = item?.dataId;
    if (currentId !== undefined && currentId !== null && !usedIds.has(String(currentId))) {
      usedIds.add(String(currentId));
      const numericId = Number(currentId);
      if (Number.isFinite(numericId) && numericId >= nextSeed) {
        nextSeed = numericId + 1;
      }
      return;
    }

    while (usedIds.has(String(nextSeed))) {
      nextSeed += 1;
    }
    item.dataId = nextSeed;
    usedIds.add(String(item.dataId));
    nextSeed += 1;
  });

  rowDataIdSeed = nextSeed;
}

function nextRowDataId() {
  syncDataIds();
  const nextId = rowDataIdSeed;
  rowDataIdSeed += 1;
  return nextId;
}

function addRow() {
  ensureTableData();

  selfData.value.push({
    key: '',
    value: '',
    enable: true,
    type: 'string',
    desc: '',
    dataId: nextRowDataId(),
    scope: ScopeEnum.case.value,
    sourceWay: 1,
    assert: "equals"
  });
  stopEditCell();
}

function delRow() {
  const selectedRows = multipleTable.value?.getSelectionRows?.() || [];
  if (selectedRows.length === 0) {
    ElMessageBox.alert('请选择要删除的行', '提示', {
      confirmButtonText: '确定',
    });
    return;
  }

  selectedRows.forEach((row) => {
    selfData.value.splice(selfData.value.indexOf(row), 1);
  });

  multipleTable.value?.clearSelection?.();
  stopEditCell();
}

function copyData() {
  try {
    if (!isSupported.value) {
      ElMessage.warning("您的浏览器不支持复制", "复制失败");
    }
    const selectedRows = multipleTable.value?.getSelectionRows?.() || [];
    if (selectedRows.length === 0) {
      ElMessage.warning("请选择要复制的行");
      return;
    }
    const copyRows = selectedRows.map((row) => {
      const nextLine = JSON.parse(JSON.stringify(toRaw(row)));
      nextLine.dataId = nextRowDataId();
      return nextLine;
    });
    copy(Json.compressJson(copyRows));
    ElMessage.success("复制成功");
  } catch (e) {
    ElMessage.warning("复制失败");
  }
}

function paste() {
  navigator.clipboard.readText().then((content) => {
    ensureTableData();
    let data = parseHeader(content);
    data = JSON.parse(JSON.stringify(data));
    data.forEach((item) => {
      item.dataId = nextRowDataId();
    });
    selfData.value.push(...data);
    stopEditCell();
  }).catch(() => {
    ElMessage.warning("粘贴失败");
  });
}

function changeSwitch(changeType) {
  const tableData = ensureTableData();
  let newStatus = null;
  tableData.forEach((item) => {
    if (changeType === "open") {
      newStatus = true;
    } else if (changeType === "close") {
      newStatus = false;
    } else if (changeType === "invert") {
      newStatus = !item.enable;
    } else {
      return;
    }
    item.enable = newStatus;
  });
}

function uniKey(row) {
  return row.dataId;
}

function buildCellKey(row, prop) {
  return `${row?.dataId ?? "unknown"}:${prop}`;
}

function isEditingCell(row, prop) {
  return editingCellKey.value === buildCellKey(row, prop);
}

function focusEditingField() {
  const tableEl = multipleTable.value?.$el;
  const inputEl = tableEl?.querySelector(".config-table-cell.is-editing input, .config-table-cell.is-editing textarea");
  inputEl?.focus?.();
  inputEl?.select?.();
}

function startEditCell(row, prop) {
  editingCellKey.value = buildCellKey(row, prop);
  nextTick(() => {
    focusEditingField();
  });
}

function stopEditCell() {
  editingCellKey.value = "";
}

function displayCellValue(value) {
  if (value === undefined || value === null || value === "") {
    return "点击编辑";
  }
  return String(value);
}

function isEmptyCellValue(value) {
  return value === undefined || value === null || value === "";
}

function setSort() {
  sortableInstance?.destroy();
  ensureTableData();
  const tableEl = multipleTable.value?.$el;
  const tbody = tableEl?.querySelector?.("tbody");
  if (!tbody) {
    return;
  }
  sortableInstance = new Sortable(tbody, {
    animation: 150,
    handle: ".el-checkbox",
    sort: true,
    onEnd: (evt) => {
      const oldItem = selfData.value[evt.oldIndex];
      selfData.value.splice(evt.oldIndex, 1);
      selfData.value.splice(evt.newIndex, 0, oldItem);
    },
  });
}

onMounted(() => {
  syncDataIds();
  nextTick(() => {
    setSort();
  });
});

watch(() => [selfData.value, Array.isArray(selfData.value) ? selfData.value.length : -1], () => {
  stopEditCell();
  nextTick(() => {
    syncDataIds();
    setSort();
  });
}, {immediate: true});

onBeforeUnmount(() => {
  sortableInstance?.destroy();
});
</script>

<template>
  <div class="config-table-container">
    <div>
      <el-text v-if="tableTitle"> {{ tableTitle }}</el-text>
      <div style="display: flex; justify-content: left; align-items: center; padding-bottom: 5px">
        <el-tooltip placement="top" content="增加行">
          <el-button size="small" @click="addRow" icon="CirclePlusFilled" type="success" circle></el-button>
        </el-tooltip>
        <el-tooltip placement="top" content="删除选中行">
          <el-button size="small" @click="delRow" icon="RemoveFilled" type="danger" circle></el-button>
        </el-tooltip>
        <el-tooltip placement="top" content="复制选中行">
          <el-button size="small" @click="copyData" icon="CopyDocument" type="warning" circle
                     :disabled="!isSupported"></el-button>
        </el-tooltip>
        <el-tooltip placement="top" content="粘贴">
          <el-button size="small" @click="paste" icon="DocumentCopy" type="info" circle></el-button>
        </el-tooltip>

        <slot name="tableHeader"></slot>
      </div>
    </div>
    <el-table
        table-layout="fixed"
        ref="tableRef"
        show-overflow-tooltip
        tooltip-effect="dark"
        style="width: 100%"
        size="small"
        border
        :row-key="uniKey"
        :data="selfData || []"
    >
      <el-table-column type="selection" width="30"></el-table-column>
      <el-table-column v-for="col in cols" :key="col.prop || col.name" :label="col.name" v-bind="buildColumnProps(col)">
        <template #header>
          <template v-if="col.type === 'switch'">
            <el-popover trigger="click">
              <template #reference>
                {{ col.name }}
              </template>
              <el-button size="small" type="primary" circle @click="changeSwitch('open')">全开</el-button>
              <el-button size="small" type="success" circle @click="changeSwitch('invert')">反选</el-button>
              <el-button size="small" type="warning" circle @click="changeSwitch('close')">全关</el-button>
            </el-popover>
          </template>
        </template>

        <template #default="{ row }">
          <template v-if="col.type === 'select'">
            <CellDictSelectChange v-model="row[col.prop]" :options="col.options || hrm_data_type"></CellDictSelectChange>
          </template>
          <template v-else-if="col.type === 'compaList'">
            <CellAssertComparator v-model:cell-data="row[col.prop]"
                                  :hrm_comparator_dict="hrm_comparator_dict"
            ></CellAssertComparator>
          </template>
          <template v-else-if="col.type === 'switch'">
            <div class="config-table-cell" :class="{'is-editing': isEditingCell(row, col.prop)}">
              <template v-if="isEditingCell(row, col.prop)">
                <el-switch v-model="row[col.prop]" @change="stopEditCell"></el-switch>
              </template>
              <div v-else class="config-table-cell__display" @click="startEditCell(row, col.prop)">
                <el-tag size="small" :type="row[col.prop] ? 'success' : 'info'">
                  {{ row[col.prop] ? '启用' : '禁用' }}
                </el-tag>
              </div>
            </div>
          </template>
          <template v-else>
            <div class="config-table-cell" :class="{'is-editing': isEditingCell(row, col.prop)}">
              <template v-if="isEditingCell(row, col.prop)">
                <el-input v-model="row[col.prop]" size="small" @blur="stopEditCell"></el-input>
              </template>
              <div v-else
                   class="config-table-cell__display"
                   :title="displayCellValue(row[col.prop])"
                   @click="startEditCell(row, col.prop)">
                <span class="config-table-cell__text"
                      :class="{'config-table-cell__placeholder': isEmptyCellValue(row[col.prop])}">
                  {{ displayCellValue(row[col.prop]) }}
                </span>
              </div>
            </div>
          </template>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped lang="scss">
.config-table-cell {
  min-height: 24px;
}

.config-table-cell__display {
  display: flex;
  align-items: center;
  min-height: 24px;
  width: 100%;
  min-width: 0;
  overflow: hidden;
  cursor: text;
}

.config-table-cell__text {
  display: inline-block;
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-table-cell__placeholder {
  color: var(--el-text-color-placeholder);
}
</style>
