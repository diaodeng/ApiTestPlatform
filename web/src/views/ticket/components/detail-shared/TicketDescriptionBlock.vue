<script setup name="TicketDescriptionBlock">
  import { ref, watch } from 'vue';

  /**
   * 工单描述与 AI 翻译共享展示块。
   * 供列表详情弹窗和独立详情页复用；原文与译文各自独立折叠。
   * “翻译”按钮为写操作（触发 AI 翻译），通过 allowTranslate 控制是否展示，权限由 v-hasPermi 控制。
   */
  const props = defineProps({
    // 展示的工单原文（翻译前的原始描述）
    originalDescription: {
      type: String,
      default: '',
    },
    // AI 翻译结果；为空时不展示翻译区块
    aiTranslation: {
      type: String,
      default: '',
    },
    // 是否允许手动触发翻译；只读入口传 false
    allowTranslate: {
      type: Boolean,
      default: false,
    },
    // 翻译请求进行中状态
    translateLoading: {
      type: Boolean,
      default: false,
    },
  });

  const emit = defineEmits(['translate']);

  // 原文与译文默认展开，切换工单时由父组件通过 key 重建或此处 watch 重置
  const descriptionExpanded = ref(true);
  const translationExpanded = ref(true);

  watch(
    () => [props.originalDescription, props.aiTranslation],
    () => {
      descriptionExpanded.value = true;
      translationExpanded.value = true;
    }
  );
</script>

<template>
  <section class="description-block">
    <div class="description-label">
      <span>描述</span>
      <div class="description-actions">
        <el-button
          v-if="allowTranslate"
          link
          type="primary"
          :loading="translateLoading"
          @click="emit('translate')"
          v-hasPermi="['ticket:ticket:edit']"
        >
          翻译
        </el-button>
        <el-button link type="primary" @click="descriptionExpanded = !descriptionExpanded">
          {{ descriptionExpanded ? '收起' : '展开' }}
        </el-button>
      </div>
    </div>
    <div :class="['description-content', { 'description-content--collapsed': !descriptionExpanded }]">
      {{ originalDescription || '-' }}
    </div>
    <div v-if="aiTranslation" class="translation-section">
      <div class="description-label">
        <span>AI翻译</span>
        <el-button link type="primary" @click="translationExpanded = !translationExpanded">
          {{ translationExpanded ? '收起' : '展开' }}
        </el-button>
      </div>
      <div :class="['description-content', { 'description-content--collapsed': !translationExpanded }]">
        {{ aiTranslation }}
      </div>
    </div>
  </section>
</template>

<style scoped>
  .description-label {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
    font-weight: 600;
    color: #303133;
  }

  .description-actions {
    display: flex;
    align-items: center;
    gap: 0;
  }

  .description-content {
    padding: 12px;
    border: 1px solid #ebeef5;
    border-radius: 6px;
    background: #fafafa;
    white-space: pre-line;
    word-break: break-word;
  }

  .description-content--collapsed {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .translation-section {
    margin-top: 12px;
  }
</style>
