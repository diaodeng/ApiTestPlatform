<script setup>

import {CirclePlus, EditPen, Remove, Plus} from "@element-plus/icons-vue";

const props = defineProps(["indexKey", "type"]);
const labelName = defineModel();
defineEmits(["editElement"]);
const edit = ref(false);
</script>

<template>
  <span class="custom-tabs-label">
    <el-space wrap :size="3">
      <el-icon :size="15" v-if="type === 1" color="green">RQ-</el-icon>
      <el-icon :size="15" v-else-if="type === 2" color="blue">WS-</el-icon>
      <span v-show="!edit">{{ labelName }}</span>
      <el-input style="width: 80px" v-show="edit" v-model="labelName"></el-input>
      <el-icon :size="15" color="blue" @click="() => {edit=true}" v-show="!edit"><EditPen/></el-icon>
      <el-icon :size="15" @click="() => {edit=false}" v-show="edit"><Select/></el-icon>
<!--      <el-icon :size="15" color="green" @click.stop="$emit('editElement', indexKey, 'add')"><CirclePlus/></el-icon>-->
      <el-popover
          placement="top-start"
          title="步骤类型"
          :width="200"
          trigger="click"
          content="this is content, this is content, this is content"
      >
        <template #reference>
          <el-icon :size="15" color="green"><CirclePlus/></el-icon>
        </template>
        <template #default>
          <el-menu>
            <el-menu-item index="1">
              <el-button size="default" type="primary" @click.stop="$emit('editElement', indexKey, 'add', 1)">request</el-button>
            </el-menu-item>
            <el-menu-item index="2">
              <el-button size="default" type="warning" @click.stop="$emit('editElement', indexKey, 'add', 2)">websocket</el-button>
            </el-menu-item>
            <el-menu-item index="3">
              <el-button size="default" type="info" disabled>webUI</el-button>
            </el-menu-item>
            <el-menu-item index="4">
              <el-button size="default" type="info" disabled>import API</el-button>
            </el-menu-item>
            <el-menu-item index="5">
              <el-button size="default" type="info" disabled>import CASE</el-button>
            </el-menu-item>
          </el-menu>
        </template>
      </el-popover>
      <el-icon :size="15" color="red" @click.stop="$emit('editElement', indexKey, 'remove')"><Remove/></el-icon>
    </el-space>
  </span>
</template>

<style scoped lang="scss">

</style>