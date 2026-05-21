<template>
  <el-popover
    :width="props.width"
    :placement="props.placement"
    :trigger="props.trigger"
    :show-after="0"
    :hide-after="0"
    :teleported="props.teleported"
  >
    <template #reference>
      <el-button :type="props.type" :size="props.size" :plain="props.plain" :link="props.link" :disabled="props.disabled">
        <el-icon v-if="props.showIcon" class="mr4">
          <QuestionFilled />
        </el-icon>
        <slot name="button">{{ props.buttonText }}</slot>
      </el-button>
    </template>
    <div class="prompt-button-panel">
      <div v-if="props.title" class="prompt-button-title">{{ props.title }}</div>
      <div class="prompt-button-content">
        <slot>{{ props.content }}</slot>
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { QuestionFilled } from '@element-plus/icons-vue'

defineOptions({
  name: 'PromptButton'
})

const props = defineProps({
  buttonText: {
    type: String,
    default: '提示'
  },
  title: {
    type: String,
    default: ''
  },
  content: {
    type: String,
    default: ''
  },
  placement: {
    type: String,
    default: 'bottom'
  },
  trigger: {
    type: String,
    default: 'click'
  },
  width: {
    type: [String, Number],
    default: 420
  },
  type: {
    type: String,
    default: 'primary'
  },
  size: {
    type: String,
    default: 'default'
  },
  plain: {
    type: Boolean,
    default: true
  },
  link: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  },
  teleported: {
    type: Boolean,
    default: true
  },
  showIcon: {
    type: Boolean,
    default: true
  }
})
</script>

<style scoped>
.mr4 {
  margin-right: 4px;
}

.prompt-button-panel {
  max-width: 100%;
}

.prompt-button-title {
  margin-bottom: 8px;
  font-weight: 600;
  color: #303133;
}

.prompt-button-content {
  white-space: pre-wrap;
  color: #606266;
  line-height: 1.6;
}
</style>
