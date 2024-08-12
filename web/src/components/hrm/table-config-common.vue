<script setup>

/*
* 各种配置小表哥的通用模板
* */
import SelectDataType from "@/components/hrm/select-dataType.vue";
import SelectComparator from '@/components/select/popover-select.vue'
import {ElMessageBox} from 'element-plus';
import {inject} from "vue";

const props = defineProps(["cols"]);

const selfData = defineModel();

const multipleTable = ref(null);

const hrm_data_type = inject("hrm_data_type");
const hrm_comparator_dict = inject("hrm_comparator_dict");

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


function copy(event) {
  const selectedRows = multipleTable.value.getSelectionRows();
  if (selectedRows.length === 0) {
    ElMessageBox.alert('请选择要复制的行', '提示', {
      confirmButtonText: '确定',
    });
    return;
  }
  const copyData = [];
  selectedRows.forEach((row) => {
    copyData.push(toRaw(row));
  });
  console.log(copyData);
  // props.data.forEach((item, index) => {
  //   console.log(item.key)
  // })
}

function paste(event) {
  ElMessageBox.alert('没有可以粘贴的数据', '提示', {
    confirmButtonText: '确定',
  });
}


</script>

<template>
  <el-button size="small" @click="addRow">ADD</el-button>
  <el-button size="small" @click="delRow">DEL</el-button>
  <el-button size="small" @click="copy">COPY</el-button>
  <el-button size="small" @click="paste">PASE</el-button>
  <el-table
      table-layout="fixed"
      ref="multipleTable"
      tooltip-effect="dark"
      style="width: 100%"
      size="small"
      border
      :data="selfData"
  >
    <el-table-column type="selection" width="30"></el-table-column>
    <el-table-column v-for="col in cols" :label="col.name" v-bind="colWith(col.width)">

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
</template>

<style scoped lang="scss">

</style>