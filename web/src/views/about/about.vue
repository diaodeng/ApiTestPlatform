<script lang="ts" setup>
import {onMounted, ref} from 'vue'
import {
  Document,
  Menu as IconMenu,
  Location,
  Setting,
} from '@element-plus/icons-vue'
import QtrDocsBack from "@/components/hrm/common/qtr-docs-back.vue";

const isCollapse = ref(false);
const markdownSource = ref("");
const handleOpen = (key: string, keyPath: string[]) => {
  console.log(key, keyPath)
}
const handleClose = (key: string, keyPath: string[]) => {
  console.log(key, keyPath)
}

async function loadSource(fileName) {
  try {
    // 假设文档存储在项目的 docs/ 目录下
    const response = await fetch(`docs/${fileName}`);
    if (response.ok) {
      const text = await response.text()
      markdownSource.value = text;
    } else {
      console.log("请求异常");
    }
  } catch (error) {
    console.error('Error loading document:', error);
    markdownSource.value = 'Error loading document.';
  }
}

onMounted(()=>{
  loadSource('home.md');
})

</script>

<template>
  <div style="display: flex;height: 100vh">
    <el-menu
        default-active="0"
        class="el-menu-vertical-demo"
        :collapse="isCollapse"
        @open="handleOpen"
        @close="handleClose"
    >
      <el-menu-item index="0" @click="loadSource('home.md')">
        <template #title>
          <span style="font-weight: bold">首页</span>
        </template>
      </el-menu-item>
      <el-menu-item index="1" @click="loadSource('use_guide.md')">
        <template #title>
          <span style="font-weight: bold">简介</span>
        </template>
      </el-menu-item>
      <el-sub-menu index="3">
        <template #title>
<!--          <el-icon>-->
<!--            <location/>-->
<!--          </el-icon>-->
          <span style="font-weight: bold">详细介绍</span>
        </template>
        <el-menu-item index="3-1" @click="loadSource('case_config.md')">用例配置</el-menu-item>
        <el-menu-item index="3-2" @click="loadSource('run.md')">执行</el-menu-item>
        <el-menu-item index="3-3" @click="loadSource('configs.md')">配置范围及优先级</el-menu-item>
        <el-menu-item index="3-4" @click="loadSource('hooks.md')">关于Hook</el-menu-item>
        <el-menu-item index="3-5" @click="loadSource('assert.md')">断言</el-menu-item>
        <el-menu-item index="3-6" @click="loadSource('about_jobs.md')">定时任务</el-menu-item>
        <el-menu-item index="3-7" @click="loadSource('about_forward.md')">转发规则</el-menu-item>
      </el-sub-menu>
      <el-menu-item index="4" @click="loadSource('update_history.md')">
        <template #title>
          <span style="font-weight: bold">更新历史</span>
        </template>
      </el-menu-item>
      <el-menu-item index="5" @click="loadSource('develop.md')">
        <template #title>
          <span style="font-weight: bold">开发调试</span>
        </template>
      </el-menu-item>
    </el-menu>
    <el-scrollbar style="flex-grow: 1">
      <el-container style="padding: 20px;align-items: center;align-content: center">
        <QtrDocsBack v-model:markdown-source="markdownSource"></QtrDocsBack>
      </el-container>
    </el-scrollbar>

  </div>

</template>

<style scoped lang="scss">
.el-menu-vertical-demo:not(.el-menu--collapse) {
  width: 200px;
  min-height: 100vh;
}
</style>