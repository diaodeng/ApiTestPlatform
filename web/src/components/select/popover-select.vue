<script setup>
const props = defineProps(["optionsDict", "placeholder"])
const value = defineModel()
</script>

<template>
  <el-select v-model="value" :placeholder="placeholder" clearable>

    <el-option
        v-for="(value, key, index) in optionsDict"
        :key="key"
        :label="key"
        :value="key"
    >
      <el-popover
          placement="bottom"
          :title="key"
          :width="200"
          trigger="hover"
          :content="value"
      >
        <template #reference>
          <el-text class="m-2">{{key}}</el-text>
        </template>
      </el-popover>
    </el-option>
  </el-select>
</template>

<style scoped lang="scss">

</style>