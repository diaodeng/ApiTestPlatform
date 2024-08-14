<script setup>

import {EditPen} from "@element-plus/icons-vue";

const content = defineModel();
const edit = ref(false);

</script>

<template>
  <span v-show="!edit" style="padding-right: 5px">{{ content }}</span>
  <el-input style="width: auto; padding-right: 5px" v-show="edit" v-model="content" @blur="evt => {edit=false}"></el-input>
  <el-icon :size="15" color="blue" @click="() => {edit=true}" v-show="!edit">
    <EditPen/>
  </el-icon>
  <el-icon color="green" :size="15" @click="() => {edit=false}" v-show="edit"><Select/></el-icon>
</template>

<style scoped lang="scss">

</style>