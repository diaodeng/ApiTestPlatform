<script lang="ts" setup>
import {ref} from 'vue'
import {
  Document,
  Menu as IconMenu,
  Location,
  Setting,
} from '@element-plus/icons-vue'

const isCollapse = ref(false)
const handleOpen = (key: string, keyPath: string[]) => {
  console.log(key, keyPath)
}
const handleClose = (key: string, keyPath: string[]) => {
  console.log(key, keyPath)
}
</script>

<template>
  <el-menu
      default-active="2"
      class="el-menu-vertical-demo"
      :collapse="isCollapse"
      @open="handleOpen"
      @close="handleClose"
  >
    <el-sub-menu index="1">
      <template #title>
        <el-icon>
          <location/>
        </el-icon>
        <span>介绍</span>
      </template>

      <el-menu-item index="1-1">创建</el-menu-item>
      <el-menu-item index="1-2">执行</el-menu-item>
      <el-menu-item index="1-2">报告</el-menu-item>
      <el-menu-item index="1-2">环境管理</el-menu-item>
      <el-menu-item index="1-2">接口管理</el-menu-item>

      <el-menu-item index="1-3">item three</el-menu-item>
      <el-sub-menu index="1-4">
        <template #title><span>详细指南</span></template>
        <el-menu-item index="1-4-1">关于Hook</el-menu-item>
        <el-menu-item index="1-4-1">断言</el-menu-item>
        <el-menu-item index="1-4-1">定时任务</el-menu-item>
      </el-sub-menu>
    </el-sub-menu>
    <el-menu-item index="2">
      <el-icon>
        <icon-menu/>
      </el-icon>
      <template #title>Navigator Two</template>
    </el-menu-item>
    <el-menu-item index="3" disabled>
      <el-icon>
        <document/>
      </el-icon>
      <template #title>Navigator Three</template>
    </el-menu-item>
    <el-menu-item index="4">
      <el-icon>
        <setting/>
      </el-icon>
      <template #title>更新历史</template>
    </el-menu-item>
  </el-menu>
</template>

<style scoped lang="scss">
.el-menu-vertical-demo:not(.el-menu--collapse) {
  width: 200px;
  min-height: 100vh;
}
</style>