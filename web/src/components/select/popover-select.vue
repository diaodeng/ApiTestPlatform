<script setup>
const props = defineProps(["optionsDict", "placeholder"])
const value = defineModel()
</script>

<template>
  <el-select v-model="value"
             :placeholder="placeholder"
             :filterable="true"
             clearable
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