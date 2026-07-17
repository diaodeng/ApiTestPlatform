<script>
  export default {
    name: 'TicketDetailCollabTab',
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
  <div class="collab-toolbar mb16">
    <el-button type="primary" @click="openAiAnalysisDialog" v-hasPermi="['ticket:ai:analysis:run']">
      发起AI分析
    </el-button>
    <el-button @click="openAiTaskHistory" v-hasPermi="['ticket:ai:analysis:list']">
      任务历史
    </el-button>
  </div>
  <el-row :gutter="16">
    <el-col :span="16">
      <el-form :model="messageForm" label-width="90px" class="mb16">
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="角色">
              <el-select v-model="messageForm.role">
                <el-option label="提问人" value="user" />
                <el-option label="AI" value="ai" />
                <el-option label="开发" value="developer" />
                <el-option label="测试" value="tester" />
                <el-option label="系统" value="system" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="类型">
              <el-select v-model="messageForm.messageType">
                <el-option label="追问" value="question" />
                <el-option label="分析" value="analysis" />
                <el-option label="日志" value="log" />
                <el-option label="结论" value="conclusion" />
                <el-option label="动作" value="action" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="发起AI">
              <el-switch
                v-model="messageForm.runAi"
                inline-prompt
                active-text="是"
                inactive-text="否"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-alert
              :title="`协同消息默认沿用工单版本号：${detail.versionKey || detail.extraData?.versionKey || '-'}。`"
              type="info"
              show-icon
              :closable="false"
              class="mb12"
            />
          </el-col>
          <el-col :span="24">
            <el-form-item label="版本号">
              <el-select
                v-model="messageForm.versionKey"
                placeholder="请选择或输入版本号"
                filterable
                clearable
                allow-create
                default-first-option
                style="width: 100%"
              >
                <el-option
                  v-for="item in detailVersionOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="Agent">
              <el-select
                v-model="messageForm.agentCode"
                placeholder="可选"
                filterable
                clearable
                @change="handleMessageAgentChange"
              >
                <el-option
                  v-for="item in agentOptions"
                  :key="item.agentCode"
                  :label="`${item.agentName || item.agentCode} [${item.agentCode}]`"
                  :value="item.agentCode"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="Provider">
              <el-select
                v-model="messageForm.aiProviderCode"
                placeholder="可选"
                filterable
                clearable
                style="width: 100%"
                @change="handleMessageProviderChange"
              >
                <el-option
                  v-for="item in providerOptions"
                  :key="item.providerCode"
                  :label="`${item.providerName || item.providerCode} [${item.providerCode}] ${item.modelName ? `- ${item.modelName}` : ''}`"
                  :value="item.providerCode"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="内容">
              <el-input
                v-model="messageForm.content"
                type="textarea"
                :rows="4"
                placeholder="补充追问、开发反馈、排查动作或AI结论"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="附件JSON">
              <el-input
                v-model="messageDataText"
                type="textarea"
                :rows="3"
                placeholder='可选，如 {"traceIds":["..."],"evidence":"..."}'
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item>
              <el-button type="primary" @click="submitMessage" v-hasPermi="['ticket:message:add']"
                >提交消息</el-button
              >
              <el-button @click="resetMessageForm">重置</el-button>
              <el-button
                type="success"
                plain
                @click="saveSnapshotFromCurrentState"
                v-hasPermi="['ticket:snapshot:add']"
              >
                生成快照
              </el-button>
              <el-button
                type="warning"
                plain
                @click="generateKnowledgeFromTicket"
                v-hasPermi="['ticket:knowledge:add']"
              >
                生成知识库
              </el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <el-card shadow="never">
        <template #header>消息流</template>
        <el-empty v-if="!messageItems.length" description="暂无消息" />
        <div v-for="item in messageItems" :key="item.id" class="mb12">
          <div class="record-head">
            <span>{{ item.roleLabel }}</span>
            <el-tag size="small">{{ item.typeLabel }}</el-tag>
            <span>{{ parseTime(item.createTime) }}</span>
          </div>
          <div>{{ item.content || '-' }}</div>
          <pre v-if="item.attachments" class="json-block">{{ formatJson(item.attachments) }}</pre>
        </div>
      </el-card>
    </el-col>
    <el-col :span="8">
      <el-card shadow="never">
        <template #header>相似工单</template>
        <el-empty v-if="!similarTickets.length" description="暂无相似工单" />
        <div v-for="item in similarTickets" :key="item.ticketId" class="similar-item">
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
