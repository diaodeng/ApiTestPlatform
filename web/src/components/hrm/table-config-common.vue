<script setup>

/*
* 各种配置小表哥的通用模板
* */
import SelectDataType from "@/components/hrm/select-dataType.vue";
import SelectComparator from '@/components/select/popover-select.vue'
import {ElMessage, ElMessageBox} from 'element-plus';
import {inject, useTemplateRef} from "vue";
import {useClipboard} from "@vueuse/core";
import {Json, parseHeader} from "@/utils/tools.js";
import Sortable from "sortablejs";

const props = defineProps({
  cols: {type: Object},
  tableTitle: {type: String, default: ""},
  toolFixTarget: {type: String, default: ""},
  toolFixOffset: {type: Number, default: 0}
});

const selfData = defineModel();

// const multipleTable = ref(null);

const multipleTable = useTemplateRef("tableRef")

const hrm_data_type = inject("hrm_data_type");
const hrm_comparator_dict = inject("hrm_comparator_dict");

const {text, copy, copied, isSupported} = useClipboard({legacy: true})

function colWith(content) {
  if (content) {
    return {width: content};
  }
  return {}
}

function addRow(event) {

  if (selfData.value && typeof selfData.value === "object") {

    selfData.value.push({
      key: '',
      value: '',
      enable: true,
      type: 'string',
      desc: '',
      dataId: selfData.value.length,
    })
  } else {
    console.log("selfData is not object")
    // selfData = ref([{
    //   key: '',
    //   value: '',
    //   type: 'string',
    //   desc: '',
    // }])
  }
}


function delRow(event) {
  const selectedRows = multipleTable.value.getSelectionRows();
  console.log(multipleTable.value)
  if (selectedRows.length === 0) {
    ElMessageBox.alert('请选择要删除的行', '提示', {
      confirmButtonText: '确定',
    });
    return;
  }

  selectedRows.forEach((row) => {
    selfData.value.splice(selfData.value.indexOf(row), 1);
  })

  // 重置选中的行
  multipleTable.value.clearSelection();

}

function copyData(event) {
  try {
    if (!isSupported.value) {
      ElMessage.warning("您的浏览器不支持复制", "复制失败");
    }
    const selectedRows = multipleTable.value.getSelectionRows();
    if (selectedRows.length === 0) {
      ElMessage.warning("请选择要复制的行");
      return;
    }
    let copyData = [];
    console.log("selectedRows:", selectedRows)
    selectedRows.forEach((row) => {
      let new_line = JSON.parse(JSON.stringify(toRaw(row)));
      new_line.dataId = selfData.value.length;
      copyData.push(new_line);
    });
    copy(Json.compressJson(copyData));
    ElMessage.success("复制成功");
  } catch (e) {
    ElMessage.warning("复制失败");
  }
}

function paste(event) {
  navigator.clipboard.readText().then((content) => {
    let data = parseHeader(content);
    data = JSON.parse(JSON.stringify(data))
    let tableLines = selfData.value.length;
    data.map((item, index) => {
      item["dataId"] = tableLines;
      tableLines += 1;
    })
    selfData.value.push(...data);
  }).catch(() => {
    ElMessage.warning("粘贴失败");
  })

}

function changeSwitch(changeType) {
  // 全开 open、全关 close、反选 invert
  let newStatus = null;
  selfData.value.forEach((item, index) => {
    if (changeType === "open") {
      newStatus = true;
    } else if (changeType === "close") {
      newStatus = false;
    } else if (changeType === "invert") {
      newStatus = !item.enable;
    } else {
      console.log("类型错误");
      return;
    }
    item.enable = newStatus;
  });

}

function uniKey(row) {
  return row.dataId;
}

/*
* 数据没有ID需要添加唯一ID作为数据行唯一标识
* */
onMounted(() => {
  selfData.value.map((item, index) => {
    if (!("dataId" in item)) {
      item["dataId"] = index;
    }

  })
  setSort();
})

function setSort() {//行拖拽
  // const tbody = document.querySelector('table.drag-table tbody');
  const tableEl = multipleTable.value.$el;
  const tbody = tableEl.querySelector(`tbody`);
  new Sortable(tbody, {
    animation: 150,
    // filter: ".el-input__wrapper",
    handle: ".el-checkbox",
    sort: true,
    // ghostClass: 'sortable-ghost',
    onEnd: (evt) => {
      console.log("e", evt);
      // const targetRow = tableDatasRef.value.splice(e.oldIndex, 1)[0];
      // tableDatasRef.value.splice(e.newIndex, 0, targetRow);
      const oldItem = selfData.value[evt.oldIndex];
      selfData.value.splice(evt.oldIndex, 1);
      selfData.value.splice(evt.newIndex, 0, oldItem);
    },
  });
}

</script>

<template>
  <div class="config-table-container">
    <div>
      <el-text v-if="tableTitle"> {{ tableTitle }}</el-text>
      <div style="display: flex; justify-content: left; align-items: center; padding-bottom: 5px">
        <el-tooltip placement="top"
                    content="增加行"
        >
          <el-button size="small" @click="addRow" icon="CirclePlusFilled" type="success" circle></el-button>
        </el-tooltip>
        <el-tooltip placement="top"
                    content="删除选中行"
        >
          <el-button size="small" @click="delRow" icon="RemoveFilled" type="danger" circle></el-button>
        </el-tooltip>
        <el-tooltip placement="top"
                    content="复制选中行"
        >
          <el-button size="small" @click="copyData" icon="CopyDocument" type="warning" circle
                     :disabled="!isSupported"></el-button>
        </el-tooltip>
        <el-tooltip placement="top"
                    content="粘贴"
        >
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
        v-model:data="selfData"
    >
      <el-table-column type="selection" width="30"></el-table-column>
      <el-table-column v-for="col in cols" :label="col.name" v-bind="colWith(col.width)">
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

        <template #default="{ row, $index }">
          <template v-if="col.type === 'select'">
            <SelectDataType v-model="row.type" :options="hrm_data_type"></SelectDataType>
          </template>
          <template v-else-if="col.type === 'compaList'">
            <SelectComparator v-model="row[col.prop]" :options-dict="hrm_comparator_dict"></SelectComparator>
          </template>
          <template v-else-if="col.type === 'switch'">
            <el-switch v-model="row[col.prop]"></el-switch>
          </template>
          <template v-else>
            <el-input v-model="row[col.prop]"></el-input>
          </template>
        </template>

      </el-table-column>
      <!--    <el-table-column prop="key" label="key" width="300"></el-table-column>-->
      <!--    <el-table-column prop="value" label="type" width="300"></el-table-column>-->
      <!--    <el-table-column prop="desc" label="value" show-overflow-tooltip></el-table-column>-->
    </el-table>
  </div>

</template>

<style scoped lang="scss">

</style>