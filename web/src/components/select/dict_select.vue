<script setup>
const props = defineProps(["optionsDict", "placeholder"])
const value = defineModel()
</script>

<template>
<el-select v-model="value" :placeholder="placeholder" clearable>
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