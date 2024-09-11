<script setup>
import ContextMenu from "@/components/hrm/common/context-menu.vue";
import {CaseStepTypeEnum, EditTableContextMenuEnum} from "@/components/hrm/enum.js";
import {decompressText, compressData} from "@/utils/tools.js"

const ColumnTypeEnum = {
  switch: 1,
  input: 2,
  select: 3
}
const columnsRef = defineModel("columnsRef");
const tableDatasRef = defineModel("tableDatasRef");

const props = defineProps({
  tableTitle: {
    type: String,
    default: "表格"
  }
})

const emit = defineEmits(["submit"])

const cellContextMenuData = [
  {
    title: '编辑',
    menuType: EditTableContextMenuEnum.editCell,
    icon: 'Menu',
    divided: true
  }, {
    title: '删除行',
    menuType: EditTableContextMenuEnum.DeleteRow,
    icon: 'Menu',
    divided: true
  },
  {
    title: '向上新增一行',
    menuType: EditTableContextMenuEnum.InsertRowBefore,
    icon: 'Menu'
  },
  {
    title: '向下新增一行',
    menuType: EditTableContextMenuEnum.InsertRowAfter,
    icon: 'Menu',
    divided: true
  }, {
    title: '删除列',
    menuType: EditTableContextMenuEnum.DeleteColumn,
    icon: 'Menu',
    divided: true
  },
  {
    title: '向前新增一列',
    menuType: EditTableContextMenuEnum.InsertColumnBefore,
    icon: 'Menu',
    divided: true
  },
  {
    title: '向后新增一列',
    menuType: EditTableContextMenuEnum.InsertColumnAfter,
    icon: 'Menu',
    divided: true
  },
  // {
  //   title: '1-3 菜单',
  //   icon: 'https://element-plus.org/images/element-plus-logo.svg',
  //   children: [
  //     {title: '1-3-1 菜单', remark: 'Ctrl+A'},
  //     {title: '1-3-2 菜单', disabled: true},
  //     {
  //       title: '1-3-3 菜单',
  //       className: 'custom-red-menu-item'
  //     }
  //   ],
  //   disabled: true
  // }
]

const headerContextMenuData = [
  {
    title: '编辑',
    menuType: EditTableContextMenuEnum.editHeader,
    icon: 'Menu',
    divided: true
  }, {
    title: '隐藏',
    menuType: EditTableContextMenuEnum.HideColumn,
    icon: 'Menu',
    divided: true
  }, {
    title: '删除列',
    menuType: EditTableContextMenuEnum.DeleteColumn,
    icon: 'Menu',
    divided: true
  },
  {
    title: '向前新增一列',
    menuType: EditTableContextMenuEnum.InsertColumnBefore,
    icon: 'Menu',
    divided: true
  },
  {
    title: '向后新增一列',
    menuType: EditTableContextMenuEnum.InsertColumnAfter,
    icon: 'Menu',
    divided: true
  },
  // {
  //   title: '1-3 菜单',
  //   icon: 'https://element-plus.org/images/element-plus-logo.svg',
  //   children: [
  //     {title: '1-3-1 菜单', remark: 'Ctrl+A'},
  //     {title: '1-3-2 菜单', disabled: true},
  //     {
  //       title: '1-3-3 菜单',
  //       className: 'custom-red-menu-item'
  //     }
  //   ],
  //   disabled: true
  // }
]

const initTableColumn = {
  label: "启用",
  prop: "__enable",
  show: true,
  enable: true,
  type: ColumnTypeEnum.switch
}
const initTableRow = {
  __enable: {
    content: true,
    edit: false,
  }
}

const contextMenuSelectCell = ref({row: null, column: null, cell: null, e: null});
const contextMenu = reactive({
  show: false,
  x: 0,
  y: 0,
  data: cellContextMenuData,
  onSelect: (item) => {
    contextMenuClickHandle(item.menuType);
    // ElMessage.success('选中了' + item.title)
  }
})
const newDataInfo = reactive({
  row: 1,
  column: 1,
})
const editeHeader = ref(false);
const editeHeaderData = ref({desc: null, key: null, oldKey: null});

// watch([() => props.tableHeaders, () => props.tableData], ([newHeader, newData]) => {
//   debugger
//   columnsRef.value = newHeader ? decompressText(newHeader) : [];
//   tableDatasRef.value = newData ? decompressText(newData) : [];
// })

function cellDblclick(row, column, cell, event) {
  row[column.rawColumnKey].edit = true;

  const editIputEl = cell.querySelector('textarea');
  editIputEl && nextTick(() => {
    editIputEl.focus()
  })
}

