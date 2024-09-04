<script setup>

import {CaseStepTypeEnum} from "@/components/hrm/enum.js";

const props = defineProps({
  x: {type: Number, default: 0},
  y: {type: Number, default: 0},
  menus: {type: Array, default: [{"title": "右键菜单"}]}
});

const visible = defineModel("visible", {type: Boolean, default: false});

const emits = defineEmits(["select"]);

</script>

<template>
  <div v-show="visible"
       :style="{left: x + 'px',top: y + 'px',display: visible ? 'block' : 'none'}"
       class="context-menu"
  >
    <div
        v-for="(item, i) in menus"
        :key="i"
        class="menu-item"
        @click="visible = false;$emit('select', item)"
        :disabled="item.disabled"
        style="display: flex;flex-direction: column;"
    >
      {{ item.title }}
<!--      <el-button type="success">{{ item.title }}</el-button>-->

    </div>
    <!--    <el-menu-->
    <!--        class="el-menu-demo"-->
    <!--        mode="horizontal"-->
    <!--        @select="visible = false;$emit('select', 'fadfadsf')"-->
    <!--    >-->
    <!--      <el-sub-menu index="1">-->
    <!--        <template #title>Workspace</template>-->
    <!--        <el-menu-item index="2-1">item one</el-menu-item>-->
    <!--        <el-menu-item index="2-2">item two</el-menu-item>-->
    <!--        <el-menu-item index="2-3">item three</el-menu-item>-->
    <!--        <el-sub-menu index="2-4">-->
    <!--          <template #title>item four</template>-->
    <!--          <el-menu-item index="2-4-1">item one</el-menu-item>-->
    <!--          <el-menu-item index="2-4-2">item two</el-menu-item>-->
    <!--          <el-menu-item index="2-4-3">item three</el-menu-item>-->
    <!--        </el-sub-menu>-->
    <!--      </el-sub-menu>-->
    <!--    </el-menu>-->
  </div>

</template>

<style scoped lang="scss">

.context-menu {
  margin: 0;
  background: #fff;
  z-index: 9999;
  position: fixed;
  list-style-type: none;
  padding: 4px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 400;
  color: #333;
  box-shadow: 2px 2px 2px 2px rgba(0, 0, 0, 0.3);

  .menu-item {
    padding: 0 15px;
    height: 32px;
    line-height: 32px;
    color: rgb(29, 33, 41);
    cursor: pointer;
  }

  .menu-item:hover {
    background: var(--el-color-primary-light-9);
    border-radius: 4px;
  }
}
</style>