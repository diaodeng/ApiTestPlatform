<template>
  <template v-if="model">
    <el-col :span="24">
      <el-divider content-position="left">通知配置</el-divider>
    </el-col>
    <el-col :span="12">
      <el-form-item label="启用通知" :prop="getProp('allowPush')">
        <el-switch
          v-model="model.allowPush"
          inline-prompt
          :active-value="1"
          :inactive-value="0"
          active-text="是"
          inactive-text="否"
        />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="推送项" :prop="getProp('pushIds')">
        <el-select
          v-model="model.pushIds"
          multiple
          filterable
          clearable
          collapse-tags
          collapse-tags-tooltip
          placeholder="选择已有推送项"
          :disabled="!model.allowPush"
        >
          <el-option
            v-for="item in pushOptions"
            :key="item.pushId"
            :label="`${item.name || item.pushId} [${item.pushId}]`"
            :value="item.pushId"
          />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="成功通知" :prop="getProp('success.push')">
        <el-switch
          v-model="model.success.push"
          inline-prompt
          :active-value="true"
          :inactive-value="false"
          active-text="是"
          inactive-text="否"
        />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="失败通知" :prop="getProp('failed.push')">
        <el-switch
          v-model="model.failed.push"
          inline-prompt
          :active-value="true"
          :inactive-value="false"
          active-text="是"
          inactive-text="否"
        />
      </el-form-item>
    </el-col>
  </template>
</template>

<script setup>
const props = defineProps({
  fieldPrefix: {
    type: String,
    default: ''
  },
  pushOptions: {
    type: Array,
    default: () => []
  }
})

const model = defineModel({
  type: Object,
  default: () => ({})
})

function getProp(name) {
  return props.fieldPrefix ? `${props.fieldPrefix}.${name}` : name
}
</script>