function headerDbClick(column, index) {
  const col = column;
  const currentDataIndex = columnsRef.value.findIndex((item) => item.prop === col.columnKey);
  if (!currentDataIndex) return;
  const currentData = columnsRef.value[currentDataIndex];
  editeHeaderData.value.desc = currentData.label;
  editeHeaderData.value.key = currentData.prop;
  editeHeaderData.value.oldKey = currentData.prop;
  editeHeader.value = true;
}

function handleHeaderRightClick(column, event) {
  contextMenuSelectCell.value.column = column;
  contextMenuSelectCell.value.e = event;
  contextMenu.data = headerContextMenuData;
  contextMenu.x = event.clientX;
  contextMenu.y = event.clientY;
  contextMenu.show = true;
  event.preventDefault();

}

function handleRowRightClick(row, column, event) {
  // event.preventDefault();
}

function handleCellRightClick(row, column, cell, event) {
  contextMenuSelectCell.value.row = row;
  contextMenuSelectCell.value.column = column;
  contextMenuSelectCell.value.cell = cell;
  contextMenuSelectCell.value.e = event;
  contextMenu.data = cellContextMenuData;
  contextMenu.x = event.clientX;
  contextMenu.y = event.clientY;
  contextMenu.show = true;
  event.preventDefault();
}

function contextMenuClickHandle(menuType) {
  if (menuType === EditTableContextMenuEnum.InsertRowBefore || menuType === EditTableContextMenuEnum.InsertRowAfter) {

    const row = contextMenuSelectCell.value.row;
    let currentDataIndex = tableDatasRef.value.indexOf(row);
    addRowAndColumnHandle(undefined, 1, menuType, currentDataIndex);

  } else if (menuType === EditTableContextMenuEnum.editHeader) {

    const col = contextMenuSelectCell.value.column;
    const currentDataIndex = columnsRef.value.findIndex((item) => item.prop === col.columnKey);
    if (!currentDataIndex) return;
    const currentData = columnsRef.value[currentDataIndex];
    editeHeaderData.value.desc = currentData.label;
    editeHeaderData.value.key = currentData.prop;
    editeHeaderData.value.oldKey = currentData.prop;
    editeHeader.value = true;

  } else if (menuType === EditTableContextMenuEnum.InsertColumnBefore || menuType === EditTableContextMenuEnum.InsertColumnAfter) {

    const col = contextMenuSelectCell.value.column;
    const currentDataIndex = columnsRef.value.findIndex((item) => item.prop === col.columnKey);
    addRowAndColumnHandle(
        1,
        undefined,
        menuType,
        currentDataIndex
    );

  } else if (menuType === EditTableContextMenuEnum.DeleteRow) {

    const row = contextMenuSelectCell.value.row;
    let currentDataIndex = tableDatasRef.value.indexOf(row);
    tableDatasRef.value.splice(currentDataIndex, 1);

  } else if (menuType === EditTableContextMenuEnum.HideColumn) {

    const col = contextMenuSelectCell.value.column;
    const currentDataIndex = columnsRef.value.findIndex((item) => item.prop === col.columnKey);
    columnsRef.value[currentDataIndex].show = !columnsRef.value[currentDataIndex].show;

  } else if (menuType === EditTableContextMenuEnum.DeleteColumn) {

    const col = contextMenuSelectCell.value.column;
    const currentDataIndex = columnsRef.value.findIndex((item) => item.prop === col.columnKey);
    columnsRef.value.splice(currentDataIndex, 1);

  }
}

function addRowAndColumnHandle(columnNum, rowNum, position, index) {
  const row = rowNum;
  const column = columnNum;
  if (column) {
    if (columnsRef.value.length <= 0) {
      let newData = JSON.parse(JSON.stringify(initTableColumn));
      newData.width = "70px";
      columnsRef.value.push(newData);
    }
    for (let i = 0; i < column; i++) {
      // let newData = structuredClone(toValue(toRaw(columnsRef.value[2])));
      let newData = JSON.parse(JSON.stringify(initTableColumn));
      let num = columnsRef.value.length;
      newData.label = "新增列" + num;
      newData.prop = "new" + num;
      newData.show = true;
      newData.type = ColumnTypeEnum.input;
      // columnsRef.value.push(newData);
      let insertIndex = index ? index : columnsRef.value.length - 1;
      columnsRef.value.splice(
          position === EditTableContextMenuEnum.InsertColumnBefore ? insertIndex : insertIndex + 1,
          0,
          newData)

      tableDatasRef.value.forEach((item) => {
        item[newData.prop] = JSON.parse(JSON.stringify({
          content: "",
          edit: false
        }))
      })
    }
  }
  if (row) {
    for (let i = 0; i < row; i++) {
      // let newData = structuredClone(toValue(toRaw(tableDatasRef.value[0])));
      let newData = {};
      for (let newDataKey of columnsRef.value) {
        if (newDataKey.prop === '__enable') {
          newData[newDataKey.prop] = {content: true, edit: false};
        } else {
          newData[newDataKey.prop] = {content: "", edit: false};
        }
      }
      let insertIndex = index ? index : tableDatasRef.value.length - 1;
      tableDatasRef.value.splice(
          position === EditTableContextMenuEnum.InsertRowBefore ? insertIndex : insertIndex + 1,
          0,
          newData)
      // tableDatasRef.value.push(newData);
    }
  }
}

