<script>
  export default {
    name: 'TicketDetailCommentsTab',
    props: {
      ctx: {
        type: Object,
        required: true,
      },
    },
    /**
     * 暴露详情组件内部上下文，保持当前 tab 只负责自身模板展示和交互触发。
     * @param {object} props 组件属性，包含详情内部上下文。
     * @returns {object} 当前 tab 模板所需的响应式上下文。
     */
    setup(props) {
      return props.ctx;
    },
  };
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
