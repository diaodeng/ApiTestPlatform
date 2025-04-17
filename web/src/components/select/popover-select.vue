<script setup>
import {useTemplateRef} from "vue";

const props = defineProps({optionsDict:{require: true}, placeholder:{default:"请选择"}, clearable:{default: false}})
const value = defineModel()
const emits = defineEmits(["blur"])

const selectRef = useTemplateRef('selectRef')
function focus() {
  if (selectRef.value){

    nextTick(()=>{
      selectRef.value.focus();
    });
  }
}

defineExpose({focus});

</script>

<template>
  <el-select v-model="value"
             ref="selectRef"
             :placeholder="placeholder"
             :filterable="true"
             @blur="$emit('blur', $event)"
             :automatic-dropdown="true"
             :clearable="clearable"
  >

    <el-option
        v-for="(value, key, index) in optionsDict"
        :key="key"
        :label="key"
        :value="key"
    >
      <el-popover
          placement="right"
          :title="key"
          trigger="hover"
          :width="300"
          :content="value"
      >
        <template #reference>
          <el-text class="m-2">{{ key }}</el-text>
        </template>
        <el-scrollbar>
          <div>
            <el-text style="white-space: pre">{{ value }}</el-text>
          </div>
        </el-scrollbar>

      </el-popover>
    </el-option>
  </el-select>
</template>

<style scoped lang="scss">

</style>