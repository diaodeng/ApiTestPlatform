<script>
  export default {
    name: 'TicketDetailOverviewTab',
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
  <el-row :gutter="16">
    <el-col :span="16">
      <el-card shadow="never" class="mb16">
        <template #header>
          <div class="panel-header">
            <span>最新AI结论</span>
            <el-button-group>
              <el-button
                type="primary"
                @click="openAiAnalysisDialog"
                v-hasPermi="['ticket:ai:analysis:run']"
              >
                发起AI分析
              </el-button>
              <el-button
                type="info"
                plain
                @click="refreshAiAnalysisData"
                :loading="aiAnalysisRefreshLoading"
                v-hasPermi="['ticket:ai:analysis:list']"
              >
                刷新AI数据
              </el-button>
              <el-button @click="openAiTaskHistory" v-hasPermi="['ticket:ai:analysis:list']">
                查看任务历史
              </el-button>
              <el-button
                type="warning"
                plain
                @click="openAiRepoMappingDialog()"
                v-hasPermi="['ticket:ai:mapping:add']"
              >
                管理映射
              </el-button>
              <el-button
                type="success"
                plain
                @click="openProjectVendorMapDialog()"
                v-hasPermi="['ticket:logpull:config']"
              >
                商家映射
              </el-button>
            </el-button-group>
          </div>
        </template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="最新执行状态">
            <el-tag
              v-if="latestAiAnalysisTask?.status"
              :type="getAiStatusTagType(latestAiAnalysisTask.status)"
            >
              {{ getAiStatusLabel(latestAiAnalysisTask.status) }}
            </el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="快照版本">
            {{ latestSnapshot?.version || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="快照时间">
            {{ parseTime(latestSnapshot?.createTime) || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="创建人">
            {{ latestSnapshot?.createdByName || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="摘要" :span="2">{{
            latestSnapshot?.summary || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="根因" :span="2">{{
            latestSnapshot?.rootCause || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="解决方案" :span="2">{{
            latestSnapshot?.solution || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="预防建议" :span="2">{{
            latestSnapshot?.prevention || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="风险说明" :span="2">{{
            latestSnapshot?.risk || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="负责人" :span="2">{{
            latestSnapshot?.owner || '-'
          }}</el-descriptions-item>
        </el-descriptions>
        <el-alert
          v-if="latestAiAnalysisTask?.errorMessage"
          type="error"
          show-icon
          :title="latestAiAnalysisTask.errorMessage"
          class="mt16"
        />
      </el-card>
    </el-col>
    <el-col :span="8">
      <el-card shadow="never">
        <template #header>相似工单</template>
        <el-empty v-if="!latestSimilarTickets.length" description="暂无相似工单" />
        <div v-for="item in latestSimilarTickets" :key="item.ticketId" class="similar-item">
          <div class="similar-title">{{ item.ticketNo }} {{ item.title }}</div>
          <div class="similar-meta">
            <span>相似度 {{ Math.round((item.score || 0) * 100) }}%</span>
            <span>{{ item.rootCause || '-' }}</span>
          </div>
          <div class="similar-actions">
            <el-link type="primary" :underline="false" @click="openSystemTicketDetail(item)"
              >系统详情</el-link
            >
            <el-link
              v-if="resolveTicketDetailUrl(item)"
              type="info"
              :underline="false"
              @click="openTicketLink(item)"
            >
              飞书详情
            </el-link>
            <el-button
              link
              type="success"
              :loading="issueActionLoading"
              @click="handleBindIssueFromSimilar(item)"
              v-hasPermi="['ticket:issue:bind']"
            >
              归入同一问题
            </el-button>
          </div>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>
