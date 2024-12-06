<script setup>

import {CirclePlus, EditPen, Remove, Plus, CirclePlusFilled, CopyDocument} from "@element-plus/icons-vue";
import {CaseStepTypeEnum} from "@/components/hrm/enum.js";
import RequestTypeDropdown from "@/components/hrm/case/request-type-dropdown.vue"

const props = defineProps(["indexKey", "type", "isShow", "notify"]);
const labelName = defineModel("nameText");
const labelEnable = defineModel("enable");
const emit = defineEmits(["editElement"]);
const edit = ref(false);


function selectedType(indexKey, type, stepData) {
  emit("editElement", 'add', indexKey, type, stepData);
}

</script>

<template>
  <span class="custom-tabs-label" v-show="isShow">
    <el-space :size="3">
<!--      <el-icon :size="15" v-if="type === 1" color="green">RQ-</el-icon>-->
      <!--      <el-icon :size="15" v-else-if="type === 2" color="blue">WS-</el-icon>-->
      <el-badge is-dot :offset="[0, 5]" v-if="notify">
        <el-switch v-model="labelEnable"
                   inline-prompt
                   active-text="启用"
                   inactive-text="禁用"
        ></el-switch>
      </el-badge>
      <el-switch v-model="labelEnable"
                 inline-prompt
                 active-text="启用"
                 inactive-text="禁用"
                 v-if="!notify"
      ></el-switch>

      <el-button v-if="type === CaseStepTypeEnum.http" type="success" link class="step-type-icon">RQ</el-button>
      <el-button v-else-if="type === CaseStepTypeEnum.websocket" type="primary" link
                 class="step-type-icon">WS</el-button>

      <span v-if="!edit" @dblclick.stop="()=>edit=true">{{ labelName }}</span>
      <input style="width: 80px"
             v-if="edit"
             v-model="labelName"
             @blur="()=>edit=false"
             @vue:mounted="({el})=>{el.focus()}"
      ></input>
      <!--      <el-icon :size="15" color="blue" @click="() => {edit=true}" v-show="!edit"><EditPen/></el-icon>-->
      <!--      <el-icon :size="15" @click="() => {edit=false}" v-show="edit"><Select/></el-icon>-->
      <!--      <el-icon :size="15" color="green" @click.stop="$emit('editElement', indexKey, 'add')"><CirclePlus/></el-icon>-->
      <el-popconfirm title="确认复制？"
                     @confirm="$emit('editElement', 'copy', indexKey)"
      >
        <template #reference>
          <el-icon :size="15" color="#e6a23c" @click.stop><CopyDocument/></el-icon>
        </template>
      </el-popconfirm>

      <RequestTypeDropdown :index-key="indexKey" @type-selected="selectedType"></RequestTypeDropdown>
      <el-popconfirm title="确定删除当前步骤?"
                     @confirm="$emit('editElement', 'remove', indexKey)"
      >
        <template #reference>
          <el-icon :size="15" color="red" @click.stop><Remove/></el-icon>
        </template>
      </el-popconfirm>

    </el-space>
  </span>
</template>

<style scoped lang="scss">

</style>