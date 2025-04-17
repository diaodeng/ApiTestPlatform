<script setup>
// 可以编辑的单元格

import {ref} from 'vue'

const props = defineProps(["cellData"]);

const editing = ref(false);

function update(e) {
  editing.value = false;
  // e.target.value.trim();
}


</script>

<template>
  <div class="cell" :title="cellData" @click="editing = true">
    <!--    <input-->
    <!--        v-if="editing"-->
    <!--        :value="cellData"-->
    <!--        @change="update"-->
    <!--        @blur="update"-->
    <!--        @vue:mounted="({ el }) => el.focus()"-->
    <!--    >-->
    <!--    <span v-else>{{ cellData }}</span>-->
    <template v-if="editing">
      <div style="padding: 0;margin: 0" @focus="update">
        <slot name="edit"></slot>
      </div>
    </template>
    <template v-else>
      <slot name="show"></slot>
    </template>
  </div>
</template>

<style scoped lang="scss">
.cell, .cell input {
  //height: 1.5em;
  //line-height: 1.5;
  //font-size: 15px;
}

.cell span {
  //padding: 0 6px;
}

.cell input {
  width: 100%;
  box-sizing: border-box;
}
</style>