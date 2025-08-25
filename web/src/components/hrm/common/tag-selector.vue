<script setup>


const selectedValue = defineModel("selectedValue");
const props = defineProps({
  options: {type: Object},
  disable: {type: Boolean, default: false},
  selectorWidth: {default: "200px"},
  sourceData: {type: Object, default: undefined}
});
const emit = defineEmits(["selectChanged"]);

const selectedClass = computed(() => {
  const cur_item = props.options.filter((item)=>item.value*1===selectedValue.value);
  return cur_item&&cur_item.length>0?cur_item[0].elTagType:"primary";
});

</script>

<template>
  <el-select placeholder="请选择"
             v-model="selectedValue"
             :style="{width: selectorWidth}"
             :disabled="disable"
             filterable
             @change="$emit('selectChanged', $event, sourceData)"
  >
    <template #label="{ label, value }">
      <el-tag round size="small" :type="selectedClass">{{ label }}</el-tag>
    </template>
    <template #loading>加载中。。。</template>
    <el-option
        v-for="option in options"
        :key="option.value * 1"
        :label="option.label"
        :value="option.value * 1">
      <template #default>
        <el-tag round size="small" :type="option.elTagType">{{ option.label }}</el-tag>
      </template>
    </el-option>
  </el-select>
</template>

<style scoped lang="scss">

</style>