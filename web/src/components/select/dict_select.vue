<script setup>
import {useTemplateRef} from "vue";

const props = defineProps({
  optionsDict: {},
  placeholder: {default: "请选择"},
  clearable: {type: Boolean, default: false}
})
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
           :placeholder="placeholder"
           :clearable="clearable"
           @blur="()=>{$emit('blur', $event)}"
           :automatic-dropdown="true"
           ref="selectRef"
>
  <el-option
      v-for="dict in optionsDict"
      :key="dict.value"
      :label="dict.label"
      :value="dict.value"
      :disabled="dict.disabled"
  />
</el-select>
</template>

<style scoped lang="scss">

</style>