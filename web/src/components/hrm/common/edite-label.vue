<script setup>

import {CirclePlus, EditPen, Remove} from "@element-plus/icons-vue";
const props = defineProps(["indexKey"]);
const labelName = defineModel();
defineEmits(["editElement"]);
const edit = ref(false);
</script>

<template>
  <span class="custom-tabs-label">
    <el-space wrap :size="3">
      <span v-show="!edit">{{ labelName }}</span>
      <el-input style="width: 80px" v-show="edit" v-model="labelName"></el-input>
      <el-icon :size="15" color="blue" @click="() => {edit=true}" v-show="!edit"><EditPen/></el-icon>
      <el-icon :size="15" @click="() => {edit=false}" v-show="edit"><Select/></el-icon>
      <el-icon :size="15" color="green" @click.stop="$emit('editElement', indexKey, 'add')"><CirclePlus/></el-icon>
      <el-icon :size="15" color="red" @click.stop="$emit('editElement', indexKey, 'remove')"><Remove/></el-icon>
    </el-space>
  </span>
</template>

<style scoped lang="scss">

</style>