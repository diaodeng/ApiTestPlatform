<script setup name="TicketDetailCommentsTab">
  import { ref, watch } from 'vue';
  import { getCurrentInstance } from 'vue';
  import { addTicketComment, getTicketComments } from '@/api/ticket/ticket';

  const props = defineProps({
    ticketId: {
      type: [Number, String],
      required: true,
    },
    active: {
      type: Boolean,
      default: false,
    },
  });

  const emit = defineEmits(['changed']);
  const { proxy } = getCurrentInstance();

  const commentLoading = ref(false);
  const commentLoaded = ref(false);
  const commentList = ref([]);
  const commentForm = ref({
    content: '',
    isInternal: false,
  });

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
    if (!commentForm.value.content) {
      proxy.$modal.msgWarning('请填写评论内容');
      return;
    }
    addTicketComment(props.ticketId, commentForm.value).then(() => {
      proxy.$modal.msgSuccess('评论成功');
      commentForm.value = { content: '', isInternal: false };
      loadComments(true);
      emit('changed');
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
  <el-form :model="commentForm" label-width="80px" class="mb16">
    <el-form-item label="评论">
      <el-input
        v-model="commentForm.content"
        type="textarea"
        :rows="3"
        placeholder="请输入沟通评论"
      />
    </el-form-item>
    <el-form-item>
      <el-checkbox v-model="commentForm.isInternal">内部评论</el-checkbox>
      <el-button
        type="primary"
        class="ml12"
        @click="submitComment"
        v-hasPermi="['ticket:comment:add']"
      >
        提交评论
      </el-button>
    </el-form-item>
  </el-form>
  <div v-loading="commentLoading">
    <el-empty v-if="!commentList.length" description="暂无评论" />
    <el-card v-for="item in commentList" :key="item.id" shadow="never" class="mb8">
      <div class="record-head">
        <span>{{ item.userName || '-' }}</span>
        <el-tag v-if="item.isInternal" size="small" type="warning">内部</el-tag>
        <span>{{ parseTime(item.createTime) }}</span>
      </div>
      <div>{{ item.content }}</div>
    </el-card>
  </div>
</template>

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
