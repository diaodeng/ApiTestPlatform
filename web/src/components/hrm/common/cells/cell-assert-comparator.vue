<script setup>
// 可以编辑的单元格

import {ref} from 'vue'
import SelectComparator from "@/components/select/popover-select.vue";

const props = defineProps(["hrm_comparator_dict"]);
const cellData = defineModel('cellData')

const editing = ref(false);

function update(e) {
  editing.value = false;
}

const selectRef = ref(null);

onMounted(()=>{});
watch(()=>editing.value, (newValue)=>{
  if (newValue){
    nextTick(()=>{
      selectRef.value.focus();
    });
  }

});

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
      <div style="padding: 0;margin: 0">
        <SelectComparator
            ref="selectRef"
            v-model="cellData"
            :options-dict="hrm_comparator_dict"
            @blur="()=>{editing = false}"
            :clearable="false"
        ></SelectComparator>
      </div>
    </template>
    <template v-else>
      <span style="width: 100%;">{{ cellData }}</span>
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