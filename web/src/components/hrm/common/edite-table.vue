<script setup>
import {useTemplateRef} from "vue";
import {ElMessage, genFileId} from "element-plus"
import * as XLSX from 'xlsx';
import ContextMenu from "@/components/hrm/common/context-menu.vue";
import {EditTableContextMenuEnum} from "@/components/hrm/enum.js";
import {findDuplicates, Json, randomString} from "@/utils/tools.js"
import Sortable from "sortablejs";
import AceEditorDialog from "@/components/hrm/common/ace-editor-dialog.vue";

const ColumnTypeEnum = {
  switch: 1,
  input: 2,
  select: 3
}
const columnsRef = defineModel("columnsRef");
const tableDatasRef = defineModel("tableDatasRef");
const currentTableRef = useTemplateRef("tableRef")
const uploadRef = useTemplateRef('upload');
const showEditorDialog = ref(false);

const showUploadDialog = ref(false);
const loadMode = ref(1);


const currentEditCell = ref({
  row: null,
  column: null,
  cell: null
})
const editorData = computed({
  get() {
    if (currentEditCell.value.row === null || !currentEditCell.value.column) {
      return "";
    }
    return currentEditCell.value.row[currentEditCell.value.column.columnKey].content;
  },
  set(newValue) {
    currentEditCell.value.row[currentEditCell.value.column.columnKey].content = newValue;
  }
});

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
const selectedIndex = ref([]);

// watch([() => props.tableHeaders, () => props.tableData], ([newHeader, newData]) => {
//   debugger
//   columnsRef.value = newHeader ? decompressText(newHeader) : [];
//   tableDatasRef.value = newData ? decompressText(newData) : [];
// })

