<script setup>

import {CirclePlus, EditPen, Remove, Plus, CirclePlusFilled} from "@element-plus/icons-vue";
import {CaseStepTypeEnum} from "@/components/hrm/enum.js";
import RequestTypeDropdown from "@/components/hrm/case/request-type-dropdown.vue"

const props = defineProps(["indexKey", "type"]);
const labelName = defineModel();
const emit = defineEmits(["editElement"]);
const edit = ref(false);

function selectedType(indexKey, type, stepData) {
  emit("editElement", 'add', indexKey, type, stepData);
}

</script>

<template>
  <span class="custom-tabs-label">
    <el-space wrap :size="3">
<!--      <el-icon :size="15" v-if="type === 1" color="green">RQ-</el-icon>-->
      <!--      <el-icon :size="15" v-else-if="type === 2" color="blue">WS-</el-icon>-->
      <el-button v-if="type === 1" type="text" style="color: green">RQ</el-button>
      <el-button v-else-if="type === 2" type="text" color="blue">WS</el-button>

      <span v-show="!edit">{{ labelName }}</span>
      <el-input style="width: 80px" v-show="edit" v-model="labelName"></el-input>
      <el-icon :size="15" color="blue" @click="() => {edit=true}" v-show="!edit"><EditPen/></el-icon>
      <el-icon :size="15" @click="() => {edit=false}" v-show="edit"><Select/></el-icon>
      <!--      <el-icon :size="15" color="green" @click.stop="$emit('editElement', indexKey, 'add')"><CirclePlus/></el-icon>-->
      <RequestTypeDropdown :index-key="indexKey" @type-selected="selectedType"></RequestTypeDropdown>
      <el-icon :size="15" color="red" @click.stop="$emit('editElement', 'remove', indexKey)"><Remove/></el-icon>
    </el-space>
  </span>
</template>

<style scoped lang="scss">

</style>