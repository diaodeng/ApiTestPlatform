<template>
  <el-dialog
      v-model="openConfigSuiteDataDialog"
      width="1200"
      title="套件数据配置"
      append-to-body
      destroy-on-close
      draggable
      overflow
      :close-on-click-modal="false"
      @closed="$emit('close-dialog')"
  >
    <el-tabs v-model="activeName" class="demo-tabs" @tab-click="handleClick">
      <el-tab-pane label="Case" name="Case">
        <CaseData
            :suiteId="suiteId"
            ref="callCase"
        >

        </CaseData>
      </el-tab-pane>
      <el-tab-pane label="Module" name="Module">
        <ModuleData
            :suiteId="suiteId"
            ref="callModule"
        >

        </ModuleData>
      </el-tab-pane>
      <el-tab-pane label="Project" name="Project">
        <ProjectData
            :suiteId="suiteId"
            ref="callProject"
        >

        </ProjectData>
      </el-tab-pane>
    </el-tabs>
  </el-dialog>
</template>

<script lang="ts" setup>

import ProjectData from "@/components/qtr/project-data.vue";

const openConfigSuiteDataDialog = defineModel("openConfigSuiteDataDialog");
import { ref, defineEmits } from 'vue'
import type { TabsPaneContext } from 'element-plus'
import CaseData from "@/components/qtr/case-data.vue";
import ModuleData from "@/components/qtr/module-data.vue";

const suiteId = defineModel("suiteId")
const activeName = ref('Case')
const callCase = ref(null);
const callModule = ref(null);
const callProject = ref(null);
const handleClick = (tab: TabsPaneContext, event: Event) => {
  // console.log(tab.props.name, event);
  if (tab.props.name === 'Case') {
    callCase.value.getList();
  } else if (tab.props.name === 'Module') {
    callModule.value.getList();
  } else if (tab.props.name === 'Project') {
    callProject.value.getList();
  }
}

const emit = defineEmits(["close-dialog"])

</script>

<style scoped lang="scss">
  .demo-tabs > .el-tabs__content {
    padding: 32px;
    color: #6b778c;
    font-size: 32px;
    font-weight: 600;
  }
</style>
