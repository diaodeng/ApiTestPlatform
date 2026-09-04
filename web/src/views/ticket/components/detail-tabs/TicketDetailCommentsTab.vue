<script setup name="TicketDetailCommentsTab">
  import { ref, watch } from 'vue';
  import { getCurrentInstance } from 'vue';
  import { Document } from '@element-plus/icons-vue';
  import { addTicketComment, buildTicketAttachmentUrl, getTicketComments } from '@/api/ticket/ticket';

  const props = defineProps({
    ticketId: {
      type: [Number, String],
      required: true,
    },
    active: {
      type: Boolean,
      default: false,
    },
    // 只读模式：隐藏评论提交区，仅保留评论列表查看
    readOnly: {
      type: Boolean,
      default: false,
    },
  });

  const emit = defineEmits(['changed']);
  const { proxy } = getCurrentInstance();

  const commentLoading = ref(false);
  const commentSubmitting = ref(false);
  const commentLoaded = ref(false);
  const commentList = ref([]);
  const commentForm = ref({
    content: '',
    isInternal: false,
  });

  /**
   * 判断评论是否来自一线回复字段（l1Response）。
   * @param {object} item 评论对象。
   * @returns {boolean} 是否一线回复。
   */
  function isL1ResponseComment(item) {
    return String(item?.sourceField || '') === 'l1Response';
  }

  /**
   * 从评论附件中提取附件文件列表。
   * attachments 可能形如 { comment_attachments: [...] }（记录评论）或
   * { content_segments: [...] }（排查过程富文本，无文件），只取文件类附件。
   * @param {object|Array} attachments 评论附件字段。
   * @returns {Array} 附件文件列表 [{fileToken,name,size,type}]。
   */
  function extractCommentFiles(attachments) {
    let files = [];
    if (Array.isArray(attachments)) {
      files = attachments;
    } else if (attachments && typeof attachments === 'object') {
      files = Array.isArray(attachments.comment_attachments) ? attachments.comment_attachments : [];
    }
    return (files || []).filter((file) => file && file.fileToken);
  }

  /**
   * 构建附件临时链接地址（后端 302 跳转飞书临时下载链接）。
   * @param {object} file 附件对象。
   * @returns {string} 临时链接地址。
   */
  function attachmentSrc(file) {
    return buildTicketAttachmentUrl(props.ticketId, file.fileToken);
  }

  /**
   * 判断附件是否为图片类型（用于决定内联展示或链接下载）。
   * @param {object} file 附件对象。
   * @returns {boolean} 是否图片。
   */
  function isImageFile(file) {
    const type = String(file.type || '').toLowerCase();
    const name = String(file.name || '').toLowerCase();
    return type.includes('image') || /\.(png|jpe?g|gif|bmp|webp|svg)$/.test(name);
  }

  /**
   * 获取当前工单评论列表，组件内部维护加载状态和缓存。
   * @param {boolean} force 是否强制刷新已加载数据。
   * @returns {Promise<void>} 评论加载完成 Promise。
   */
  function loadComments(force = false) {
    if (!props.ticketId || commentLoading.value || (commentLoaded.value && !force)) {
      return Promise.resolve();
    }
    commentLoading.value = true;
    return getTicketComments(props.ticketId)
      .then((response) => {
        commentList.value = response.data || [];
        commentLoaded.value = true;
      })
      .finally(() => {
        commentLoading.value = false;
      });
  }

  /**
   * 提交评论并刷新评论列表。
   * @returns {void}
   */
  function submitComment() {
    if (commentSubmitting.value) return;
    const content = String(commentForm.value.content || '').trim();
    if (!content) {
      proxy.$modal.msgWarning('请填写评论内容');
      return;
    }
    commentSubmitting.value = true;
    addTicketComment(props.ticketId, { ...commentForm.value, content }).then(() => {
      proxy.$modal.msgSuccess('评论成功');
      commentForm.value = { content: '', isInternal: false };
      return loadComments(true);
    }).then(() => {
      emit('changed');
    }).finally(() => {
      commentSubmitting.value = false;
    });
  }

  watch(
    () => props.ticketId,
    () => {
      commentLoaded.value = false;
      commentList.value = [];
      commentForm.value = { content: '', isInternal: false };
      if (props.active) {
        loadComments(true);
      }
    }
  );

  watch(
    () => props.active,
    (active) => {
      if (active) {
        loadComments();
      }
    },
    { immediate: true }
  );
</script>

