<script setup>

import {EditPen} from "@element-plus/icons-vue";

const content = defineModel('content');
const showEdite = defineModel("showEdite", {default: true});
const edit = ref(false);
const contentEditRef = ref(null);
const emit = defineEmits(['edite']);

</script>

<template>
  <span v-show="!edit" style="padding-right: 5px">{{ content }}</span>
  <el-input ref="contentEditRef"
            style="width: auto; padding-right: 5px"
            v-show="edit"
            v-model="content"
            @blur="evt => {$emit('edite', content);edit=false}"></el-input>
  <el-icon :size="15" color="blue" @click="() => {edit=true;contentEditRef.focus()}" v-show="!edit&&showEdite">
    <EditPen/>
  </el-icon>
  <el-icon color="green" :size="15" @click="() => {$emit('edite', content);edit=false}" v-show="edit"><Select/></el-icon>
</template>

<style scoped lang="scss">

</style>