function cellDblclick(row, column, cell, event) {
  if (event.ctrlKey) {
    // currentEditCell.value.row = tableDatasRef.value.indexOf(row);
    currentEditCell.value.row = row;
    currentEditCell.value.column = column;
    showEditorDialog.value = true;
    // const selectRow = tableDatasRef.value.find(item => item.value === row.value);
  } else {
    row[column.rawColumnKey].edit = true;

    const editInputEl = cell.querySelector('textarea');
    editInputEl && nextTick(() => {
      editInputEl.focus();
    });
  }

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
        newData["__row_key"] = randomString(10);
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

function selectionChangeHandel(newSelection) {
  let data = []
  newSelection.forEach((item) => {
    const index = tableDatasRef.value.indexOf(item);
    data.push(index)
  })
  data.sort((a, b) => b - a);
  selectedIndex.value = data;
}

function delRows(evt) {
  selectedIndex.value.forEach(index => {
    tableDatasRef.value.splice(index, 1);
  })
}

function copyRows(evt) {
  selectedIndex.value.forEach(index => {
    let oldRow = Json.parse(JSON.stringify(toValue(toRaw(tableDatasRef.value[index]))));
    oldRow.__row_key = randomString(10);
    tableDatasRef.value.splice(index + 1, 0, oldRow);

  })
}

function dragStart(ev, index) {
  console.log("dragStart.ev" + ev);
  console.log("dragStart.index" + index
  );
}

function drop(ev, index) {
  console.log("drop.ev:" + ev);
  console.log("drop.index:" + index);
}


function setSort() {//行拖拽
  // const tbody = document.querySelector('table.drag-table tbody');
  const tableEl = currentTableRef.value.$el;
  const tbody = tableEl.querySelector(`tbody`);
  new Sortable(tbody, {
    animation: 150,
    // filter: "span",
    handle: ".el-checkbox",
    sort: true,
    ghostClass: 'sortable-ghost',
    onEnd: (evt) => {
      console.log("e", evt);
      // const targetRow = tableDatasRef.value.splice(e.oldIndex, 1)[0];
      // tableDatasRef.value.splice(e.newIndex, 0, targetRow);
      const oldItem = tableDatasRef.value[evt.oldIndex];
      tableDatasRef.value.splice(evt.oldIndex, 1);
      tableDatasRef.value.splice(evt.newIndex, 0, oldItem);
    },
  });
}

function setSortCloumn() {//列拖拽
  const tableEl = currentTableRef.value.$el;
  const wrapperTr = tableEl.querySelector(`.el-table__header-wrapper tr`);
  Sortable.create(wrapperTr, {
    animation: 180,
    delay: 0,
    // filter: "thead > tr > th:nth-child(-n + 3)",
    // handle: ".el-text",
    draggable: "thead > tr > th:nth-child(n + 4)",
    onEnd: (evt) => {
      // 跳过显示的列数量，如开头我们用了一个多选框
      if (evt.oldIndex < 2) {
        return false;
      }  // 前三列是固定列，不允许拖拽

      const oldItem = columnsRef.value[evt.oldIndex - 2];
      columnsRef.value.splice(evt.oldIndex - 2, 1);
      columnsRef.value.splice(evt.newIndex - 2, 0, oldItem);
    },
    onStart: (evt) => {
      if (evt && evt.oldIndex < 2) {
        debugger
        return false;
      }
    }
  });
}

function handleFileUpload(file) {
  try {
    const reader = new FileReader();
    reader.onload = (e) => {
      const data = new Uint8Array(e.target.result);
      const workbook = XLSX.read(data, {type: 'array'});

      const firstSheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[firstSheetName];
      let jsonData = XLSX.utils.sheet_to_json(worksheet, {header: 1});
      jsonData = jsonData.filter(item => item.length > 0);  // 过滤空数据行

      if (!jsonData || jsonData.length <= 2) {
        ElMessage.warning("请检查文件内容，至少有一条数据可上传(注意:文件头是两行)");
        return;
      }

      if (loadMode.value === 2) {
        const hasBlank = jsonData[1].find((item) => {
          return item === undefined || item === ""
        })
        if (hasBlank) {
          ElMessage.warning("关键字行（第二行）不能有空字段");
          return;
        }

        const repeatKey = findDuplicates(jsonData[1]);
        if (repeatKey.length > 0) {
          ElMessage.warning("关键字行（第二行）不能有重复值，当前重复的值" + repeatKey.join(","));
          return;
        }

        columnsRef.value = jsonData[1].map((colProp, index) => {
          return {
            prop: colProp,
            label: jsonData[0][index],
            enable: true,
            show: true,
            type: colProp === "__enable" ? 1 : 2,
            width: colProp === "__enable" ? "70px" : ""
          };
        });
      } else if (loadMode.value === 1) {

      }

      console.log(jsonData)
      let tableData = jsonData.splice(2).map((row, index) => {

        let rowData = {};
        // row.forEach((col, index) => {
        //   rowData[jsonData[1][index]] = {"content": col, "edit": false}
        // });

        jsonData[1].forEach((col, index) => {
          rowData[col] = {"content": row[index], "edit": false}
        });

        rowData["__row_key"] = randomString(10);
        return rowData;

      });
      console.log(tableData)
      tableDatasRef.value = loadMode.value === 2 ? tableData : tableDatasRef.value.concat(tableData);
    };
    reader.readAsArrayBuffer(file.raw); // 注意这里使用 file.raw 来获取 File 对象
    showUploadDialog.value = false;
    ElMessage.success("导入成功");
  } catch (e) {
    console.log(e);
    ElMessage.error("导入失败");
  }

}

function beforeUpload(file) {
  // 在这里你可以添加额外的文件验证逻辑
  const isExcel = file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
      file.type === 'application/vnd.ms-excel';
  if (!isExcel) {
    ElMessage.error('Please upload an Excel file (.xlsx or .xls)');
    return false; // 阻止文件上传
  }
  return true; // 允许文件上传（但实际上文件并不会真的上传到服务器，因为我们设置了 action=""）
}

const handleExceed = (files) => {
  //重置文件
  uploadRef.value.clearFiles();
  const file = files[0]
  file.uid = genFileId()
  uploadRef.value.handleStart(file)
}

function exportToExcel() {
  try {
    // 创建工作簿
    const workbook = XLSX.utils.book_new();

    let headers = []
    let headerNames = columnsRef.value.map(item => {
      headers.push(item.prop);
      return item.label;
    });

    let tableDataArray = tableDatasRef.value.map(item => {
      return headers.map(col => {
        return typeof item[col] === "string" ? item[col] : item[col].content;
      });
    });
    tableDataArray.splice(0, 0, headers);
    tableDataArray.splice(0, 0, headerNames);

    // let tableData = [];
    // tableDatasRef.value.map(item =>{
    //   let newRow = {};
    //   for(const cell in item){
    //     newRow[cell] = typeof item[cell] === "string"? item[cell]:item[cell].content;
    //   }
    //   tableData.push(newRow);
    // });

    const worksheet = XLSX.utils.aoa_to_sheet(tableDataArray);

    // 将数据转换为工作表
    // const worksheet = XLSX.utils.json_to_sheet(tableData, {
    //   header: headers,
    // });

    // 将工作表添加到工作簿
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Sheet1');

    // 生成 Excel 文件并下载
    XLSX.writeFile(workbook, 'exported-data.xlsx');
    ElMessage.success("导出成功");
  } catch (e) {
    console.log(e);
    ElMessage.error("导出失败");
  }
}

onMounted(() => {
  setSort();
  setSortCloumn();
})

</script>

<template>
  <el-row style="padding-bottom: 5px; display: flex; flex-direction: row">
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
    <el-button @click="addRowAndColumnHandle(1);" type="success">新增列</el-button>
    <el-button @click="addRowAndColumnHandle(undefined, 1);" type="info">新增行</el-button>
    <el-button @click="copyRows" type="warning">复制选中行</el-button>
    <el-button @click="delRows" type="danger">删除选中行</el-button>
    <el-button @click="showUploadDialog = true" type="info">导入</el-button>
    <el-button @click="exportToExcel">导出</el-button>
    <span style="flex-grow: 1"></span>
    <el-button type="primary" @click="$emit('submit', columnsRef, tableDatasRef)">保存</el-button>
  </el-row>
  <el-table v-model:data="tableDatasRef"
            ref="tableRef"
            class="drag-edit-table"
            border
            style="width: 100%"
            @cell-dblclick="cellDblclick"
            @header-contextmenu="handleHeaderRightClick"
            @row-contextmenu="handleRowRightClick"
            @cell-contextmenu="handleCellRightClick"
            @selection-change="selectionChangeHandel"
            max-height="calc(100vh - 172px)"
            show-overflow-tooltip
            row-key="__row_key"
  >
    <el-table-column type="selection" fixed>
    </el-table-column>
    <el-table-column type="index" align="center" fixed>
      <template #header>序号</template>
    </el-table-column>
    <template v-for="col in columnsRef">
      <el-table-column :key="col.prop" :column-key="col.prop" v-if="col.show" :width="col.width" :label="col.label">
        <template #header="{ column,$index }">
          <el-text @dblclick="headerDbClick(column, $index)">{{ col.label }}[{{ col.prop }}]</el-text>
          <!--        <el-input v-show="!col.show" size="small" v-model="col.label" @blur="col.show = true"></el-input>-->
        </template>
        <template #default="{ row,column,$index }">
          <div style="margin: 0;padding: 0;overflow: hidden">
            <template v-if="col.type === ColumnTypeEnum.switch">
              <el-switch v-model="row[col.prop].content"></el-switch>
            </template>
            <template v-else>
              <el-text v-show="!row[col.prop].edit"
                       style="white-space: nowrap;overflow: hidden;text-overflow: ellipsis;display: inline-block;max-width: 100%"
              >{{ row[col.prop].content }}
              </el-text>
              <el-input v-show="row[col.prop].edit"
                        type="textarea" size="small"
                        v-model="row[col.prop].content"
                        @blur="row[col.prop].edit = false"
                        :autofocus="true"
                        style="flex-grow: 1"
              ></el-input>
            </template>
          </div>
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

  <el-dialog
      v-model="showUploadDialog"
      title="导入参数表格"
      width="500"
  >
    <el-upload
        ref="upload"
        action=""
        :auto-upload="false"
        :limit="1"
        :show-file-list="false"
        :drag="true"
        :on-change="handleFileUpload"
        :on-exceed="handleExceed"
        :before-upload="beforeUpload">
      <template #trigger>
        <el-button type="primary">选择文件</el-button>
      </template>
    </el-upload>
    <el-radio-group v-model="loadMode">
      <el-radio :value="1" size="large">增加</el-radio>
      <el-radio :value="2" size="large">覆盖</el-radio>
    </el-radio-group>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="showUploadDialog = false">关闭</el-button>
      </div>
    </template>
  </el-dialog>

  <AceEditorDialog v-model:show-dialog="showEditorDialog" v-model:edit-content="editorData"></AceEditorDialog>

</template>

<style scoped lang="scss">

</style>