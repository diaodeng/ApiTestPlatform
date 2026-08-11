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
      <el-button
        :type="props.type"
        :size="props.size"
        :plain="props.plain"
        :link="props.link"
        :circle="props.circle"
        :disabled="props.disabled"
      >
        <el-icon v-if="props.showIcon" :class="{ 'mr4': !props.circle && hasButtonText }">
          <component :is="iconComponent" />
        </el-icon>
        <template v-if="!props.circle">
          <slot name="button">{{ props.buttonText }}</slot>
        </template>
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
import { computed } from 'vue'
import * as ElementPlusIcons from '@element-plus/icons-vue'

defineOptions({
  name: 'PromptButton'
})

const props = defineProps({
  /** 按钮文字，传空字符串则仅显示图标 */
  buttonText: {
    type: String,
    default: ''
  },
  /** 弹窗标题 */
  title: {
    type: String,
    default: ''
  },
  /** 弹窗文本内容（简易模式，优先级低于 slot） */
  content: {
    type: String,
    default: ''
  },
  /** 弹窗弹出方向 */
  placement: {
    type: String,
    default: 'bottom'
  },
  /** 触发方式：click / hover */
  trigger: {
    type: String,
    default: 'click'
  },
  /** 弹窗宽度 */
  width: {
    type: [String, Number],
    default: 420
  },
  /** 按钮类型 */
  type: {
    type: String,
    default: ''
  },
  /** 按钮尺寸 */
  size: {
    type: String,
    default: 'small'
  },
  /** 是否镂空按钮 */
  plain: {
    type: Boolean,
    default: false
  },
  /** 是否为链接按钮 */
  link: {
    type: Boolean,
    default: false
  },
  /** 是否为圆形按钮（仅显示图标，隐藏文字） */
  circle: {
    type: Boolean,
    default: true
  },
  /** 是否禁用 */
  disabled: {
    type: Boolean,
    default: false
  },
  /** 弹窗是否 teleport 到 body */
  teleported: {
    type: Boolean,
    default: true
  },
  /** 是否显示图标 */
  showIcon: {
    type: Boolean,
    default: true
  },
  /** 图标名称（Element Plus Icons 导出名），默认 QuestionFilled */
  icon: {
    type: String,
    default: 'QuestionFilled'
  }
})

/** 是否有按钮文字显示 */
const hasButtonText = computed(() => {
  return props.buttonText !== '' && props.buttonText != null
})

/** 根据 icon prop 动态解析 Element Plus 图标组件 */
const iconComponent = computed(() => {
  const icon = ElementPlusIcons[props.icon]
  if (!icon) {
    console.warn(`[PromptButton] 图标 "${props.icon}" 不存在，降级使用 QuestionFilled`)
    return ElementPlusIcons['QuestionFilled']
  }
  return icon
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