function addRowAndColumn() {
  const row = newDataInfo.row;
  const column = newDataInfo.column;
  addRowAndColumnHandle(column, row);
}

function replaceColumnKey() {
  const oldProp = editeHeaderData.value.oldKey;
  const newProp = editeHeaderData.value.key;
  const newLabel = editeHeaderData.value.desc;
  tableDatasRef.value = tableDatasRef.value.map((item) => {
    const {[oldProp]: value, ...rest} = item;
    return {[newProp]: value, ...rest};
  });
  console.log(tableDatasRef.value)
  columnsRef.value.forEach((item) => {
    if (item.prop === oldProp) {
      item.prop = newProp;
      item.label = newLabel;
    }
  });
  editeHeader.value = false;

}

</script>

<template>
  <el-row style="padding-bottom: 5px">
    <el-popover placement="right" :width="400" trigger="click">
      <template #reference>
        <el-button style="margin-right: 16px">新增数据</el-button>
      </template>
      <el-row>
        <el-text>行数：</el-text>
        <el-input-number v-model="newDataInfo.row" :min="0"></el-input-number>
      </el-row>
      <el-row style="margin-top: 16px">
        <el-text>列数：</el-text>
        <el-input-number v-model="newDataInfo.column" :min="0"></el-input-number>
      </el-row>
      <el-row>
        <el-button type="primary" @click="addRowAndColumn">确定</el-button>
      </el-row>

    </el-popover>
    <el-button @click="addRowAndColumnHandle(1);">新增列</el-button>
    <el-button @click="addRowAndColumnHandle(undefined, 1);">新增行</el-button>
    <span style="flex-grow: 1"></span>
    <el-button type="primary" @click="$emit('submit', columnsRef, tableDatasRef)">保存</el-button>
  </el-row>
  <el-table v-model:data="tableDatasRef"
            border
            style="width: 100%"
            @cell-dblclick="cellDblclick"
            @header-contextmenu="handleHeaderRightClick"
            @row-contextmenu="handleRowRightClick"
            @cell-contextmenu="handleCellRightClick"
            max-height="calc(100vh - 172px)"
  >
    <el-table-column type="selection"></el-table-column>
    <template v-for="col in columnsRef">
      <el-table-column :key="col.prop" :column-key="col.prop" v-if="col.show" :width="col.width">
        <template #header="{ column,$index }">
          <el-text @dblclick="headerDbClick(column, $index)">{{ col.label }}[{{ col.prop }}]</el-text>
          <!--        <el-input v-show="!col.show" size="small" v-model="col.label" @blur="col.show = true"></el-input>-->
        </template>
        <template #default="{ row,column,$index }">
          <template v-if="col.type === ColumnTypeEnum.switch">
            <el-switch v-model="row[col.prop].content"></el-switch>
          </template>
          <template v-else>
            <p v-show="!row[col.prop].edit" style="width: 100%">{{ row[col.prop].content }}</p>
            <el-input v-show="row[col.prop].edit"
                      type="textarea" size="small"
                      v-model="row[col.prop].content"
                      @blur="row[col.prop].edit = false"
                      :autofocus="true"
            ></el-input>
          </template>

        </template>
      </el-table-column>
    </template>

  </el-table>

  <ContextMenu v-model:visible="contextMenu.show"
               :x="contextMenu.x"
               :y="contextMenu.y"
               @select="contextMenu.onSelect"
               :menus="contextMenu.data"

  ></ContextMenu>

  <el-dialog
      v-model="editeHeader"
      title="修改列信息"
      width="500"
  >
    <el-row>
      <el-text>描述：</el-text>
      <el-input v-model="editeHeaderData.desc"></el-input>
    </el-row>
    <el-row>
      <el-text>oldKey：</el-text>
      <el-input v-model="editeHeaderData.key"></el-input>
    </el-row>
    <el-row v-show="false">
      <el-text>newKey：</el-text>
      <el-input v-model="editeHeaderData.oldKey"></el-input>
    </el-row>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="editeHeader = false">取消</el-button>
        <el-button type="primary" @click="replaceColumnKey">
          确认
        </el-button>
      </div>
    </template>
  </el-dialog>

</template>

<style scoped lang="scss">

</style>