<template>
  <div class="comments-tab">
    <section v-if="!readOnly" class="comment-composer">
      <div class="composer-heading">
        <div>
          <div class="composer-title">发表评论</div>
          <div class="composer-caption">用于工单沟通，不会触发 AI 分析</div>
        </div>
        <el-tag v-if="commentForm.isInternal" size="small" type="warning" effect="plain">内部可见</el-tag>
      </div>
      <el-input
        v-model="commentForm.content"
        type="textarea"
        :rows="3"
        resize="none"
        maxlength="4000"
        show-word-limit
        placeholder="输入沟通评论"
        :disabled="commentSubmitting"
        class="comment-input"
        @keydown.ctrl.enter.prevent="submitComment"
        @keydown.meta.enter.prevent="submitComment"
      />
      <div class="comment-composer-footer">
        <el-checkbox v-model="commentForm.isInternal" :disabled="commentSubmitting">
          内部评论
        </el-checkbox>
        <el-button
          v-hasPermi="['ticket:comment:add']"
          type="primary"
          icon="Promotion"
          :loading="commentSubmitting"
          :disabled="commentSubmitting || !String(commentForm.content || '').trim()"
          @click="submitComment"
        >
          提交评论
        </el-button>
      </div>
    </section>

    <section v-loading="commentLoading" class="comment-list-panel">
      <div class="comment-list-heading">
        <span>评论记录</span>
        <span class="comment-count">{{ commentList.length }} 条</span>
      </div>
      <el-empty v-if="!commentList.length" description="暂无评论" />
      <div v-else class="comment-list">
        <article v-for="item in commentList" :key="item.id" class="comment-item">
          <div class="comment-meta">
            <strong>{{ item.userName || '-' }}</strong>
            <el-tag v-if="item.isInternal" size="small" type="warning" effect="plain">内部</el-tag>
            <el-tag v-if="isL1ResponseComment(item)" size="small" type="success" effect="plain">一线回复</el-tag>
            <span class="comment-time">{{ parseTime(item.createTime) }}</span>
          </div>
          <div class="comment-content">{{ item.content || '-' }}</div>
          <div v-if="extractCommentFiles(item.attachments).length" class="comment-files">
            <template v-for="file in extractCommentFiles(item.attachments)" :key="file.fileToken">
              <a
                v-if="isImageFile(file)"
                class="comment-file-image"
                :href="attachmentSrc(file)"
                target="_blank"
                rel="noopener"
              >
                <img :src="attachmentSrc(file)" :alt="file.name" loading="lazy" />
              </a>
              <a v-else class="comment-file-link" :href="attachmentSrc(file)" target="_blank" rel="noopener">
                <el-icon><Document /></el-icon>
                {{ file.name }}
              </a>
            </template>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
  .comments-tab {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .comment-composer,
  .comment-list-panel {
    padding: 14px;
    border: 1px solid #e4e7ed;
    border-radius: 10px;
    background: #fff;
  }

  .comment-composer {
    background: #fbfcfe;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }

  .comment-composer:focus-within {
    border-color: #409eff;
    box-shadow: 0 0 0 2px rgb(64 158 255 / 12%);
  }

  .composer-heading,
  .comment-composer-footer,
  .comment-list-heading,
  .comment-meta {
    display: flex;
    align-items: center;
  }

  .composer-heading,
  .comment-list-heading {
    justify-content: space-between;
    gap: 12px;
  }

  .composer-title,
  .comment-list-heading {
    color: #303133;
    font-size: 14px;
    font-weight: 600;
  }

  .composer-caption,
  .comment-count {
    color: #909399;
    font-size: 12px;
    font-weight: 400;
  }

  .composer-caption {
    margin-top: 4px;
  }

  .comment-input {
    margin-top: 10px;
  }

  .comment-input :deep(.el-textarea__inner) {
    padding: 8px 10px;
    border-color: #dcdfe6;
    line-height: 1.6;
  }

  .comment-composer-footer {
    justify-content: space-between;
    gap: 12px;
    margin-top: 8px;
  }

  .comment-list-heading {
    padding-bottom: 10px;
    border-bottom: 1px solid #f0f2f5;
  }

  .comment-list {
    display: flex;
    flex-direction: column;
  }

  .comment-item {
    padding: 12px 2px;
    border-bottom: 1px solid #f0f2f5;
  }

  .comment-item:last-child {
    border-bottom: 0;
  }

  .comment-meta {
    gap: 8px;
    color: #606266;
    font-size: 12px;
  }

  .comment-time {
    margin-left: auto;
    color: #a8abb2;
  }

  .comment-content {
    padding: 8px 10px;
    margin-top: 7px;
    color: #303133;
    line-height: 1.65;
    white-space: pre-wrap;
    word-break: break-word;
    background: #f8fafc;
    border-radius: 6px;
  }

  .comment-files {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
  }

  .comment-file-image img {
    max-width: 180px;
    max-height: 140px;
    border: 1px solid #e4e7ed;
    border-radius: 6px;
    display: block;
  }

  .comment-file-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    color: #409eff;
    font-size: 12px;
    background: #f0f7ff;
    border-radius: 4px;
  }
</style>

<style scoped>
  .record-head {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 8px;
    color: #606266;
    font-size: 13px;
  }
</style>
